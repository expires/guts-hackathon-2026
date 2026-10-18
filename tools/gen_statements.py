"""Write the sample statements for the 10 students (PENNY_V3_BUILD.md A, ADR 0072). W1 owns this file.

The students, their funding, rent and spending live in services/api/lifeline_data/statements/seed.py (package code,
so the API can build each statement up to the day before the import). This script writes the demo files for the
fixed reference day seed.REF_DAY:
- services/api/lifeline_data/statements/samples/ (package data) and demo/statements/ (identical copy for judges):
  <id>.csv (the CSV layout the importer reads), <id>.pdf (text PDF with a running balance), index.json
  (SampleStatement card fields + `hints`, including the sources per figure).
- docs/seed_sources.md: the A5.5 table and every figure's source.
Deterministic, no network, standard library only. Run from the repo root:
  uv run --project services/api python tools/gen_statements.py [out_dir]
"""

from __future__ import annotations

import json
import sys
import zlib
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "services" / "api"))

from lifeline_data.statements import seed  # noqa: E402
from lifeline_data.statements.seed import START, Profile, Tx  # noqa: E402

OUTPUT_DIRS = [REPO / "services" / "api" / "lifeline_data" / "statements" / "samples", REPO / "demo" / "statements"]
DOC = REPO / "docs" / "seed_sources.md"


# ---------- PDF (minimal writer, Helvetica, WinAnsiEncoding) -------------------------------------

# Helvetica advance widths (1/1000 em) for the characters used in numbers.
_NUM_W = {**dict.fromkeys("0123456789", 556), ".": 278, ",": 278, "-": 333, "+": 584, "£": 556, " ": 278}


def _num_width(text: str, size: float) -> float:
    return sum(_NUM_W.get(c, 556) for c in text) * size / 1000


def _pdf_str(text: str) -> str:
    raw = text.encode("cp1252", "replace")
    out = []
    for b in raw:
        ch = chr(b)
        if ch in "()\\":
            out.append("\\" + ch)
        elif 32 <= b < 127:
            out.append(ch)
        else:
            out.append(f"\\{b:03o}")
    return "(" + "".join(out) + ")"


def _row(cells: list[tuple[float, float, str, str, float]]) -> str:
    """One BT..ET block per table row: each cell is (x, y, font, text, size). The parser reads one row per block."""
    parts = ["BT"]
    for x, y, font, text, size in cells:
        parts.append(f"/{font} {size:g} Tf 1 0 0 1 {x:.2f} {y:.2f} Tm {_pdf_str(text)} Tj")
    parts.append("ET")
    return "\n".join(parts)


def _money(v: float) -> str:
    return f"{v:,.2f}"


def to_pdf(p: Profile, txs: list[Tx], opening: float, end: date) -> bytes:
    width, height, left, right = 595.0, 842.0, 40.0, 555.0
    first_page_rows, rows_per_page = 44, 55  # page 1 has the summary block
    pages_rows = [txs[:first_page_rows]] + [txs[i:i + rows_per_page]
                                            for i in range(first_page_rows, len(txs), rows_per_page)]
    money_in_total = sum(t.amount for t in txs if t.amount > 0)
    money_out_total = -sum(t.amount for t in txs if t.amount < 0)
    closing = txs[-1].balance if txs else opening
    streams: list[str] = []
    for n, chunk in enumerate(pages_rows, start=1):
        ops: list[str] = []
        y = height - 50
        if n == 1:
            ops.append(_row([(left, y, "F2", p.bank, 20)]))
            y -= 22
            ops.append(_row([(left, y, "F2", f"{p.current_name} statement", 12)]))
            y -= 16
            ops.append(_row([(left, y, "F1", "Sample statement built from real UK figures. Not a real person or "
                                             "account.", 8)]))
            y -= 20
            ops.append(_row([(left, y, "F1", f"Account holder: {p.holder}", 9)]))
            y -= 13
            ops.append(_row([(left, y, "F1", f"Period: {START.strftime('%d/%m/%Y')} to {end.strftime('%d/%m/%Y')}",
                              9)]))
            y -= 13
            for label, value in (("Opening balance", opening), ("Money in", money_in_total),
                                 ("Money out", money_out_total), ("Closing balance", closing)):
                text = _money(value)
                ops.append(_row([(left, y, "F1", label, 9), (200 - _num_width(text, 9), y, "F1", text, 9)]))
                y -= 12
            y -= 10
        ops.append(_row([(left, y, "F2", "Date", 9), (110, y, "F2", "Description", 9),
                         (430 - _num_width("Amount (GBP)", 9) * 1.1, y, "F2", "Amount (GBP)", 9),
                         (right - _num_width("Balance (GBP)", 9) * 1.1, y, "F2", "Balance (GBP)", 9)]))
        y -= 14
        for t in chunk:
            desc = t.name if t.description.upper() == t.name.upper() else f"{t.name} - {t.description}"
            amt, bal = _money(t.amount), _money(t.balance)
            ops.append(_row([(left, y, "F1", t.day.strftime("%d/%m/%Y"), 8), (110, y, "F1", desc[:62], 8),
                             (430 - _num_width(amt, 8), y, "F1", amt, 8),
                             (right - _num_width(bal, 8), y, "F1", bal, 8)]))
            y -= 13
        ops.append(_row([(left, 30, "F1", f"Page {n} of {len(pages_rows)}. Sample statement.", 7)]))
        streams.append("\n".join(ops))

    objects: list[bytes] = []
    n_pages = len(streams)
    page_ids = [5 + 2 * i for i in range(n_pages)]
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{' '.join(f'{i} 0 R' for i in page_ids)}] /Count {n_pages} >>".encode())
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>")
    for i, s in enumerate(streams):
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {width:g} {height:g}] "
                       f"/Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents {page_ids[i] + 1} 0 R >>".encode())
        data = zlib.compress(s.encode("latin-1"), 9)
        objects.append(f"<< /Length {len(data)} /Filter /FlateDecode >>\nstream\n".encode() + data
                       + b"\nendstream")
    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R /Info << /Title (Sample statement {p.id}) "
            f"/Producer (gen_statements.py) >> >>\nstartxref\n{xref}\n%%EOF\n").encode()
    return bytes(out)


# ---------- main ---------------------------------------------------------------------------------


def build(out_dir: Path, end: date = seed.REF_END) -> list[dict[str, object]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    index = []
    for sample_id in seed.IDS:
        p, rows, opening = seed.statement(sample_id, end)
        (out_dir / f"{p.id}.csv").write_bytes(seed.to_csv(p, rows))
        (out_dir / f"{p.id}.pdf").write_bytes(to_pdf(p, rows, opening, end))
        index.append(seed.index_entry(sample_id, end))
    (out_dir / "index.json").write_text(json.dumps({"samples": index}, indent=2, ensure_ascii=False) + "\n")
    return index


def _gbp(v: float) -> str:
    return f"£{v:,.0f}" if v >= 0 else f"-£{-v:,.0f}"


def report(end: date = seed.REF_END) -> str:
    """docs/seed_sources.md: the A5.5 table, then every figure and its source per student."""
    lines = [
        "# Seed sources: the 10 sample students",
        "",
        f"Generated by `tools/gen_statements.py` from `services/api/lifeline_data/statements/seed.py`. Reference "
        f"import day {seed.REF_DAY.isoformat()} (statements 1 July 2026 to {end.isoformat()}). Sources checked "
        f"{seed.CHECKED}. Research limit: PENNY_V3_BUILD.md A2 and A3 only; any other figure is marked "
        "\"example within <source> range\" with the range. The import builds each statement up to the day before "
        "the import, so the dates move; the funding schedules and amounts do not.",
        "",
        "## A5.5 report",
        "",
        "Income = money in a month from the stated funding (termly payments shown per term). Actual = September "
        "2026 non-rent spending in the statement (every payment out except rent and transfers to savings). "
        "Forecast = the data-side B2 estimate on the reference day (10% buffer); the engine owns the real forecast.",
        "",
        "| Student | Bank | Town (region) | Income | Rent | Target Sept | Actual Sept | Diff | Forecast "
        "(expected) | Sources |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for sample_id in seed.IDS:
        p, rows, _ = seed.statement(sample_id, end)
        actual = seed.non_rent_spending(rows, "2026-09")
        fc = seed.expected_forecast(p, rows, end)
        state = str(fc["state"]).replace("_", " ")
        extra = f", runs out {fc['run_out']}" if fc.get("run_out") else f", spare {_gbp(float(fc['spare']))}" \
            if fc.get("spare") is not None else ""
        income = "; ".join(f"{label} {_gbp(float(m['amount']))}/{m['period']}"
                           for label, m in zip([x[0] for x in p.card.money_in], seed.card_money_in(p, rows),
                                               strict=True))
        rent = next((s.value for s in p.sources if s.ref == "rent"), "-")
        srcs = sorted({s.source for s in p.sources})
        lines.append(f"| {p.holder} ({p.id}) | {p.bank} | {p.card.city} ({p.card.region}) | {income} | {rent} | "
                     f"{_gbp(p.target)} | £{actual:,.2f} | {(actual / p.target - 1) * 100:+.1f}% | "
                     f"{state}{extra} (A4: {p.expected_state.replace('_', ' ')}) | {'; '.join(srcs)} |")
    lines += ["", "## Figures and sources per student", ""]
    for sample_id in seed.IDS:
        p = seed.profile(sample_id)
        lines += [f"### {p.holder} ({p.id})", "", "| Figure | Value | Source | URL | Checked | Example range |",
                  "|---|---|---|---|---|---|"]
        for s in p.sources:
            lines.append(f"| {s.figure} | {s.value} | {s.source} | {s.url or '-'} | {seed.CHECKED} | "
                         f"{s.note or 'official figure'} |")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


if __name__ == "__main__":
    if len(sys.argv) > 1:
        build(Path(sys.argv[1]))
    else:
        for target in OUTPUT_DIRS:
            build(target)
        DOC.write_text(report(), encoding="utf-8")
