# Seed audit: the 10 sample students

Date: 18 Oct 2026, 04:30. Read-only audit. Source: the live API (`https://api-production-15615.up.railway.app`) after `POST /v1/samples/{id}/import` on a fresh demo account per student, plus `tools/gen_statements.py` (the generator of the sample statements). Statement period ends 16 Oct 2026.

All amounts come from the generated statements. They are sample data (`meta.label = "Sample data"`), not real people.

## Summary of findings

- **Funding and rent provenance:** `tools/gen_statements.py` contains no source URL or citation for any funding or rent figure. Every funding and rent figure below is therefore marked **invented**. Where the facts table (`lifeline_engine/rules.py`) holds a checked official value, the provenance column adds a plausibility note.
- **Months:** October is a part month (1 to 16 Oct). Spending by category below uses **September 2026**, the last full month. The October total is given for reference.
- **Location bug (all 10 students):** every imported profile has town Manchester and region north-west, whatever the card says (Edinburgh, Newcastle, London and others). Effects: the Life game, Penny, regional pay and rent data, and the Guess my spend weather all use Manchester. The Scottish student is placed in England. Cause not yet traced (read-only audit).
- **Mismatches** between the student card and the server profile:

- **Amara Okoye (scholarship)**: card city Sheffield, profile town Manchester (region north-west). The Life game and Penny use the profile town.
- **Eilidh Fraser (scottish)**: card city Edinburgh, profile town Manchester (region north-west). The Life game and Penny use the profile town.
- **Priya Patel (commuter)**: card city Bolton, profile town Manchester (region north-west). The Life game and Penny use the profile town.
- **Jordan Hughes (loan_england)**: card city Newcastle, profile town Manchester (region north-west). The Life game and Penny use the profile town.
- **Callum Reid (working)**: card city Leeds, profile town Manchester (region north-west). The Life game and Penny use the profile town.
- **Grace Mensah (mature)**: card city Birmingham, profile town Manchester (region north-west). The Life game and Penny use the profile town.
- **Yutong Chen (international)**: card city Coventry, profile town Manchester (region north-west). The Life game and Penny use the profile town.
- **Sam Whitfield (final_year)**: card city Exeter, profile town Manchester (region north-west). The Life game and Penny use the profile town.
- **Hugo Ashworth (rich)**: card city Leeds, profile town Manchester (region north-west). The Life game and Penny use the profile town.
- **Lena Novak (graduate)**: card city London, profile town Manchester (region north-west). The Life game and Penny use the profile town.

## Amara Okoye (scholarship)

| Field | Value |
|---|---|
| Name | Amara Okoye |
| Age | 19 (profile age 19) |
| Uni and city (card) | University of Sheffield, Sheffield |
| Town and region (profile) | Manchester, north-west |
| Funding label | Scholarship + bursary |
| Housing (card) | Halls, paid by the scholarship |
| Rent a month (profile) | - |
| Habit line | Not counting rent and bills, spends most on food shopping; saved £180 in 3 months |
| Balance (16 Oct) | £1,249.16 |
| Net worth | £1,249.16 |
| Accounts | Monzo Current Account (current) £919.16; Monzo Pots (savings) £330.00 |
| Savings (profile) | £330.00 |
| Months of cover | 7.5 |
| Annual income (profile) | £5,040.00 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| bursary_university_of_sheffield | bursary | £140.00 | monthly | 2026-08-17, 2026-09-15, 2026-10-15, 2026-11-16 | 2026-11-16 | - | invented (no source in generator) |
| scholarship_university_of_sheffield | scholarship | £280.00 | monthly | 2026-08-03, 2026-09-01, 2026-10-01, 2026-11-02 | 2026-11-02 | - | invented (no source in generator) |
| card: Scholarship | - | £280.00 | per month | 1st of each month | - | Scholarship | invented (no source in generator) |
| card: University bursary | - | £140.00 | per month | 15th of each month | - | University bursary | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £165.80; October to the 16th: £57.94)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Groceries | £91.16 | 55.0% | 6 |
| Education | £24.99 | 15.1% | 1 |
| Eating out | £17.86 | 10.8% | 4 |
| Transport | £15.80 | 9.5% | 3 |
| Bills | £10.00 | 6.0% | 1 |
| Subscriptions | £5.99 | 3.6% | 1 |

**Bills, next 30 days** (total £15.99)

| Name | Kind | Amount | Due |
|---|---|---|---|
| giffgaff | bill | £10.00 | 2026-11-05 |
| Spotify | subscription | £5.99 | 2026-11-09 |

**Subscriptions** (1 subscriptions, £5.99 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| Spotify | £5.99 | monthly | 2026-11-09 |

**Debts**

None.

**Budgets and savings goals (created on import)**

- Budget: Groceries £100.00 a month, spent £23.17 in October (ok).
- Goal: Rainy day pot, target £500.00, saved £330.00, by 2027-03-31.

**Habit score:** 82 of 100. Parts: savings_rate 100, months_of_cover 100, spend_stability 36, discretionary_share 81, subscription_creep 76, debt_pressure 100.

**Next Move** (options compared: 2)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | weekly_budget | Move £822 you will not need into savings | At your usual pace you have £822 spare before your scholarship payment on 2 November | Medium confidence: based on your last 4 weeks of spending |
| Runner-up | build_emergency_fund | Keep your safety net topped up | We found no bill, rate or debt that needs action now | No rating: nothing in your data needs action now |

**3 things Penny noticed**

- You spend £6 a month on 1 subscription.
- Your cash and savings cover 7.5 months of spending.
- Not counting rent and bills, you spent the most on groceries last month: £91.

---

## Eilidh Fraser (scottish)

| Field | Value |
|---|---|
| Name | Eilidh Fraser |
| Age | 19 (profile age 19) |
| Uni and city (card) | University of Edinburgh, Edinburgh |
| Town and region (profile) | Manchester, north-west |
| Funding label | SAAS + bursary |
| Housing (card) | Shared flat in Marchmont, £540 a month |
| Rent a month (profile) | £540.00 |
| Habit line | Not counting rent and bills, spends most on food shopping; saved £300 in 3 months |
| Balance (16 Oct) | £1,397.62 |
| Net worth | £1,397.62 |
| Accounts | Monzo Current Account (current) £1,097.62; Monzo Pots (savings) £300.00 |
| Savings (profile) | £300.00 |
| Months of cover | 2.0 |
| Annual income (profile) | £11,038.25 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| bursary_student_loans_company | bursary | £166.00 | monthly | 2026-09-18, 2026-10-16, 2026-11-16, 2026-12-16 | 2026-11-16 | - | invented (no source in generator) |
| part_time_job_fringe_bars_ltd | part_time_job | £226.25 | one_off | 2026-08-07, 2026-08-14, 2026-08-21, 2026-08-28 (+2 earlier) | - | - | invented (no source in generator) |
| maintenance_loan_student_loans_company | maintenance_loan | £735.00 | monthly | 2026-09-18, 2026-10-16, 2026-11-16, 2026-12-16 | 2026-11-16 | - | invented (no source in generator). Plausibility: England 2026/27 maximum Maintenance Loan: £9,118 at home, £10,830 away outside London, £14,135 in London (gov.uk/student-finance/new-fulltime-students, checked 18 Oct 2026). |
| card: SAAS loan | - | £735.00 | per month | Mid-month (18 Sep, 16 Oct) | - | SAAS loan | invented (no source in generator) |
| card: Young Students' Bursary | - | £166.00 | per month | Same day as the SAAS loan | - | Young Students' Bursary | invented (no source in generator) |
| card: Fringe bar job | - | £214.79 | per week | Fridays, 24 Jul to 28 Aug, pay varies | - | Fringe bar job | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £678.32; October to the 16th: £698.35)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Housing | £540.00 | 79.6% | 1 |
| Groceries | £121.69 | 17.9% | 9 |
| Bills | £8.00 | 1.2% | 1 |
| Subscriptions | £5.99 | 0.9% | 1 |
| Eating out | £2.64 | 0.4% | 1 |

**Bills, next 30 days** (total £553.99)

| Name | Kind | Amount | Due |
|---|---|---|---|
| Spotify | subscription | £5.99 | 2026-10-20 |
| Marchmont Lettings | rent | £540.00 | 2026-11-01 |
| giffgaff | bill | £8.00 | 2026-11-05 |

**Subscriptions** (1 subscriptions, £5.99 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| Spotify | £5.99 | monthly | 2026-10-20 |

**Debts**

None.

**Budgets and savings goals (created on import)**

- Budget: Groceries £130.00 a month, spent £133.96 in October (over).
- Goal: Rainy day pot, target £600.00, saved £300.00, by 2027-05-31.

**Habit score:** 84 of 100. Parts: savings_rate 100, months_of_cover 66, spend_stability 46, discretionary_share 98, subscription_creep 94, debt_pressure 100.

**Next Move** (options compared: 1)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | build_emergency_fund | Build a safety net of £2,115 | With 3 months of costs put aside, a surprise bill does not go on a card | Low confidence: mixed results in 5 similar past years in UK data |

**3 things Penny noticed**

- You spend £6 a month on 1 subscription.
- Your cash and savings cover 2 months of spending.
- Not counting rent and bills, you spent the most on groceries last month: £122.

---

## Priya Patel (commuter)

| Field | Value |
|---|---|
| Name | Priya Patel |
| Age | 19 (profile age 19) |
| Uni and city (card) | University of Manchester, Bolton |
| Town and region (profile) | Manchester, north-west |
| Funding label | Access grant + family |
| Housing (card) | Lives at home with family |
| Rent a month (profile) | - |
| Habit line | Not counting rent and bills, spends most on travel; saved £725 in 3 months |
| Balance (16 Oct) | £2,549.97 |
| Net worth | £2,549.97 |
| Accounts | Monzo Current Account (current) £1,004.97; Monzo Pots (savings) £1,545.00 |
| Savings (profile) | £1,545.00 |
| Months of cover | 29.9 |
| Annual income (profile) | £5,080.00 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| family_s_patel | family | £40.00 | weekly | 2026-09-25, 2026-10-02, 2026-10-09, 2026-10-16 (+10 earlier) | 2026-10-23 | - | invented (no source in generator) |
| grant_university_of_manchester | grant | £1,000.00 | termly | 2026-10-05, 2027-02-01, 2027-04-26 | 2027-02-01 | - | invented (no source in generator) |
| card: Access grant | - | £1,000.00 | per term | 5 Oct, 1 Feb, 26 Apr | - | Access grant | invented (no source in generator) |
| card: Mum | - | £40.00 | per week | Every Friday | - | Mum | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £114.84; October to the 16th: £56.69)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Transport | £69.90 | 60.9% | 9 |
| Health | £14.05 | 12.2% | 2 |
| Eating out | £12.71 | 11.1% | 5 |
| Subscriptions | £10.48 | 9.1% | 2 |
| Groceries | £7.70 | 6.7% | 2 |

**Bills, next 30 days** (total £10.48)

| Name | Kind | Amount | Due |
|---|---|---|---|
| Amazon Prime | subscription | £4.49 | 2026-10-19 |
| Spotify | subscription | £5.99 | 2026-11-03 |

**Subscriptions** (2 subscriptions, £10.48 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| Spotify | £5.99 | monthly | 2026-11-03 |
| Amazon Prime | £4.49 | monthly | 2026-10-19 |

**Debts**

None.

**Budgets and savings goals (created on import)**

- Budget: Eating out £15.00 a month, spent £10.20 in October (ok).
- Goal: Deposit for a flat near uni, target £2,000.00, saved £1,545.00, by 2027-06-30.

**Habit score:** 71 of 100. Parts: savings_rate 100, months_of_cover 100, spend_stability 54, discretionary_share 52, subscription_creep 18, debt_pressure 100.

**Next Move** (options compared: 2)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | lifetime_isa | Put £1,289 in a Lifetime ISA | The government adds 25% to what you pay in, so £1,289 gets a £322 bonus | High confidence: the bonus is a fixed government rule |
| Runner-up | move_savings | Move your savings to a better rate | Other easy-access accounts pay more interest than yours | Medium confidence: based on 5 similar past periods in UK data |

**3 things Penny noticed**

- You spend £10 a month on 2 subscriptions.
- Your cash and savings cover 29.9 months of spending.
- Not counting rent and bills, you spent the most on transport last month: £70.

---

## Jordan Hughes (loan_england)

| Field | Value |
|---|---|
| Name | Jordan Hughes |
| Age | 20 (profile age 20) |
| Uni and city (card) | Newcastle University, Newcastle |
| Town and region (profile) | Manchester, north-west |
| Funding label | Student Finance England |
| Housing (card) | Shared house in Jesmond, £495 a month |
| Rent a month (profile) | £495.00 |
| Habit line | Not counting rent and bills, spends most on shopping; no savings yet |
| Balance (16 Oct) | £2,003.63 |
| Net worth | £2,003.63 |
| Accounts | Monzo Current Account (current) £2,003.63 |
| Savings (profile) | £0.00 |
| Months of cover | 2.0 |
| Annual income (profile) | £10,836.00 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| maintenance_loan_student_loans_company | maintenance_loan | £3,612.00 | termly | 2026-09-28, 2027-01-18, 2027-04-26 | 2027-01-18 | - | invented (no source in generator). Plausibility: England 2026/27 maximum Maintenance Loan: £9,118 at home, £10,830 away outside London, £14,135 in London (gov.uk/student-finance/new-fulltime-students, checked 18 Oct 2026). |
| card: Maintenance loan | - | £3,612.00 | per term | 28 Sep, 18 Jan, 26 Apr | - | Maintenance loan | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £1,334.38; October to the 16th: £1,090.27)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Shopping | £548.99 | 41.1% | 2 |
| Housing | £495.00 | 37.1% | 1 |
| Eating out | £155.73 | 11.7% | 11 |
| Bills | £55.00 | 4.1% | 2 |
| Groceries | £54.19 | 4.1% | 6 |
| Subscriptions | £16.47 | 1.2% | 3 |
| Transport | £9.00 | 0.7% | 3 |

**Bills, next 30 days** (total £566.47)

| Name | Kind | Amount | Due |
|---|---|---|---|
| Netflix | subscription | £5.99 | 2026-10-21 |
| Jesmond Student Lets | rent | £495.00 | 2026-11-01 |
| Kieran Walsh | bill | £45.00 | 2026-11-06 |
| Amazon Prime | subscription | £4.49 | 2026-11-09 |
| Smarty | bill | £10.00 | 2026-11-12 |
| Spotify | subscription | £5.99 | 2026-11-14 |

**Subscriptions** (3 subscriptions, £16.47 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| Netflix | £5.99 | monthly | 2026-10-21 |
| Spotify | £5.99 | monthly | 2026-11-14 |
| Amazon Prime | £4.49 | monthly | 2026-11-09 |

**Debts**

None.

**Budgets and savings goals (created on import)**

- Budget: Eating out £100.00 a month, spent £232.65 in October (over).
- Goal: Summer InterRail, target £400.00, saved £0.00, by 2027-06-01.

**Habit score:** 46 of 100. Parts: savings_rate 0, months_of_cover 66, spend_stability 0, discretionary_share 24, subscription_creep 89, debt_pressure 100.

**Next Move** (options compared: 3)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | weekly_budget | Spend up to £23 a week until 18 January | At your usual pace, your money runs out before your student loan payment on 18 January | Medium confidence: based on your last 4 weeks of spending |
| Runner-up | cut_budget | Cut eating out to £63 a month | You spent £93 more than usual on eating out last month | Low confidence: only 2 months of spending so far |
| Runner-up | build_emergency_fund | Build a safety net of £3,039 | With 3 months of costs put aside, a surprise bill does not go on a card | Low confidence: mixed results in 5 similar past years in UK data |

**3 things Penny noticed**

- You spend £16 a month on 3 subscriptions.
- Your cash and savings cover 2 months of spending.
- Not counting rent and bills, you spent the most on shopping last month: £549.

---

## Callum Reid (working)

| Field | Value |
|---|---|
| Name | Callum Reid |
| Age | 21 (profile age 21) |
| Uni and city (card) | University of Leeds, Leeds |
| Town and region (profile) | Manchester, north-west |
| Funding label | Student Finance England + bar job |
| Housing (card) | Shared house in Hyde Park, £460 a month |
| Rent a month (profile) | £460.00 |
| Habit line | Not counting rent and bills, spends most on shopping; often in the overdraft |
| Balance (16 Oct) | -£371.03 |
| Net worth | -£371.03 |
| Accounts | Monzo Current Account (current) -£371.03 |
| Savings (profile) | £0.00 |
| Months of cover | 0.0 |
| Annual income (profile) | £10,991.76 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| part_time_job_jd_wetherspoon | part_time_job | £116.88 | weekly | 2026-09-25, 2026-10-02, 2026-10-09, 2026-10-16 (+10 earlier) | 2026-10-23 | - | invented (no source in generator) |
| maintenance_loan_student_loans_company | maintenance_loan | £1,638.00 | termly | 2026-09-28, 2027-01-18, 2027-04-26 | 2027-01-18 | - | invented (no source in generator). Plausibility: England 2026/27 maximum Maintenance Loan: £9,118 at home, £10,830 away outside London, £14,135 in London (gov.uk/student-finance/new-fulltime-students, checked 18 Oct 2026). |
| card: Maintenance loan | - | £1,638.00 | per term | 28 Sep, 18 Jan, 26 Apr | - | Maintenance loan | invented (no source in generator) |
| card: Bar job | - | £85.67 | per week | Every Friday, pay varies | - | Bar job | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £1,289.18; October to the 16th: £1,418.85)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Housing | £920.00 | 71.4% | 2 |
| Eating out | £147.95 | 11.5% | 22 |
| Groceries | £133.21 | 10.3% | 12 |
| Bills | £46.00 | 3.6% | 2 |
| Transport | £27.00 | 2.1% | 9 |
| Subscriptions | £11.98 | 0.9% | 2 |
| Fees | £3.04 | 0.2% | 1 |

**Bills, next 30 days** (total £517.98)

| Name | Kind | Amount | Due |
|---|---|---|---|
| Netflix | subscription | £5.99 | 2026-10-17 |
| Headrow Lettings | rent | £460.00 | 2026-11-01 |
| Ellie Shaw | bill | £38.00 | 2026-11-05 |
| Smarty | bill | £8.00 | 2026-11-06 |
| Spotify | subscription | £5.99 | 2026-11-12 |

**Subscriptions** (2 subscriptions, £11.98 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| Netflix | £5.99 | monthly | 2026-10-17 |
| Spotify | £5.99 | monthly | 2026-11-12 |

**Debts**

| Kind | Balance | Rate | Free limit / due |
|---|---|---|---|
| overdraft | £371.03 | 39.0% | 0.0 |

**Budgets and savings goals (created on import)**

- Budget: Eating out £120.00 a month, spent £105.60 in October (near).
- Goal: Out of the overdraft buffer, target £400.00, saved £0.00, by 2027-04-30.

**Habit score:** 42 of 100. Parts: savings_rate 0, months_of_cover 0, spend_stability 0, discretionary_share 70, subscription_creep 93, debt_pressure 88.

**Next Move** (options compared: 3)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | weekly_budget | Plan for £131 you are missing before 23 October | Your bills before your pay on 23 October take all your cash | Medium confidence: based on your last 4 weeks of spending |
| Runner-up | pay_off_debt | Pay £100 a month extra to your overdraft | Paying down your overdraft cuts the interest you pay | Medium confidence: based on 5 similar past years in UK data |
| Runner-up | build_emergency_fund | Build a safety net of £3,196 | With 3 months of costs put aside, a surprise bill does not go on a card | Low confidence: mixed results in 5 similar past years in UK data |

**3 things Penny noticed**

- You spend £12 a month on 2 subscriptions.
- You are £371 in your overdraft, so your cash covers 0 months of spending.
- Not counting rent and bills, you spent the most on eating out last month: £148.

---

## Grace Mensah (mature)

| Field | Value |
|---|---|
| Name | Grace Mensah |
| Age | 29 (profile age 29) |
| Uni and city (card) | University of Birmingham, Birmingham |
| Town and region (profile) | Manchester, north-west |
| Funding label | Student Finance England + NHS grant |
| Housing (card) | Shared house in Moseley, £625 a month |
| Rent a month (profile) | £625.00 |
| Habit line | Not counting rent and bills, spends most on food shopping; saved £960 in 3 months |
| Balance (16 Oct) | £4,679.48 |
| Net worth | £4,679.48 |
| Accounts | Monzo Current Account (current) £2,319.48; Monzo Pots (savings) £2,360.00 |
| Savings (profile) | £2,360.00 |
| Months of cover | 5.4 |
| Annual income (profile) | £16,533.00 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| grant_nhsbsa | grant | £416.67 | monthly | 2026-07-20, 2026-08-20, 2026-09-21, 2026-11-20 | 2026-11-20 | - | invented (no source in generator) |
| part_time_job_nhs_professionals | part_time_job | £236.08 | monthly | 2026-08-05, 2026-09-07, 2026-10-05, 2026-11-05 | 2026-11-05 | - | invented (no source in generator) |
| maintenance_loan_student_loans_company | maintenance_loan | £2,900.00 | termly | 2026-09-28, 2027-01-18, 2027-04-26 | 2027-01-18 | - | invented (no source in generator). Plausibility: England 2026/27 maximum Maintenance Loan: £9,118 at home, £10,830 away outside London, £14,135 in London (gov.uk/student-finance/new-fulltime-students, checked 18 Oct 2026). |
| card: Maintenance loan | - | £2,900.00 | per term | 28 Sep, 18 Jan, 26 Apr | - | Maintenance loan | invented (no source in generator) |
| card: NHS Learning Support Fund | - | £416.67 | per month | Around the 20th each month | - | NHS Learning Support Fund | invented (no source in generator) |
| card: NHS bank shifts | - | £236.08 | per month | Around the 5th each month, pay varies | - | NHS bank shifts | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £884.77; October to the 16th: £741.50)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Housing | £625.00 | 70.6% | 1 |
| Groceries | £143.25 | 16.2% | 6 |
| Bills | £60.00 | 6.8% | 2 |
| Transport | £38.00 | 4.3% | 19 |
| Eating out | £12.53 | 1.4% | 4 |
| Subscriptions | £5.99 | 0.7% | 1 |

**Bills, next 30 days** (total £690.99)

| Name | Kind | Amount | Due |
|---|---|---|---|
| Tesco Mobile | bill | £12.00 | 2026-10-17 |
| Netflix | subscription | £5.99 | 2026-10-24 |
| Moseley Lettings | rent | £625.00 | 2026-11-01 |
| Octopus Energy | bill | £48.00 | 2026-11-12 |

**Subscriptions** (1 subscriptions, £5.99 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| Netflix | £5.99 | monthly | 2026-10-24 |

**Debts**

None.

**Budgets and savings goals (created on import)**

- Budget: Groceries £110.00 a month, spent £42.52 in October (ok).
- Goal: Emergency fund, target £3,000.00, saved £2,360.00, by 2027-06-30.

**Habit score:** 92 of 100. Parts: savings_rate 100, months_of_cover 100, spend_stability 61, discretionary_share 98, subscription_creep 95, debt_pressure 100.

**Next Move** (options compared: 2)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | cut_budget | Cut groceries to £97 a month | You spent £46 more than usual on groceries last month | Low confidence: only 2 months of spending so far |
| Runner-up | move_savings | Move your savings to a better rate | Other easy-access accounts pay more interest than yours | Medium confidence: based on 5 similar past periods in UK data |

**3 things Penny noticed**

- You spend £6 a month on 1 subscription.
- Your cash and savings cover 5.4 months of spending.
- Not counting rent and bills, you spent the most on groceries last month: £143.

---

## Yutong Chen (international)

| Field | Value |
|---|---|
| Name | Yutong Chen |
| Age | 21 (profile age 21) |
| Uni and city (card) | University of Warwick, Coventry |
| Town and region (profile) | Manchester, north-west |
| Funding label | Parents |
| Housing (card) | Unite Students room, £790 a month |
| Rent a month (profile) | £790.00 |
| Habit line | Not counting rent and bills, spends most on eating out; no savings yet |
| Balance (16 Oct) | £3,854.54 |
| Net worth | £3,854.54 |
| Accounts | Monzo Current Account (current) £3,854.54 |
| Savings (profile) | £0.00 |
| Months of cover | 2.8 |
| Annual income (profile) | £18,580.80 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| family_wise | family | £1,548.40 | monthly | 2026-08-03, 2026-09-03, 2026-10-05, 2026-11-03 (+1 earlier) | 2026-11-03 | - | invented (no source in generator) |
| card: Parents (by Wise) | - | £1,569.40 | per month | Early each month, latest 5 Oct; moves with the yuan | - | Parents (by Wise) | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £1,400.51; October to the 16th: £1,013.12)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Housing | £790.00 | 56.4% | 1 |
| Eating out | £247.89 | 17.7% | 18 |
| Groceries | £201.71 | 14.4% | 9 |
| Shopping | £80.16 | 5.7% | 2 |
| Subscriptions | £38.96 | 2.8% | 4 |
| Transport | £21.79 | 1.6% | 2 |
| Bills | £20.00 | 1.4% | 1 |

**Bills, next 30 days** (total £848.96)

| Name | Kind | Amount | Due |
|---|---|---|---|
| Disney Plus | subscription | £9.99 | 2026-10-26 |
| Apple | subscription | £2.99 | 2026-11-02 |
| Unite Students | rent | £790.00 | 2026-11-05 |
| this payee | bill | £20.00 | 2026-11-08 |
| Spotify | subscription | £12.99 | 2026-11-11 |
| Netflix | subscription | £12.99 | 2026-11-15 |

**Subscriptions** (4 subscriptions, £38.96 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| Netflix | £12.99 | monthly | 2026-11-15 |
| Spotify | £12.99 | monthly | 2026-11-11 |
| Disney Plus | £9.99 | monthly | 2026-10-26 |
| Apple | £2.99 | monthly | 2026-11-02 |

**Debts**

None.

**Budgets and savings goals (created on import)**

- Budget: Eating out £180.00 a month, spent £74.77 in October (ok).
- Goal: Flight home at Christmas, target £650.00, saved £0.00, by 2026-12-10.

**Habit score:** 74 of 100. Parts: savings_rate 57, months_of_cover 94, spend_stability 59, discretionary_share 50, subscription_creep 81, debt_pressure 100.

**Next Move** (options compared: 2)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | cut_budget | Cut groceries to £115 a month | You spent £86 more than usual on groceries last month | Low confidence: only 2 months of spending so far |
| Runner-up | build_emergency_fund | Build a safety net of £4,117 | With 3 months of costs put aside, a surprise bill does not go on a card | Low confidence: mixed results in 5 similar past years in UK data |

**3 things Penny noticed**

- You spend £39 a month on 4 subscriptions.
- Your cash and savings cover 2.8 months of spending.
- Not counting rent and bills, you spent the most on eating out last month: £248.

---

## Sam Whitfield (final_year)

| Field | Value |
|---|---|
| Name | Sam Whitfield |
| Age | 21 (profile age 21) |
| Uni and city (card) | University of Exeter, Exeter |
| Town and region (profile) | Manchester, north-west |
| Funding label | Student Finance England + internship |
| Housing (card) | Shared house in Exeter, £560 a month |
| Rent a month (profile) | £560.00 |
| Habit line | Not counting rent and bills, spends most on holidays; saved £1,500 in 3 months |
| Balance (16 Oct) | £2,917.54 |
| Net worth | £2,917.54 |
| Accounts | Monzo Current Account (current) £2,917.54 |
| Savings (profile) | £0.00 |
| Months of cover | 3.2 |
| Annual income (profile) | £9,035.00 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| salary_northbridge_capital_ltd | salary | £1,985.00 | one_off | 2026-07-31, 2026-08-28 | - | - | invented (no source in generator) |
| maintenance_loan_student_loans_company | maintenance_loan | £2,350.00 | termly | 2026-09-28, 2027-01-18, 2027-04-26 | 2027-01-18 | - | invented (no source in generator). Plausibility: England 2026/27 maximum Maintenance Loan: £9,118 at home, £10,830 away outside London, £14,135 in London (gov.uk/student-finance/new-fulltime-students, checked 18 Oct 2026). |
| card: Summer internship | - | £1,985.00 | per month | 31 Jul and 28 Aug only | - | Summer internship | invented (no source in generator) |
| card: Maintenance loan | - | £2,350.00 | per term | 28 Sep, 18 Jan, 26 Apr | - | Maintenance loan | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £1,396.24; October to the 16th: £616.59)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Housing | £560.00 | 40.1% | 1 |
| Travel | £498.00 | 35.7% | 2 |
| Eating out | £213.73 | 15.3% | 11 |
| Entertainment | £54.45 | 3.9% | 2 |
| Groceries | £50.07 | 3.6% | 3 |
| Bills | £10.00 | 0.7% | 1 |
| Subscriptions | £5.99 | 0.4% | 1 |
| Transport | £4.00 | 0.3% | 2 |

**Bills, next 30 days** (total £570.00)

| Name | Kind | Amount | Due |
|---|---|---|---|
| VOXI | bill | £10.00 | 2026-10-22 |
| Exeter Student Lets | rent | £560.00 | 2026-11-01 |

**Subscriptions** (1 subscriptions, £5.99 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| Spotify | £5.99 | monthly | 2026-11-16 |

**Debts**

None.

**Budgets and savings goals (created on import)**

- Budget: Eating out £100.00 a month, spent £30.77 in October (ok).
- Goal: Deposit for a flat after uni, target £1,000.00, saved £0.00, by 2027-08-31.

**Habit score:** 53 of 100. Parts: savings_rate 0, months_of_cover 100, spend_stability 0, discretionary_share 20, subscription_creep 96, debt_pressure 100.

**Next Move** (options compared: 2)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | weekly_budget | Move £469 you will not need into savings | At your usual pace you have £469 spare before your student loan payment on 18 January | Medium confidence: based on your last 4 weeks of spending |
| Runner-up | build_emergency_fund | Keep your safety net topped up | We found no bill, rate or debt that needs action now | No rating: nothing in your data needs action now |

**3 things Penny noticed**

- You spend £6 a month on 1 subscription.
- Your cash and savings cover 3.2 months of spending.
- Not counting rent and bills, you spent the most on travel last month: £498.

---

## Hugo Ashworth (rich)

| Field | Value |
|---|---|
| Name | Hugo Ashworth |
| Age | 20 (profile age 20) |
| Uni and city (card) | University of Leeds, Leeds |
| Town and region (profile) | Manchester, north-west |
| Funding label | Parents |
| Housing (card) | City flat, £895 a month |
| Rent a month (profile) | £895.00 |
| Habit line | Not counting rent and bills, spends most on eating out; spreads payments with Klarna |
| Balance (16 Oct) | £882.81 |
| Net worth | £744.81 |
| Accounts | Monzo Current Account (current) £882.81; Buy now, pay later (credit) -£138.00 |
| Savings (profile) | £0.00 |
| Months of cover | 0.4 |
| Annual income (profile) | £25,500.00 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| family_j_ashworth | family | £125.00 | monthly | 2026-09-12, 2026-10-10 | 2026-11-10 | - | invented (no source in generator) |
| family_r_ashworth | family | £2,000.00 | monthly | 2026-08-03, 2026-09-01, 2026-10-01, 2026-11-02 | 2026-11-02 | - | invented (no source in generator) |
| card: Parents | - | £2,000.00 | per month | 1st of each month | - | Parents | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £2,138.30; October to the 16th: £1,398.38)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Housing | £895.00 | 41.9% | 1 |
| Eating out | £557.26 | 26.1% | 37 |
| Groceries | £214.38 | 10.0% | 15 |
| Shopping | £154.99 | 7.2% | 3 |
| Transport | £139.04 | 6.5% | 13 |
| Subscriptions | £113.92 | 5.3% | 8 |
| Entertainment | £63.71 | 3.0% | 2 |

**Bills, next 30 days** (total £1,008.92)

| Name | Kind | Amount | Due |
|---|---|---|---|
| Xbox | subscription | £22.99 | 2026-10-18 |
| Amazon Prime | subscription | £8.99 | 2026-10-21 |
| YouTube Premium | subscription | £12.99 | 2026-10-27 |
| City Living Lettings | rent | £895.00 | 2026-11-01 |
| PureGym | subscription | £29.99 | 2026-11-01 |
| Apple | subscription | £2.99 | 2026-11-02 |
| Netflix | subscription | £12.99 | 2026-11-04 |
| Spotify | subscription | £12.99 | 2026-11-11 |
| Disney Plus | subscription | £9.99 | 2026-11-14 |

**Subscriptions** (8 subscriptions, £113.92 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| PureGym | £29.99 | monthly | 2026-11-01 |
| Xbox | £22.99 | monthly | 2026-10-18 |
| Netflix | £12.99 | monthly | 2026-11-04 |
| Spotify | £12.99 | monthly | 2026-11-11 |
| YouTube Premium | £12.99 | monthly | 2026-10-27 |
| Disney Plus | £9.99 | monthly | 2026-11-14 |
| Amazon Prime | £8.99 | monthly | 2026-10-21 |
| Apple | £2.99 | monthly | 2026-11-02 |

**Debts**

| Kind | Balance | Rate | Free limit / due |
|---|---|---|---|
| bnpl | £138.00 | 0.0% | 2026-10-20 |

**Budgets and savings goals (created on import)**

- Budget: Shopping £120.00 a month, spent £106.47 in October (near).
- Budget: Eating out £450.00 a month, spent £166.44 in October (ok).
- Goal: Ski trip with friends, target £800.00, saved £0.00, by 2027-02-01.

**Habit score:** 45 of 100. Parts: savings_rate 0, months_of_cover 14, spend_stability 78, discretionary_share 14, subscription_creep 64, debt_pressure 100.

**Next Move** (options compared: 3)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | weekly_budget | Plan for £612 you are missing before 2 November | Your bills before your money from family on 2 November take all your cash | Medium confidence: based on your last 4 weeks of spending |
| Runner-up | cut_budget | Cut groceries to £84 a month | You spent £131 more than usual on groceries last month | Low confidence: only 2 months of spending so far |
| Runner-up | build_emergency_fund | Build a safety net of £6,394 | With 3 months of costs put aside, a surprise bill does not go on a card | Low confidence: mixed results in 5 similar past years in UK data |

**3 things Penny noticed**

- You spend £114 a month on 8 subscriptions.
- Your cash and savings cover 0.4 months of spending.
- You owe £138 on cards and loans.

---

## Lena Novak (graduate)

| Field | Value |
|---|---|
| Name | Lena Novak |
| Age | 22 (profile age 22) |
| Uni and city (card) | -, London |
| Town and region (profile) | Manchester, north-west |
| Funding label | Salary |
| Housing (card) | Room in Hackney, £1,050 a month |
| Rent a month (profile) | £1,050.00 |
| Habit line | Not counting rent and bills, spends most on travel; dipped into the overdraft |
| Balance (16 Oct) | £4,596.69 |
| Net worth | £4,596.69 |
| Accounts | Monzo Current Account (current) £296.69; Monzo Pots (savings) £4,300.00 |
| Savings (profile) | £4,300.00 |
| Months of cover | 3.1 |
| Annual income (profile) | £26,636.80 |

**Funding and other income** (from the statement; provenance column per the audit request)

| Source | Kind | Amount | Schedule | Dates in statement | Next | Card label | Provenance |
|---|---|---|---|---|---|---|---|
| family_a_novak | family | £400.00 | one_off | 2026-08-21 | - | - | invented (no source in generator) |
| salary_halden_group_plc | salary | £2,186.40 | monthly | 2026-09-25, 2026-10-23, 2026-11-25 | 2026-10-23 | - | invented (no source in generator) |
| card: Graduate salary | - | £2,186.40 | per month | 25th of each month | - | Graduate salary | invented (no source in generator) |

Rent provenance: **invented** (no uni accommodation page or other source is cited in `tools/gen_statements.py`).

**Spending by category, September 2026** (total £1,488.81; October to the 16th: £1,372.20)

| Category | Amount | Share | Payments |
|---|---|---|---|
| Housing | £1,050.00 | 70.5% | 1 |
| Transport | £182.50 | 12.3% | 22 |
| Eating out | £96.87 | 6.5% | 12 |
| Subscriptions | £60.97 | 4.1% | 3 |
| Groceries | £60.47 | 4.1% | 3 |
| Bills | £38.00 | 2.5% | 1 |

**Bills, next 30 days** (total £1,148.97)

| Name | Kind | Amount | Due |
|---|---|---|---|
| Hackney Lettings | rent | £1,050.00 | 2026-11-01 |
| PureGym | subscription | £34.99 | 2026-11-02 |
| Spotify | subscription | £12.99 | 2026-11-03 |
| Netflix | subscription | £12.99 | 2026-11-09 |
| Octopus Energy | bill | £38.00 | 2026-11-12 |

**Subscriptions** (3 subscriptions, £60.97 a month)

| Merchant | Amount | Cadence | Next payment |
|---|---|---|---|
| PureGym | £34.99 | monthly | 2026-11-02 |
| Netflix | £12.99 | monthly | 2026-11-09 |
| Spotify | £12.99 | monthly | 2026-11-03 |

**Debts**

None.

**Budgets and savings goals (created on import)**

- Budget: Eating out £60.00 a month, spent £77.81 in October (over).
- Goal: Emergency fund, target £5,000.00, saved £4,300.00, by 2027-03-31.

**Habit score:** 89 of 100. Parts: savings_rate 100, months_of_cover 100, spend_stability 73, discretionary_share 91, subscription_creep 72, debt_pressure 100.

**Next Move** (options compared: 1)

| Rank | Kind | Action | Reason | Confidence |
|---|---|---|---|---|
| Top | move_savings | Move your savings to a better rate | Other easy-access accounts pay more interest than yours | Medium confidence: based on 5 similar past periods in UK data |

**3 things Penny noticed**

- You spend £61 a month on 3 subscriptions.
- Your cash and savings cover 3.1 months of spending.
- Not counting rent and bills, you spent the most on transport last month: £182.

---

## 2. Data sources the engine uses

Status from live `GET /v1/sources` at 04:30, 18 Oct 2026. "Feeds" comes from the code (`lifeline_data/macro.py` KEY_SPECS, `lifeline_engine/next_move.py`, `lifeline_explain`, `lifeline_data/hub.py`).

| Source | Status | Series or data | Feeds |
|---|---|---|---|
| Bank of England Database (boe) | live | Bank Rate IUMBEDR; 2y and 5y fixed mortgage IUMBV34, IUMBV42; tracker IUMBV48; SVR IUMTLMV; savings rate IUMB6VJ; card rate IUMCCTL | Next Move (savings, debt, mortgage moves), Test it replays, Life game rates, Penny boe_rates tool |
| Office for National Statistics (ons) | live | CPI D7G7; energy D7GT; fuel D7IO; rent PIPR | Next Move inflation and real returns, Life game prices, Penny inflation tool |
| Nomis (nomis) | live | Median pay NM_30_1; unemployment NM_17_5; owner-occupied share NM_2072_1 | Next Move (job security, pay), Life game jobs and regions |
| HM Land Registry UK HPI (landregistry) | cached | Average price and annual change by region | Life game house prices; Next Move housing moves |
| Frankfurter FX (frankfurter) | live | ECB reference rates | Penny fx_convert tool (international students); GBP/USD in the macro table |
| CoinGecko (coingecko) | cached | Bitcoin return | Life game crypto events; Next Move risk context |
| Yahoo Finance (yahoo) | unavailable | FTSE All-Share return | Life game stock returns (falls back to the saved table) |
| FRED (fred) | unavailable | 10-year gilt yield | Life game bond returns (falls back to the saved table) |
| Octopus Energy (octopus) | live | Typical dual-fuel bill | Next Move energy moves; bill categorisation |
| Open-Meteo (openmeteo) | live | Daily max temperature and rain by region | Guess my spend weather feature |
| GOV.UK bank holidays (bankholidays) | live | Bank holiday dates | Guess my spend bank-holiday feature; bill dates |
| postcodes.io (postcodes) | live | Postcode to region | Manual entry region |
| Police UK (police) | live | Burglary rate | Life game home events (macro table) |
| Environment Agency (environmentagency) | live | Flood risk | Life game home events (macro table) |
| Companies House (companieshouse) | live | Employer status | Next Move job-security check; Life game employer events |
| The Guardian (guardian) | live | News headlines | Penny news_search tool (context only, never a decision input) |
| Bank of England MPC dates (boe-mpc) | live | Next rate decision dates | Money home context line; Penny rate_decision_dates tool (context only) |
| Carbon Intensity (carbonintensity) | live | Grid carbon intensity | Served on /v1/sources only; no decision uses it |
| DWP Stat-Xplore (statxplore) | live | Benefit statistics | Served on /v1/sources only; no decision uses it |
| EPC register (epc) | live | Energy performance of buildings | Served on /v1/sources only; no decision uses it |

Plus the user's own data: the imported statement (sample CSV or PDF), manual entry, and the facts table (`lifeline_engine/rules.py`, each fact with an official URL and checked date).

## 3. Guess my spend model

Code: `lifeline_engine/money/predict.py`; method: `docs/prediction.md`.

- **Target:** `log(1 + spend)` for one day. Daily spend excludes transfers, savings, income, housing, bills, subscriptions and fees.
- **Features:** weekday (one-hot), payday (days since last pay / 30, payday flag), bank holiday (GOV.UK), weather (Open-Meteo max temperature and rain), recent trend (mean log spend of the 7 days before), month end (last 3 days).
- **Model:** ridge regression with standardised features; alpha chosen by walk-forward MAE over 28 days; range = 10th to 90th percentile of walk-forward residuals over 60 days.
- **Training data:** the student's own statement days before the prediction day.

**Inputs and output for one student: Callum Reid (working), prediction for 2026-10-16**

| Item | Value |
|---|---|
| Predicted spend | £6.99 |
| Range | £0.22 to £43.14 |
| Typical day (baseline) | £6.18 |
| Weather | Mild and rain, max 12.7 °C, rain 3.1 mm (live) |
| Bank holiday | False |
| Model | ridge regression on log spend, trained on 91 days |
| Backtest MAE | model £21.12, weekday average £21.35, range coverage 58.7% |
| Reason: weather | It is 13°C and rainy (+£1.18) |
| Reason: recent_trend | You spent less than usual in the last 7 days (-£0.62) |
| Reason: weekday | It is Friday (+£0.07) |

Note: for this student the model beats the weekday average by only £0.23 a day, and the 10% to 90% range covers 58.7% of days (target about 80%).
