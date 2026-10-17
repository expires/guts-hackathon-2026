"""Bank statement import (ADR 0029). Deterministic code, no LLM. All text in a file is untrusted (ADR 0034).

Public API:
- `parse_statement(content: bytes, filename: str | None = None) -> ParsedStatement`. Never raises.
- `to_snapshot(parsed, as_of=None, ...) -> FinanceSnapshot` for `DataHub.set_user_snapshot`.

Supported: Monzo CSV and Revolut CSV exports (the provider is detected from the header row), and text PDF
statements with date, description, amount and balance columns (statements/pdf.py; scanned or CID-font PDFs fail
with a warning). `to_snapshot` also fills income_sources, debts and is_student (statements/detect.py).
Sample statements (demo/statements/, ADR 0047): `list_samples()`, `load_sample(id)` in statements/samples.py.
Limits: 5 MB, 20,000 data rows. Malformed rows are skipped with a warning; the rest import.
Sign convention: money out is negative. Only GBP rows import (FinanceSnapshot is GBP only).
"""

from lifeline_data.statements.parse import (
    MAX_BYTES,
    MAX_ROWS,
    ParsedStatement,
    parse_statement,
    to_snapshot,
)
from lifeline_data.statements.samples import list_samples, load_sample

__all__ = ["MAX_BYTES", "MAX_ROWS", "ParsedStatement", "list_samples", "load_sample", "parse_statement", "to_snapshot"]
