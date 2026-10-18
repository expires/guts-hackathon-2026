import Foundation

/// Responses recorded from the local API for the sample student "scottish" (Eilidh Fraser), 2026-10-18,
/// for previews and tests of the ADR 0069 onboarding. The local API did not fill the new ADR 0069 fields yet, so
/// `profile` adds `income_sources`, `debts`, `months_of_cover` and `monthly_rent` from the sample hints (preview
/// data only). The forecast, September and category payments are built from `ForecastMock` (preview data only).
/// The sample cards come from `lifeline_data/statements/samples/index.json`.
enum OnboardingRecorded {
    static var samples: Components.Schemas.SamplesResponse { ContractExamples.decode(#"""
    {"samples": [{"id": "scottish", "title": "Scottish student", "description": "Edinburgh student with a monthly SAAS loan and Young Students' Bursary. Free buses, a summer Fringe job.", "funding": ["maintenance_loan", "bursary", "part_time_job"], "months": 3, "name": "Eilidh Fraser", "age": 19, "avatar": "face-blue-hair", "uni": "University of Edinburgh", "city": "Edinburgh", "funding_label": "SAAS + bursary", "money_in": [{"label": "SAAS loan", "amount": 735.0, "period": "month", "dates": "Mid-month (18 Sep, 16 Oct)"}, {"label": "Young Students' Bursary", "amount": 166.0, "period": "month", "dates": "Same day as the SAAS loan"}, {"label": "Fringe bar job", "amount": 214.79, "period": "week", "dates": "Fridays, 24 Jul to 28 Aug, pay varies"}], "housing": "Shared flat in Marchmont, £540 a month", "habit_line": "Not counting rent and bills, spends most on food shopping; saved £300 in 3 months"}, {"id": "commuter", "title": "Commuter student", "description": "Lives with family and takes the train in with a 16-25 Railcard. Grant plus family help. Saving for a deposit.", "funding": ["grant", "family"], "months": 3, "name": "Priya Patel", "age": 19, "avatar": "face-priya", "uni": "University of Manchester", "city": "Bolton", "funding_label": "Access grant + family", "money_in": [{"label": "Access grant", "amount": 1000.0, "period": "term", "dates": "5 Oct, 1 Feb, 26 Apr"}, {"label": "Mum", "amount": 40.0, "period": "week", "dates": "Every Friday"}], "housing": "Lives at home with family", "habit_line": "Not counting rent and bills, spends most on travel; saved £725 in 3 months"}, {"id": "international", "title": "International student", "description": "From China, studying in Coventry. Parents send money each month by Wise (yuan to pounds). Eats out a lot.", "funding": ["family"], "months": 3, "name": "Yutong Chen", "age": 21, "avatar": "face-girl", "uni": "University of Warwick", "city": "Coventry", "funding_label": "Parents", "money_in": [{"label": "Parents (by Wise)", "amount": 1569.4, "period": "month", "dates": "Early each month, latest 5 Oct; moves with the yuan"}], "housing": "Unite Students room, £790 a month", "habit_line": "Not counting rent and bills, spends most on eating out; no savings yet"}]}
    """#) }

    static var profile: FinanceProfile { ContractExamples.decode(#"""
    {"meta": {"data_status": "mock", "source": "sample", "as_of": "2026-10-16", "label": "Sample data"}, "profile": {"age": 19, "region": "north-west", "annual_income": 11038.25, "savings": 300.0, "other_debt": 0.0, "housing": "rent", "monthly_rent": 540.0}, "character": {"id": "self-scottish", "name": "You", "emoji": "🙂", "sex": "female", "occupation": "Student", "region": "north-west", "town": "Manchester", "birth_year": 2007, "annual_income": 11038.25, "savings": 300.0, "debt": 0.0, "housing": "rent", "property_value": 0.0, "mortgage_balance": 0.0, "blurb": "Built from sample bank data."}, "personal_facts": [{"id": "subscriptions_total", "concept_id": "budgeting", "text": "You spend £6 a month on 1 subscriptions.", "facts": {"monthly_total": 6.0, "count": 1.0}}, {"id": "emergency_months", "concept_id": "emergency-fund", "text": "Your cash and savings cover 1.6 months of spending.", "facts": {"months": 1.6, "liquid": 1398.0, "monthly_spend": 855.0}}], "is_student": true, "income_sources": [{"id": "saas_loan", "kind": "maintenance_loan", "amount": 735.0, "schedule": "monthly", "next_date": "2026-11-16", "dates": ["2026-09-18", "2026-10-16", "2026-11-16", "2026-12-16"]}, {"id": "saas_ysb", "kind": "bursary", "amount": 166.0, "schedule": "monthly", "next_date": "2026-11-16", "dates": ["2026-09-18", "2026-10-16", "2026-11-16", "2026-12-16"]}, {"id": "summer_fringe", "kind": "part_time_job", "amount": 215.0, "schedule": "one_off", "next_date": null, "dates": ["2026-07-24", "2026-07-31", "2026-08-07", "2026-08-14", "2026-08-21", "2026-08-28"]}], "debts": [], "months_of_cover": 1.6, "monthly_rent": 540.0}
    """#) }

    static var spending: SpendingResponse { ContractExamples.decode(#"""
    {"meta": {"data_status": "mock", "source": "sample", "as_of": "2026-10-16", "label": "Sample data"}, "month": "2026-10", "total": 698.35, "categories": [{"category": "housing", "label": "Housing", "emoji": "🏠", "amount": 540.0, "share": 0.7733, "transactions": 1, "change_pct": 0.0}, {"category": "groceries", "label": "Groceries", "emoji": "🛒", "amount": 128.72, "share": 0.1843, "transactions": 6, "change_pct": 21.5}, {"category": "health", "label": "Health", "emoji": "💊", "amount": 11.37, "share": 0.0163, "transactions": 2}, {"category": "bills", "label": "Bills", "emoji": "💡", "amount": 8.0, "share": 0.0115, "transactions": 1, "change_pct": 0.0}, {"category": "other", "label": "Other", "emoji": "📦", "amount": 5.24, "share": 0.0075, "transactions": 1, "change_pct": -96.8}, {"category": "education", "label": "Education", "emoji": "🎓", "amount": 5.02, "share": 0.0072, "transactions": 2, "change_pct": 90.2}]}
    """#) }

    static var bills: BillsResponse { ContractExamples.decode(#"""
    {"meta": {"data_status": "mock", "source": "sample", "as_of": "2026-10-16", "label": "Sample data"}, "total_next_30_days": 553.99, "items": [{"id": "bill_spotify", "name": "Spotify", "emoji": "🔁", "kind": "subscription", "amount": 5.99, "due_date": "2026-10-20", "status": "upcoming"}, {"id": "bill_marchmont-lettings", "name": "Marchmont Lettings", "emoji": "🏠", "kind": "rent", "amount": 540.0, "due_date": "2026-11-01", "status": "upcoming"}, {"id": "bill_giffgaff", "name": "giffgaff", "emoji": "💡", "kind": "bill", "amount": 8.0, "due_date": "2026-11-05", "status": "upcoming"}]}
    """#) }

    static var subscriptions: SubscriptionsResponse { ContractExamples.decode(#"""
    {"meta": {"data_status": "mock", "source": "sample", "as_of": "2026-10-16", "label": "Sample data"}, "monthly_total": 5.99, "count": 1, "items": [{"id": "sub_spotify", "merchant": "Spotify", "emoji": "🔁", "category": "subscriptions", "amount": 5.99, "cadence": "monthly", "monthly_cost": 5.99, "next_payment": "2026-10-20"}]}
    """#) }

    static var overview: FinanceOverview { ContractExamples.decode(#"""
    {"meta": {"data_status": "mock", "source": "sample", "as_of": "2026-10-16", "label": "Sample data"}, "balance": 1397.62, "net_worth": 1397.62, "balance_parts": [{"label": "Monzo Current Account", "amount": 1097.62}, {"label": "Monzo Pots", "amount": 300.0}], "net_worth_parts": [{"label": "Monzo Current Account", "amount": 1097.62}, {"label": "Monzo Pots", "amount": 300.0}], "accounts": [{"id": "monzo_current", "name": "Monzo Current Account", "kind": "current", "provider": "Monzo", "balance": 1097.62, "currency": "GBP"}, {"id": "monzo_savings", "name": "Monzo Pots", "kind": "savings", "provider": "Monzo", "balance": 300.0, "currency": "GBP"}], "balance_history": [{"date": "2026-10-09", "value": 574.85}, {"date": "2026-10-16", "value": 1397.62}], "net_worth_history": [{"date": "2026-10-09", "value": 574.85}, {"date": "2026-10-16", "value": 1397.62}]}
    """#) }

    static var habits: HabitScore { ContractExamples.decode(#"""
    {"components": {"savings_rate": 26, "months_of_cover": 54, "spend_stability": 3, "discretionary_share": 98, "subscription_creep": 95, "debt_pressure": 100}, "overall": 63}
    """#) }

    static var importResult: Components.Schemas.ImportResult { ContractExamples.decode(#"""
    {"import_id": "im_48a76b0ac078", "status": "done", "provider": "monzo", "transactions": 66, "first_date": "2026-07-18", "last_date": "2026-10-16", "months_covered": 3.0, "warnings": [], "stages": [{"name": "read", "label": "Reading your statement", "done": true}, {"name": "categorise", "label": "Sorting your spending", "done": true}, {"name": "find_bills", "label": "Finding your bills", "done": true}, {"name": "build_profile", "label": "Building your profile", "done": true}, {"name": "next_move", "label": "Finding your next move", "done": true}]}
    """#) }
}

extension OnboardingRecorded {
    /// Eilidh's forecast (ADR 0072): the canvas numbers from `ForecastMock` (on track). Preview data only.
    static var forecast: Forecast { ForecastMock.forecast(ForecastMock.onTrack) }

    /// The recorded October, with September as a steady variant of it (preview data only).
    static func spending(_ month: String?) -> SpendingResponse {
        var response = ForecastMock.spending(base: spending, month: month)
        // Spotify (£5.99 on the 20th) is paid in every full month; the recorded October is before the 20th.
        if month != nil, month != spending.month, !response.categories.contains(where: { $0.category == .subscriptions }) {
            let spotify: Components.Schemas.CategorySpend = ContractExamples.decode(#"""
            {"category": "subscriptions", "label": "Subscriptions", "emoji": "🔁", "amount": 5.99, "share": 0, "transactions": 1}
            """#)
            response.categories.append(spotify)
            let total = response.categories.reduce(0) { $0 + $1.amount }
            response.total = (total * 100).rounded() / 100
            for index in response.categories.indices {
                response.categories[index].share = total > 0 ? ((response.categories[index].amount / total) * 1_000).rounded() / 1_000 : 0
            }
        }
        return response
    }

    /// One category in one month, built from `spending(month)` (preview data only).
    static func categoryDetail(_ category: String, _ month: String?) throws -> CategoryDetail {
        guard let detail = ForecastMock.categoryDetail(spending: spending(month), category: category) else {
            throw APIError.server(status: 404, code: "not_found", message: "No spending in that category.", source: "mock")
        }
        return detail
    }

    /// Launch argument for UI tests and screenshots: onboarding answers from these recordings (Debug builds only).
    static let launchArgument = "-onboardingRecorded"

    /// Onboarding calls answered from the recordings. Sign in, bank and postcode calls use the mock client.
    static var api: OnboardingAPI {
        let mock = MockClient()
        var api = OnboardingAPI.from(client: mock)
        api.listSamples = { onUpdate in await onUpdate(OnboardingRecorded.samples.samples) }
        api.importSample = { _ in OnboardingRecorded.importResult }
        api.importStatement = { _, _, _ in OnboardingRecorded.importResult }
        api.financeProfile = { OnboardingRecorded.profile }
        api.setManualFinance = { _ in OnboardingRecorded.profile }
        api.spending = { month in OnboardingRecorded.spending(month) }
        api.categoryDetail = { category, month in try OnboardingRecorded.categoryDetail(category, month) }
        api.bills = { OnboardingRecorded.bills }
        api.subscriptions = { OnboardingRecorded.subscriptions }
        api.overview = { OnboardingRecorded.overview }
        api.habits = { OnboardingRecorded.habits }
        api.forecast = { OnboardingRecorded.forecast }
        return api
    }
}
