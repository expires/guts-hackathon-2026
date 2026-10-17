# ADR 0058: Rules and facts come from official sources

Date: 2026-10-17. Status: accepted. Source: user instruction.

- Every facts-table entry (`lifeline_engine/rules.py`) stores the official URL and the date it was checked. Allowed sources: gov.uk (incl. HMRC, Student Finance England, SLC guidance), saas.gov.uk, studentfinancewales.co.uk, studentfinanceni.co.uk, railcard.co.uk / 16-25railcard.co.uk, legislation.gov.uk, bankofengland.co.uk.
- BOSS verifies each entry against its page. Only a fact with no official source is flagged to the user.
- Penny follows the same flow for rules questions (tax, student loans, ISAs, benefits, council tax, Railcard):
  1. Use the facts table first; show its URL and "checked <date>" in sources.
  2. If the fact is not in the table, run web search restricted to the official domains above, quote the value, and cite the page with the date it was retrieved.
  3. If no official page states it, say that plainly and give no number.
- Rule numbers from the web are checked like every other number: the value must appear in the fetched official text.

## Amendment (W3 quiz sources)

- The official list also includes `www.ons.gov.uk` and `www.nomisweb.co.uk` (Office for National Statistics and its labour-market service). They are official statistics publishers; some lesson charts have official pages only there.
