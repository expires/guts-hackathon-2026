# ADR 0060: Instant screens and Penny's full toolset

Date: 2026-10-17. Status: accepted. Slotted into DIRECTION_V2 steps 1 and 2; installed with the step 2 build.

## 1. Instant screens
- The app keeps the last known response for each read endpoint on the phone (disk cache) and shows it at once; a background refresh replaces it quietly.
- Profile, Money home and lists load once at app launch, not on every tab switch.
- Fixed content ships in the app bundle: characters and student paths, sample students, Quick Life students, lessons, concepts. The server copy refreshes it when it changes.
- If something must load, the screen shows skeleton shapes of its real layout, never a spinner with text.
- Target: on the phone over Railway, every tab opens with content in under 0.5 s after the first launch.

## 2. Penny tools
- Every engine function and live source is a Penny tool: Next Move, Test it, finance summary, user balance, cash flow projection, spend prediction, habit score, facts table, Bank of England rates, ONS inflation (CPI), currency conversion (Frankfurter FX, ECB reference rates, no key), news and rate dates, official web search (ADR 0058).
- Red-team test: "Can I afford a holiday that costs 1 million yuan?" Penny converts CNY to GBP herself, states the rate and its date, then checks the amount against the user's money.

## 3. Penny never asks for what she can look up
- Penny asks the user only for what only the user knows (plans, preferences, dates of their own events). Never for rates, conversions, dates of public events or public facts. A prompt rule and golden tests enforce it.

## 4. Live steps
- Each real tool call streams a plain-words step ("Checking exchange rates…", "Checking your balance…"). Steps come only from real tool calls.

## 5. Suggested questions
- Starter chips show only while the chat is empty and disappear for the rest of the conversation after the first message. Follow-up chips under a reply match Penny's question; never a lone "Yes".
