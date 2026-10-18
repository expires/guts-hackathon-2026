# ADR 0068: Learn, a financial literacy course

Date: 2026-10-18. Status: accepted. Replaces the Concepts collection as the main way to learn.

- Concepts become a course called "Learn" on the Play tab, next to Play solo and Play with friends.
- Path layout like a level map. 6 units in student-lifecycle order: Money basics; Student money; Staying safe; Making money grow; After uni; The bigger picture.
- The existing 50 concepts are reordered into the units. New student lessons: needs vs wants, budgeting, scholarships and bursaries, overdrafts, buy now pay later, scams, payslips, tax and National Insurance, student loan repayments.
- Sequential unlock: a lesson opens only when the previous one is passed. A locked lesson shows "Finish <previous lesson> first". Each unit shows progress (for example 3/8).
- Each lesson: 2 or 3 short cards (one idea each), at least one real UK number from the facts table with its official source and checked date, then a 3-question quiz. Pass = 2 of 3. Retries allowed.
- Lesson text is fixed, written by us, not AI-generated. The server grades the quiz, so answers do not reach the client before an attempt.
- Life game events still award the concept as a bonus (`life_bonus`). The path order is the main way to learn; a life bonus does not unlock path lessons.
- "Ask Penny about this lesson" opens Penny with the lesson as context.
- Icons are SF Symbols chosen per concept (fixes Inflation and Spreading risk).
- Sample students start with the first lessons passed, so a judge sees progress.
- Contract: `lifeline_contracts/learn.py`; `GET /v1/learn`, `GET /v1/learn/lessons/{lesson_id}` (409 `lesson_locked`), `POST /v1/learn/lessons/{lesson_id}/attempts`. All take `language`.
- Languages: UI strings in all 8 languages. Lesson text is served in the requested language where a translation exists, otherwise English.
