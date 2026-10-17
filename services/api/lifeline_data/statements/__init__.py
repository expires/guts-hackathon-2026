"""Bank statement import (ADR 0029). Deterministic code, no LLM. All text in a file is untrusted (ADR 0034).

Public API:
- `parse_statement(content: bytes, filename: str | None = None) -> ParsedStatement`. Never raises.
- `to_snapshot(parsed, as_of=None, ...) -> FinanceSnapshot` for `DataHub.set_user_snapshot`.

Supported: Monzo CSV and Revolut CSV exports (the provider is detected from the header row).
PDF: returns status "failed" with a warning (PDF parsing comes later in Tier 2).
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

__all__ = ["MAX_BYTES", "MAX_ROWS", "ParsedStatement", "parse_statement", "to_snapshot"]
