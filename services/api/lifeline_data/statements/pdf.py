"""Text-based PDF statement reader. Standard library only (zlib), no PDF dependency.

Scope: PDFs with real text (not scans) that use simple fonts, such as the sample statements made by
tools/gen_statements.py. It reads every text block (BT..ET) as one line of cells, then keeps lines shaped
like a statement row: date first, then description, then amount and balance as the last two numbers.
Many bank PDFs use embedded CID fonts; their text is not readable this way and the import fails with a
clear message. All text is untrusted (ADR 0034): it is cleaned and only stored as data.
"""

from __future__ import annotations

import re
import time
import zlib
from datetime import date, datetime

MAX_STREAM_HEADERS = 2_000  # stream objects read per file
MAX_TOTAL_BYTES = 8 * 1024 * 1024  # raw bytes of every stream (read or skipped) plus decompressed output
MAX_ROWS = 20_001  # one more than the importer accepts, so it can report "too many rows"
TIME_BUDGET_S = 2.0  # parse stops and reports what it has after this much time

_DATE_FORMATS = ("%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d")
_NUMBER = re.compile(r"^[+-]?£?-?\d{1,3}(,\d{3})*(\.\d{2})$|^[+-]?£?-?\d+(\.\d{2})$")
_INTEREST = re.compile(rb"[(<\[A-Za-z'\"]")  # next byte the tokenizer cares about
_OP = re.compile(rb"[A-Za-z'\"*]+")
_TEXT_OPS = {b"Tf", b"Tm", b"Td", b"TD", b"Tc", b"Tw", b"Tz", b"TL", b"Ts", b"Tr", b"T"}


class _Budget:
    """Work limit: a deadline on the monotonic clock, checked every few thousand steps."""

    def __init__(self, seconds: float) -> None:
        self.deadline = time.monotonic() + seconds
        self.steps = 0
        self.over = False

    def tick(self) -> bool:
        self.steps += 1
        if self.steps & 0xFFF == 0 and time.monotonic() > self.deadline:
            self.over = True
        return self.over


def _streams(content: bytes, budget: _Budget) -> list[bytes]:
    """One linear pass: find each `stream` keyword, read to the next `endstream`, continue after it.
    The dictionary before the keyword (at most 400 bytes back) says the filter. Limits: MAX_STREAM_HEADERS
    streams and MAX_TOTAL_BYTES in total, counting skipped streams too."""
    out: list[bytes] = []
    total = 0
    headers = 0
    pos = 0
    while not budget.over:
        k = content.find(b"stream", pos)
        if k < 0:
            break
        after = k + 6
        if content[k - 3:k] == b"end" or content[after:after + 1] not in (b"\r", b"\n"):
            pos = after
            continue
        headers += 1
        if headers > MAX_STREAM_HEADERS:
            break
        start = after + (2 if content[after:after + 2] == b"\r\n" else 1)
        end = content.find(b"endstream", start)
        if end < 0:
            break
        pos = end + 9
        lo = content.rfind(b"<<", max(0, k - 400), k)
        header = content[lo:k] if lo >= 0 else b""
        data = content[start:end].rstrip(b"\r\n")
        total += len(data)
        if total > MAX_TOTAL_BYTES:
            break
        if b"/FlateDecode" in header:
            try:
                data = zlib.decompressobj().decompress(data, MAX_TOTAL_BYTES - total + 1)
            except zlib.error:
                continue
            total += len(data)
            if total > MAX_TOTAL_BYTES:
                break
        elif b"/Filter" in header:
            continue  # other filters (images, LZW, ...) are not text we can read
        out.append(data)
    return out


_LIT_SPECIAL = re.compile(rb"[\\()]")
_ESCAPES = {ord("n"): 10, ord("r"): 13, ord("t"): 9, ord("b"): 8, ord("f"): 12}


def _literal(data: bytes, i: int, budget: _Budget) -> tuple[bytes, int]:
    """Read a PDF literal string starting after '('. Returns (bytes, index after ')'). Plain runs are copied by
    regex, so the Python loop only runs on backslashes and parentheses."""
    out = bytearray()
    depth = 1
    n = len(data)
    while i < n and not budget.tick():
        m = _LIT_SPECIAL.search(data, i)
        if m is None:
            out += data[i:]
            return bytes(out), n
        out += data[i:m.start()]
        i = m.start()
        c = data[i]
        if c == 0x5C:  # backslash
            i += 1
            if i >= n:
                break
            e = data[i]
            if e in _ESCAPES:
                out.append(_ESCAPES[e])
            elif 0x30 <= e <= 0x37:
                j = i
                while j < n and j < i + 3 and 0x30 <= data[j] <= 0x37:
                    j += 1
                out.append(int(data[i:j], 8) & 0xFF)
                i = j - 1
            elif e not in (10, 13):  # backslash-newline is a line continuation
                out.append(e)
        elif c == 0x28:
            depth += 1
            out.append(c)
        else:
            depth -= 1
            if depth == 0:
                return bytes(out), i + 1
            out.append(c)
        i += 1
    return bytes(out), n


def _text_rows(stream: bytes, budget: _Budget) -> list[list[str]]:
    """Each BT..ET block becomes one row; each string shown by Tj, ', " or TJ becomes one cell.
    Linear: every step moves forward; plain bytes are skipped by regex."""
    rows: list[list[str]] = []
    cells: list[str] | None = None
    pending: list[bytes] = []  # strings waiting for their operator
    i, n = 0, len(stream)
    while i < n and len(rows) < MAX_ROWS and not budget.tick():
        m = _INTEREST.search(stream, i)
        if m is None:
            break
        i = m.start()
        c = stream[i]
        if c == 0x28:
            s, i = _literal(stream, i + 1, budget)
            pending.append(s)
        elif c == 0x3C:
            if i + 1 < n and stream[i + 1] == 0x3C:  # dictionary, not a hex string
                i += 2
                continue
            j = stream.find(b">", i)
            if j < 0:
                break
            hexs = re.sub(rb"[^0-9A-Fa-f]", b"", stream[i + 1:j])
            pending.append(bytes.fromhex((hexs + b"0" * (len(hexs) % 2)).decode()))
            i = j + 1
        elif c == 0x5B:  # array start: TJ collects the strings inside
            i += 1
        else:
            om = _OP.match(stream, i)
            op = om.group(0) if om else stream[i:i + 1]
            i += len(op)
            if op == b"BT":
                cells, pending = [], []
            elif op == b"ET":
                if cells:
                    rows.append(cells)
                cells, pending = None, []
            elif op in (b"Tj", b"'", b'"') and cells is not None and pending:
                cells.append(pending[-1].decode("cp1252", "replace"))
                pending = []
            elif op == b"TJ" and cells is not None:
                cells.append(b"".join(pending).decode("cp1252", "replace"))
                pending = []
            elif op not in _TEXT_OPS:
                pending = []
    return rows


def _parse_date(text: str) -> date | None:
    text = text.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _is_number(text: str) -> bool:
    return bool(_NUMBER.match(text.strip().replace(" ", "")))


def _number(text: str) -> float:
    return float(text.strip().replace(" ", "").replace("£", "").replace(",", ""))


def extract_rows(
    content: bytes, budget_s: float = TIME_BUDGET_S
) -> tuple[list[tuple[date, str, float, float | None]], str]:
    """(rows, full_text). Each row is (date, description, amount, balance or None). Never raises on bad input.
    Bounded work: linear scans, stream and byte caps, and a time budget (rows found so far are returned)."""
    found: list[tuple[date, str, float, float | None]] = []
    text_parts: list[str] = []
    budget = _Budget(budget_s)
    for stream in _streams(content, budget):
        if budget.over or len(found) >= MAX_ROWS:
            break
        for cells in _text_rows(stream, budget):
            cells = [c.strip() for c in cells if c.strip()]
            text_parts.append(" ".join(cells))
            if len(cells) < 3:
                continue
            day = _parse_date(cells[0])
            if day is None:
                continue
            nums = [k for k in range(1, len(cells)) if _is_number(cells[k])]
            if not nums or nums[0] < 2:
                continue
            first = nums[0]
            desc = " ".join(cells[1:first])
            amount = _number(cells[first])
            balance = _number(cells[first + 1]) if first + 1 < len(cells) and first + 1 in nums else None
            found.append((day, desc, amount, balance))
    return found, "\n".join(text_parts)
