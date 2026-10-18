# ADR 0063: Onboarding order and language choice

Date: 2026-10-18. Status: accepted. Amends ADR 0049.

- Order: Welcome -> Language -> 3 or 4 feature cards (Next Move, Test it, Ask Penny, Play with friends; one headline and one line each; Skip) -> an open Penny chat (general, student-and-finance scoped, not tied to any data) -> pick your student (sample statements, upload, or enter your numbers).
- Language screen: "About 1 in 4 students at UK universities come from outside the UK (HESA 2024/25)." Verified: 685,565 of 2,863,180 enrolments (23.9%), HESA SB273 Figure 7, https://www.hesa.ac.uk/data-and-analysis/sb273/figure-7, checked 2026-10-18. HESA counts home address before study, not nationality, so the wording says "come from outside the UK". Languages: English, Français, Español, Português, Italiano, 简体中文, हिन्दी, नेपाली. The screen changes live on tap, then Confirm. Arabic, Urdu and others show "Coming soon". You tab: Change language.
- Scope: app UI text is localised (String Catalog). Penny answers in the chosen language (ChatRequest.language) with Western digits and £, so the number verifier is unchanged. Engine text from the server (move headlines, evidence) stays English in this build.
- Translations are machine-written by the agent and labelled as such in the README; native speakers may review later.
