# ADR 0036: Merge of Yaffy's integration branch (one-time git exception)

- Status: accepted
- Date: 2026-10-17
- Requested by: the user (one-time exception to the no-git rule, for this merge only)

## Decision
- The merge happens in a separate scratch clone. The user's `main`, index and working tree (112 uncommitted changes) are not touched.
- Branch `merge/yaffy` from `main`:
  1. One snapshot commit of the current work. A merge needs our side committed.
  2. A merge commit with `integration`.
- The finished branch reaches the user's repo through `git fetch <clone> merge/yaffy:merge/yaffy`, which only creates the ref. **No push.** The user reviews and pushes.
- Conflicts:
  - Files both sides changed: ours, then his additions re-applied (insights route, client methods, contract paths, router registrations).
  - Files only he changed or added: his.
  - Generated files are regenerated, never hand-merged: `make contract` and `make ios-gen` (XcodeGen rebuilds `project.pbxproj`).
- `services/api/data/private/` is not in the branch. `.gitignore` keeps `**/data/private/`, `**/data/cache/` and `**/credentials.json`. Yaffy says the keys there are structural placeholders. Tokens and bank data live only in Postgres, encrypted (ADR 0028).
- Product rules applied to his code:
  - Insights opens from the Spending tile, not from Money home.
  - His emoji map to our icons in the UI.
  - `SampleInsights` appears only in previews and the Mock configuration, never in Live.
- His `tests/conftest.py` must not change our default test mode (demo data mode, test app env, `tier2` and `live` deselected).

## Consequences
- `merge/yaffy` is a snapshot. Workers keep building in the main tree, so their later changes are not on the branch. After the user pushes and pulls, the next sync is a normal commit by the user.

## Amendment: final merge permission
- The user authorised merging everything into `main` once all work is done. This is still no push without the user's word.
- Bank routes in the merge: keep Yaffy's Monzo implementation of `/v1/bank/*`. Add `provider=truelayer` → 409 `source_disabled`, and replace the mock link with 409 `source_unavailable` in live mode (ADR 0027).

## Follow-ups after the merge (BOSS)
- Yaffy's connected-account tokens (Monzo, Trading212) are stored as plain files under `CREDENTIALS_DIR`. They must move to Postgres, encrypted with `lifeline_data.crypto.Sealer` (`TOKEN_ENCRYPTION_KEY`), as ADR 0028 requires. Owner: W1, after the final merge.
- The JWT-shaped token in Yaffy's public history (commit 31eaaa6): revoke if real; a history rewrite is Yaffy's call.
