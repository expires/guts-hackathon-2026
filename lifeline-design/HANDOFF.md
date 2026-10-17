# Lifeline — design handoff

Mobile app for a 24-hour hackathon. Personal finance (Money tab) plus a life game (Life tab) on real UK mortgage data.
Pitch: "Aladdin stress tests portfolios. We stress test a life."

## What is in this folder

- `screens/*.dc.html` — one file per screen, 390 × 844 px phone frames.
  These files come from the Claude Design canvas. They use a design runtime (`support.js`, `<x-dc>`, `<sc-for>`, `<sc-if>`, `<dc-import>`) that is NOT included.
  Use them as the visual and markup reference. Rebuild the screens in the app's own framework.
- `screens/Icon.dc.html` — the icon set. Each icon is inline SVG on a 48 × 48 grid. Copy the paths.
- `screens/canvas.json` — canvas layout only. Ignore it for the build.

## Screens to build (final set)

| Tab | File | Screen |
|---|---|---|
| Money | `A2-Money.dc.html` (theme "Paper", card "White") | Money home. Next Move card is the hero. |
| Money | `Money-Why.dc.html` | "Why?" bottom sheet |
| Money | `Money-Test.dc.html` | "Test it": two lives side by side |
| Money | `Money-Guess.dc.html` | Guess my spend game |
| Money | `Money-More.dc.html` | Money tab, scrolled: net worth, subscriptions, budgets, goals |
| Life | `Life-Main.dc.html` | Story feed, stats, Age button |
| Life | `Life-Assets.dc.html` | Assets menu (list) |
| Life | `Life-Event.dc.html` | Full-screen event choice |
| Life | `Life-Lesson.dc.html` | Lesson after a key moment |
| Life | `Life-Rewind.dc.html` | Rewind to try the other path |
| Life | `Life-Summary.dc.html` | Life summary with INDEX score and ribbons |
| Play | `Play-Lobby.dc.html` | Same Life room lobby |
| Play | `Play-Live.dc.html` | Live room with rival strip |
| Play | `Play-End.dc.html` | Room results |
| You | `You-Profile.dc.html` | Profile, bank, data sources, settings, credits |
| You | `You-Paywall.dc.html` | Lifeline Plus paywall with "Demo payment" |
| — | `Style.dc.html` | Style guide (reference) |
| — | `Icons.dc.html` | Icon set overview (reference) |
| — | `AppIcon.dc.html` | App icon, 1024 × 1024 |

Ignore these early exploration files: `Main`, `A-Money`, `B-Spec`, `B-Money`, `A2-Spec`, `Card-Colours`, `Money-Home` (a wrapper).

## Flow

- Money home → "Test it" → `Money-Test`. "Why?" → `Money-Why`. "Do this" → confirm (not designed).
- Money home → "Play" on the guess card → `Money-Guess`.
- Life main → "My mortgage offer is ready" → `Life-Event` → age up → `Life-Lesson` → "Rewind and try 5 years" → `Life-Rewind` → back to `Life-Main`.
- Life main → Assets → `Life-Assets`.
- Play lobby → Start → `Play-Live` → end of run → `Play-End`.
- You → Lifeline Plus → `You-Paywall`.

## Design tokens

Colours

| Token | Hex | Use |
|---|---|---|
| paper | #F5F2EA | Screen background |
| surface | #FFFFFF | Cards, sheets, tab bar, Next Move card |
| ink | #16181D | Text, outlines, shadows, main button |
| muted | #4A4F59 | Second-level text |
| rule | #DDD8CC | Dividers inside lists |
| work | #6C8EF5 | Work area |
| home | #FFA94D | Home area |
| money | #3FB57A | Money area, Penny the coin |
| family | #A78BFA | Family area |
| health | #FF7A8A | Health area, "price up" flags |

Type: Bricolage Grotesque 800 (numbers, titles) and Atkinson Hyperlegible 400/700 (body). Google Fonts.
Only 4 sizes: 40 (hero numbers, age), 24 (titles), 17 (body, buttons), 13 (labels).

Spacing: 4 / 8 / 12 / 16 / 20 / 32. Screen side margin 20.

Shape:
- Outline 3px ink on cards, buttons, bars.
- Corners are uneven on purpose (hand-cut look). Example card radius: `22px 30px 20px 28px / 28px 20px 30px 22px`.
- Offset shadow `6px 7px 0 #16181D` on the hero element of a screen only.
- No gradients, glows, sparkles or emoji. No cards inside cards.
- Touch targets 44px minimum. Main buttons 52px tall.

## Icons

- 48 × 48 grid, 4px padding, ink outline, flat fills, at most 2 palette colours.
- Stroke: 3px at 48, 2.75px at 32, 2.5px at 24 (in the 48 grid: stroke-width = px × 48 / size).
- Tab icons: white fill when inactive, colour fill when active (Money green, Life coral, Play lilac, You blue).
- Names: tab-money, tab-life, tab-play, tab-you, home, car, bank, card, savings, pension, cart, subscriptions, bills, budget, goal, investment, debt, job, study, health, family, relationships, activities, travel, pet, happiness, rate-rise, price-rise, job-loss, pay-rise, crash, flood, burglary, baby, wedding, inheritance, boiler, mot-fail, age, rewind, test, why, check, lesson, ribbon, trophy, streak, lock, demo-pay, status-live, status-cached, status-mock, face-baby, face-girl, face-boy, face-teen, face-teen-hijab, face-woman-puff, face-man-beard, face-priya, face-man-glasses, face-blue-hair, face-older-woman, face-older-man.

## Data used

Real (Bank of England, Sep 2026): 5-year fix 4.98%, 2-year fix 5.13%, Bank Rate 3.75%.
- £180,000 over 25 years at 4.98% = £1,050 a month. At 5.13% = £1,066 a month. Difference £190 a year.
- 2022 replay: 2-year fix at 1.20% (£695 a month) in Sep 2021 → 5.91% (£1,150 a month) in Sep 2023. +£455 a month, +£5,460 a year.
- "Test it", rates rise to 5.91% in 2029: 5-year path pays £63,010 over 5 years, 2-year path £66,790 (renews at £1,145). Saving £3,780.

Fake (label "Mock data" on screen): persona Priya Shah, 34, nurse, Leeds. Balances, spending, subscriptions, game stats, rivals, INDEX scores.

## Still to fill in

- 2021 five-year fixed rate and its monthly payment. Shown as `[5-year rate, Sep 2021]` and `[£]` in `Life-Event` and `Life-Rewind`.
- Hackathon name in the credits (`You-Profile`).
- Paywall prices are demo values (£24.99 a year, £2.99 a month).
