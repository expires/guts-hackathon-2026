# ADR 0069: Onboarding redesign

Date: 2026-10-18. Status: accepted. Amends ADR 0063 (onboarding order) and ADR 0062 (sample students).

- Back button on every onboarding screen. Skip only where it makes sense (Language keeps the current language, Try Penny, How Penny decides).
- Order: Welcome; Problem ("One app. Every source. One clear decision."); Language; What you can do; Try Penny; Pick your student; Building their profile; Their profile; How Penny decides; Their Next Move; Start.
- What you can do: 5 items (See all your money; Your next move; Test it first; Ask Penny; Learn and play with friends). Explainer list: icon, headline, one line. No card shadows, no chevrons, nothing looks tappable.
- Pick your student: larger cards with name, age, avatar, uni and city, funding body or type, money in per week, month or term with dates, housing, and a one-line habit description. "Upload a statement" and "Enter your numbers" stay below. Contract: `SampleStatement` gains `name`, `age`, `avatar`, `uni`, `city`, `funding_label`, `money_in` (`SampleMoneyIn`), `housing`, `habit_line`.
- Building their profile: 8 real stages (Reading the statement; Finding income sources; Sorting spending; Finding bills and subscriptions; Checking debts; Checking live UK data; Scoring habits; Building the profile). Each stage ends when its real call or step ends. Skeleton loaders. A "View profile" button, no auto-jump.
- Their profile: income sources with amounts and dates, housing, spending by category chart, bills and subscriptions, debts, savings and months of cover, habit score with its 6 parts as bars (no amounts), "3 things Penny noticed" with a small visual each, tappable to the evidence. This replaces the separate "3 things" screen.
- How Penny decides: "Penny compared N options using this profile and live UK data (sources listed). Here is the one that helps most this month." Contract: `NextMoveResponse.options_compared`.
- Their Next Move: headline with the action, a one-line reason, the trade-off, plain-English confidence, and "Also considered:" with two runners-up, one line each. Contract: `Move.reason` and `Move.confidence_text` (for example "Medium confidence: based on your last 4 weeks of spending"). The app shows `confidence_text` everywhere and never "Medium · sample 4".
- All text in the 8 languages. Penny-generated text follows the chosen language.
