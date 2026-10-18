# PENNY_V3_BUILD.md

Source of truth for everything decided on 18 Oct, 03:30 to 05:30: (A) the reseed, (B) the forecast Next Move, (C) onboarding, (D) Penny chat, (E) Learn, (F) the cut, (G) other fixes, (H) order and rules. Replaces the seed parts of DIRECTION_V2.md. Where this file and DIRECTION_V2.md disagree, this file wins. Design reference for B: https://claude.ai/artifact/8epSoKzB7psGvgnnH7h5kn

---

# A. Reseed the 10 sample students

## A1. Rules for every student

1. Keep the 10 names and stories. Rebuild every number.
2. Every income, rent and price figure has a source. Store it per student in `docs/seed_sources.md` and in the sample metadata: figure, value, source URL, date checked. If a figure has no official or survey source, mark it "example within <source> range" and give the range.
3. Statements cover 1 July 2026 to the day before the import. Dates are relative to the import day, so the data is never stale.
4. Location: town and region come from the student card (fix the Manchester bug first).
5. Banks: use the bank named per student below. No student uses Monzo. No "Pots" naming. Savings use the bank's own product name or "Savings".
6. Spending is generated as real transactions:
   - Real UK merchants per category (examples below), at realistic frequencies and amounts.
   - Groceries 2 to 3 times a week, £6 to £35 each. A bigger shop after money arrives.
   - Going out and eating out cluster on Thursday to Saturday nights.
   - A spending spike in the 7 days after a loan or pay arrives.
   - September is higher (freshers, setting up, books). July and August follow each student's summer story.
   - Subscriptions and bills on fixed dates every month.
7. Rent and bills: rent on its due date as one payment. Never count rent twice in a month.
8. Calibrate each student's monthly non-rent spending to their university's average in the National Student Money Survey 2026 (table in A3), adjusted by the profile multiplier given per student. Final check: the September non-rent total must be within ±15% of the target in the table below.
9. Recompute everything derived from the statement after import: habit score, 3 things Penny noticed, budgets and goals, forecast.

## A2. National reference figures (checked 18 Oct 2026)

| Figure | Value | Source |
|---|---|---|
| Average student living costs | £1,146 a month (rent £551, groceries £155, transport £73, bills £68, going out £60, eating out £45, clothes £33) | Save the Student, National Student Money Survey 2026: savethestudent.org/money/student-budgeting/what-do-students-spend-their-money-on.html |
| Average student rent | £575 a month; London £793, Scotland £703, South West £610, Yorkshire £557, North East £557, North West £492, West Midlands £484 | Save the Student, National Student Accommodation Survey 2026: savethestudent.org/money/surveys/national-student-accommodation-survey-2026.html |
| Rent by type | Uni accommodation £641, private landlord £576, living with parents £400 | Same |
| Energy bills when paid separately | £83 a month per student | Same |
| Parents' contribution | £132 a month on average (48% of students get money from parents) | NSMS 2026 |
| Part-time work | 59% of students have a part-time job | NSMS 2026 |
| Minimum wage from 1 Apr 2026 | £12.71 an hour (21+), £10.85 (18 to 20) | gov.uk/government/news/national-living-wage-increases-to-1271-per-hour |
| SAAS 2026/27, young student, household up to £20,999 | Young Students' Bursary £2,000 + loan £9,400 = £11,400 | SAAS (saas.gov.uk); confirm the instalment schedule there |
| Student Finance England 2026/27 maximum loan | £10,830 away from home outside London, £9,118 at home | gov.uk/student-finance/new-fulltime-students (already in the facts table) |

**Research limit:** do not spend time researching or citing anything beyond A2 and A3. Where a figure is not given, choose a realistic value inside the A2/A3 ranges and mark it "example" in `docs/seed_sources.md`. Compute SFE loans, tax and NI with a simple, reasonable method; exact formulas are not needed.

## A3. University non-rent spending, NSMS 2026 (per month)

| University | Total | Groceries | Eating out | Going out | Transport | Bills | Clothes |
|---|---|---|---|---|---|---|---|
| Sheffield | £538 | 142 | 44 | 77 | 90 | 27 | 67 |
| Edinburgh | £637 | 186 | 33 | 67 | 49 | 89 | 23 |
| Manchester | £490 | 151 | 28 | 63 | 45 | 71 | 21 |
| Newcastle | £455 | 188 | 43 | 96 | 15 | 30 | 36 |
| Leeds | £549 | 120 | 55 | 83 | 63 | 44 | 48 |
| Birmingham | £577 | 137 | 49 | 49 | 88 | 43 | 29 |
| Warwick | £429 | 161 | 45 | 80 | 36 | 23 | 24 |
| Exeter | £443 | 125 | 37 | 58 | 47 | 64 | 23 |

## A4. The 10 students

Money amounts are monthly unless stated. "Target" = September non-rent spending.

### 1. Amara Okoye, 19, University of Sheffield (Yorkshire) — the careful saver
- Bank: Nationwide FlexStudent + Nationwide savings.
- Income: SFE maximum away from home outside London, £10,830 a year, 3 termly payments (term starts). University of Sheffield bursary: use the real published amount for her household band (cite it).
- Housing: university halls, about £600 a month equivalent, paid to the university in 3 termly instalments (cite the halls price page).
- Target: £380 (Sheffield £538 × 0.7). Groceries high share, little going out, walks or buses.
- Merchants: Aldi, Tesco Express, Co-op, Stagecoach Yorkshire, Spotify, Greggs.
- Expected forecast: on track to her January loan, with spare money.

### 2. Eilidh Fraser, 19, University of Edinburgh (Scotland) — SAAS, steady
- Bank: Bank of Scotland student account + savings.
- Income: SAAS £9,400 loan + £2,000 Young Students' Bursary, paid monthly per the SAAS schedule. Weekend café job in term: 8 hours × £10.85, paid fortnightly.
- Housing: shared flat in Marchmont, £650 rent on the 1st + £35 share of energy and broadband.
- Target: £560 (Edinburgh £637 × 0.9).
- Merchants: Lidl, Scotmid, Sainsbury's Local, Lothian Buses, Greggs, Pret, EE.
- Expected forecast: on track to her next SAAS payment.

### 3. Priya Patel, 19, University of Manchester, lives at home in Bolton (North West) — the commuter
- Bank: Santander Edge Student + Santander easy-access savings.
- Income: SFE living at home, household income £35,000 (compute and cite). Mum £40 every Friday.
- Housing: pays her parents £150 a month board.
- Target: £330 (Manchester £490 × 0.65, transport high, groceries low: eats at home).
- Merchants: Northern Rail or Bee Network bus (cite the fare), Greggs, Tesco, Boots, Spotify.
- Saving for a first-home deposit (Lifetime ISA question stays valid).
- Expected forecast: on track.

### 4. Jordan Hughes, 20, Newcastle University (North East) — runs short before January
- Bank: HSBC Student Bank Account.
- Income: SFE away from home, household income £30,000 (compute; must be under £10,830). 3 termly payments.
- Housing: shared house in Jesmond, £560 rent + £45 bills.
- Target: £620 (Newcastle £455 × 1.35: going out and takeaways high). September includes a laptop bought on loan day.
- Merchants: Tesco, Greggs, Deliveroo, Nexus Metro, Spoons (JD Wetherspoon), Currys, Apple.
- Expected forecast: running short; money runs out in December, before the January payment.

### 5. Callum Reid, 21, University of Leeds (Yorkshire) — bar job and overdraft
- Bank: NatWest student account with an interest-free arranged overdraft (use and cite NatWest's published student overdraft terms). Balance about −£370.
- Income: reduced SFE loan, household income £60,000 (compute). Bar job: 8 to 16 hours a week × £12.71, paid every Friday.
- Housing: shared house in Hyde Park, £520 rent + £50 bills.
- Target: £650 (Leeds £549 × 1.2: going out and eating out high).
- Merchants: Aldi, Sainsbury's Local, Deliveroo, Uber, First Leeds bus, Spotify, Netflix.
- Expected forecast: running short before his next pay; the overdraft is close to its limit.

### 6. Grace Mensah, 29, University of Birmingham (West Midlands) — mature nursing student
- Bank: Lloyds current account + Lloyds savings.
- Income: SFE maintenance (independent student; compute and cite) + NHS Learning Support Fund (cite amount and schedule) + NHS bank shifts 1 to 2 a month (cite a bank HCA hourly rate).
- Housing: shared house in Moseley, £520 rent + £40 bills.
- Target: £520 (Birmingham £577 × 0.9). Placement travel by bus and train.
- Merchants: Aldi, Lidl, National Express West Midlands, West Midlands Railway, Boots.
- Expected forecast: on track, healthy savings.

### 7. Yutong Chen, 21, University of Warwick (West Midlands) — international student
- Bank: Barclays student account; parents send money through Wise.
- Income: parents about £1,600 a month in yuan, converted at the live rate (Frankfurter). Not working.
- Housing: Unite Students en-suite, Coventry (cite the current Unite price).
- Target: £520 (Warwick £429 × 1.2: Asian supermarket, bubble tea, a flights-home fund).
- Merchants: Tesco, Wing Yip or Hoo Hing, Chatime, National Express Coventry, Wise fees.
- Expected forecast: on track.

### 8. Sam Whitfield, 21, University of Exeter (South West) — final year
- Bank: Starling.
- Income: SFE away from home, household income £45,000 (compute). Summer internship July and August, net pay computed with gov.uk tax and NI rules.
- Housing: shared house, £600 rent + £45 bills.
- Target: £520 (Exeter £443 × 1.15). September includes a trip (flights + hostel).
- Merchants: Co-op, Tesco, Stagecoach South West, Ryanair, Hostelworld, Spotify.
- Expected forecast: on track to January, with spare money.

### 9. Hugo Ashworth, 20, University of Leeds (Yorkshire) — rich, poor habits
- Bank: Barclays + a Klarna balance.
- Income: parents £1,500 on the 1st of each month. No SFE.
- Housing: city-centre studio, £895, bills included.
- Target: £1,000 (Leeds £549 × 1.8: eating out, going out, clothes, Uber, subscriptions, gym).
- Merchants: Deliveroo, Uber, Ole & Steen, ASOS, Klarna, PureGym, Netflix, Amazon Prime.
- Expected forecast: running short before 1 November, despite the highest income.

### 10. Lena Novak, 22, graduate in London — first salary
- Bank: Chase current account + Chase savings.
- Income: £30,000 salary. Monthly net pay computed from gov.uk income tax, employee NI and 5% auto-enrolment pension on qualifying earnings. No student loan repayment yet (repayments start the April after graduation; cite).
- Housing: room in Hackney (cite a London room-rent source), bills included.
- Transport: TfL monthly travelcard for her zones (cite).
- Target: £700.
- Merchants: Sainsbury's, Pret, TfL, Lidl, Spotify, Pure Gym.
- Expected forecast: on track; the "spare money" suggestion uses the Bank of England savings rate.

## A5. Checks after the reseed (add as tests)
1. Each student's September non-rent total is within ±15% of the target.
2. No loan above the official maximum; every funding figure has a stored source.
3. Rent appears once per period; no Monzo; town matches the card.
4. Forecast states: Jordan, Callum and Hugo are "running short"; the other 7 are "on track".
5. Report a table per student: income, rent, target vs actual, forecast state, sources.

---

# B. The new Next Move: the forecast

## B1. The decision
"Will my money last until my next money arrives, and how much can I spend each week?"

## B2. Calculation (deterministic, in the engine)
- Money now = current account balance (savings not counted; overdraft counted as negative).
- Bills before next money = recurring bills and subscriptions due from tomorrow to the day before the next money.
- Buffer = buffer % × (money now − bills). Default 10%. Options 0, 5, 10, 15, 20%. Stored per user; changeable on "The maths" and in You → Settings.
- Days to cover = tomorrow to the day before the next money (today's spending is already in the statement).
- Per day = (money now − bills − buffer) ÷ days. Per week = per day × 7.
- Usual spending = average weekly non-rent, non-bill spending over the last 4 weeks.
- On track if usual ≤ per week. Spare = (per week − usual) × weeks.
- Running short if usual > per week. Run-out date = today + (money now − bills) ÷ usual daily spending.
- Next money = next expected income from the income schedule (loan, bursary, pay, parents, salary), matched to official schedules where they exist.
- Long gaps (over 6 weeks): adjust usual spending with ONS CPI and say so in the breakdown.
- Stress test ("What if prices rose like in 2022?"): rerun with 2022 ONS inflation applied to usual spending.
- One suggestion: if on track and spare > £10, "Put £X spare aside", with the Bank of England easy-access rate. If short, the biggest non-rent category with its weekly amount.

## B3. Screens (match the canvas)
1. Money home, top: the forecast card. Chip (On track / Running short), headline ("You'll make it to 2 November" / "At this pace, you run out on 28 October"), next money line, "You can spend £X a week (about £Y a day)" or "Keep it under £X a week (about £Y a day)", one habit line, the timeline (today, bills, next money, run-out day), buttons "See the maths" and "Ask Penny".
2. Money home, below: "Where your money goes" (pie + top 5 categories, this month so far, "See all spending"), "Due before <date>", "One thing that helps", one line "In your account £X".
3. The maths: 4 steps with sources at each step, the buffer % buttons, the sum, comparison with habits, "See the detailed breakdown", "What if prices rose like in 2022?", "Ask Penny about this".
4. Detailed breakdown: every account, bill, date and week, the exact sum, and the source of each block. Numbers must add up exactly; the card shows rounded values.
5. All spending (the existing "Your money" screen, redesigned): month switch through every statement month, large pie, every category with share and change vs the previous month. Rent and bills listed separately.
6. Category: total, usual monthly amount, bars by week, every transaction, "Ask Penny about <category>".
7. Ask Penny from the forecast opens a new chat with the forecast loaded and "Explain my weekly budget" sent. Penny gets the forecast as a tool.

## B4. Remove
- Old Next Move moves as the main card, "Test it", "Why?" (replaced by "The maths"), "Do this", "In plan", the plan line, the separate weekly budget block, the two balance tiles.
- Guess my spend (all entry points).
- Every "Mock data" / "Sample data" tag. Replace with one line on "Pick your student" and on You → "Your money and data": "These are sample students. UK banks do not give apps like ours access to real accounts without a licence, so Penny runs on sample statements built from real UK figures."
- Student-facing source lists show only: your statement, official facts (gov.uk, SAAS, Student Finance), Bank of England, ONS, Nomis, Octopus Energy, Frankfurter (international students), Bank of England MPC dates.

## B5. Other agreed changes
- Greeting "Hi, <first name>" at all times; the You tab shows the name.
- Floating tab bar with bigger icons and labels, no glass effect.
- Onboarding "How Penny decides" and "Their Next Move" show the forecast and its steps; "What you can do" copy matches the new feature.

---

# C. Onboarding

Order stays: Welcome → Problem → Language → What you can do → Try Penny → Pick your student → Building their profile → View profile → Their profile → How Penny decides → Their Next Move → Start. Back on every screen after Welcome.

1. **Welcome:** headline "Your student money, sorted." Under it, 2 to 3 short lines: who it is for (UK students and graduates), what Penny uses (your statement and live UK data), what you get (one clear answer each month, with the evidence). Fill the empty space; no new screen.
2. **Problem:** keep "One app. Every source. One clear decision." Show two labelled rows: "Your money" (loan, bursary, job, parents, bank, bills) and "UK data" (only the student-facing sources in B4). Less whitespace.
3. **Language:** add the missing Back button (failing UI test). Fix the manual-entry test: manual entry has no Skip.
4. **What you can do:** less whitespace. Rewrite the 5 items for the new feature: See all your money; Know what you can spend each week; See the maths behind it; Ask Penny; Learn and play with friends.
5. **Try Penny:**
   - Opening message (Penny's first bubble, before the user types): "Hi, I'm Penny, your student money guide. Ask me anything about money or uni life: budgets, loans, rent, part-time work, or anything in between. Once you pick a student, I'll use their numbers too, and check every one."
   - Never answer with "I can't see your numbers yet" or any refusal-style opener. Answer the question.
   - **Verifier bug:** general questions fail because the verifier rejects any number not from user data (e.g. library opening hours). In general-knowledge answers, allow general numbers, label the bubble "General knowledge", and keep the strict number check only for numbers about the user's money. Add a test: "How long does Edinburgh uni library stay open?" gets a real answer, not "Penny is unavailable".
   - Remove the "1 Reply" label here.
6. **Pick your student:** larger cards with name, age, uni and city, funding, £ in with dates, housing, one habit line. Add the honesty line from B4. No "Mock data" or "Sample data" tags.
7. **Their profile:** 
   - Spending by category as a **pie chart**.
   - Every block uses the same period and says which ("September" or "October so far"). The chart, "3 things Penny noticed" and subscriptions must agree.
   - Fix the bill named "this payee" (parsing bug).
   - One set of habit names everywhere (profile and You tab): Saving, Safety cushion, Steady spending, Needs before wants, Subscriptions in check, Low debt pressure.
8. **How Penny decides:** show the forecast steps (B2) with real numbers and their sources: money now, bills before next money, buffer, next money, then the result. No Land Registry. Less whitespace.
9. **Their Next Move:** the forecast card (B3.1).

# D. Penny chat

1. **Double bubble bug:** the streaming bubble and the final bubble both stay on screen and overlap. Show one bubble per answer. The header labels also overlap ("Checked with your data" over "Checked against official sources"); show one label.
2. **New chat** button in the Penny header.
3. **Past chats:** move "Earlier chats" out of the chat into a "Past chats" button in the header that opens its own screen. Remove duplicate threads (e.g. "Prices creep up" twice).
4. **Context:** Ask Penny from a lesson asks about the **current card**, not the whole lesson. Ask Penny from the forecast sends "Explain my weekly budget" with the forecast loaded.
5. Penny link buttons ("See the maths", "Why this move?") open the right screen, not just the Money tab (map gap 4.2).
6. Keep answers short: 1 to 3 bubbles.

# E. Learn

1. **No locks.** Every lesson is open. The path still shows the order. Done lessons keep a tick at full colour (never greyed out). The dots between lessons fill in when lessons are done in order.
2. Less whitespace on each card.
3. "The real number": add one line under each number, "Why this matters to you: ...", tied to the lesson topic.
4. Progress bar segments match the number of cards ("Card 1 of 3" = 3 segments + quiz).
5. You tab: replace "Concepts learned 0/50" with "Lessons X/48"; tapping it opens Learn.
6. Homeowner lessons stay removed.

# F. The cut (hide entry points behind one flag; keep code and tests)

1. Guess my spend: remove every entry point.
2. Full Life game (Choose a life, Job/Assets/People/Activities sheets, Rewind, Life summary, "Your real decision"), Challenges, Same Decision, old Concepts screens, Collection: hidden.
3. "Real-life decision" (mortgage) cover in the old Why?: removed with Why?.
4. Play tab = "Play with friends" (Quick Life) + "Learn". Keep Money Quiz and Circles reachable inside Play with friends for now.
5. Game picker: "Quick Life" is the first option. Tapping it opens the 5 Quick Life students as cards; one tap picks a student; the year is preset; then Start. Other games below it. Joining a Quick Life room counts as ready: no "I'm ready" step; the host's Start turns on as soon as 2 or more players are in the lobby. The lobby QR code opens the app straight into the lobby when scanned with the iPhone camera.
6. Debug menu and Playground not reachable in Release builds; the phones run Release.

# G. Other fixes

1. Greeting "Hi, <first name>" at every time of day. The You tab header shows the name, not "You".
2. Floating tab bar: bigger icons and labels, no glass effect (see canvas). It is the one app-wide tab bar for Money, Penny, Play and You. Every scrolling screen has bottom padding so the last item is never hidden behind it. The Penny chat input sits above the bar. Full-screen covers keep hiding the bar. (Must-have: right after B1-B3.)
3. Net worth / Your money: remove all Monzo and Trading212 leftovers (account names, source rows). Do not show the same amount twice ("Net worth" and "In your account" both £1,249). Confirm in the report that no teammate's real data is anywhere in the seed or on the server.
4. Data source rows: no "Mock data" labels; cut sources not listed.
5. Credits line: no "mock data".

# H. Order and rules

1. Order: location bug → A (reseed) → B1–B3 (forecast engine and main screens) → G2 (floating tab bar) → C5 (Try Penny verifier) + D1 (double bubble) → B4 removals + F (cut) + G → C (rest of onboarding) → D (rest) → E.
2. Parallel workers by area; one owner per file; boss routes.
3. Commit small, by feature, to the wip branch; push after each verified commit. Merge to main only after the final verifier run.
4. One full verifier run on the final build before 09:30: fresh account, all 10 students imported, forecast states match A5, onboarding end to end, Quick Life with 2 accounts.
5. Install on both phones as soon as A + B1–B3 pass, then again after the final run.
6. Everything complete by 10:00 (user, 06:05). From 09:00 fixes only. 09:15: final verifier run on the final build. 09:45: merge to main, install on all phones. 10:00: done, main green, STATUS.md complete.
