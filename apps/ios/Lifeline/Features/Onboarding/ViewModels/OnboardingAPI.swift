import Foundation

/// The backend calls onboarding needs, as closures (ADR 0037). Tests pass their own closures.
struct OnboardingAPI: Sendable {
    /// Sends the Apple identity token. The client stores the returned token.
    var signInWithApple: @Sendable (_ identityToken: String) async throws -> Void
    /// Monzo consent link: `GET /v1/bank/auth-link?provider=monzo`.
    var bankAuthLink: @Sendable (_ provider: String) async throws -> BankAuthLink
    /// After the bank consent: `GET /v1/bank/summary?session=`.
    var bankSummary: @Sendable (_ session: String) async throws -> BankSummary
    /// `POST /v1/finance/statements` (multipart, max 5 MB).
    var importStatement: @Sendable (_ file: Data, _ fileName: String, _ provider: String?) async throws -> Components.Schemas.ImportResult
    /// `PUT /v1/finance/manual`.
    var setManualFinance: @Sendable (_ input: Components.Schemas.ManualFinanceInput) async throws -> FinanceProfile
    /// `GET /v1/postcodes/reverse`.
    var reversePostcode: @Sendable (_ lat: Double, _ lon: Double) async throws -> Components.Schemas.ReversePostcode
    var nextMove: @Sendable () async throws -> NextMoveResponse
    var financeProfile: @Sendable () async throws -> FinanceProfile
    /// The built-in sample students, cached first (ADR 0060). `onUpdate` may run twice (disk, then network).
    var listSamples: @Sendable (_ onUpdate: @escaping @MainActor @Sendable ([SampleStatement]) -> Void) async throws -> Void = { _ in }
    /// `POST /v1/finance/samples/{id}/import`: the sample student's statement through the real pipeline.
    var importSample: @Sendable (_ id: String) async throws -> Components.Schemas.ImportResult = { _ in throw OnboardingAPI.notYetAvailable }
    /// "Building their profile" (ADR 0069): one call per stage. Defaults fail, and the stage shows as skipped.
    /// `GET /v1/finance/spending?month=` (nil is this month).
    var spending: @Sendable (_ month: String?) async throws -> SpendingResponse = { _ in throw OnboardingAPI.notYetAvailable }
    var bills: @Sendable () async throws -> BillsResponse = { throw OnboardingAPI.notYetAvailable }
    var subscriptions: @Sendable () async throws -> SubscriptionsResponse = { throw OnboardingAPI.notYetAvailable }
    /// `GET /v1/finance/overview`: accounts, for debts.
    var overview: @Sendable () async throws -> FinanceOverview = { throw OnboardingAPI.notYetAvailable }
    /// `GET /v1/sources`: live UK data status.
    var sources: @Sendable () async throws -> [SourceStatus] = { throw OnboardingAPI.notYetAvailable }
    /// `GET /v1/habits`: ratios 0-100, no amounts.
    var habits: @Sendable () async throws -> HabitScore = { throw OnboardingAPI.notYetAvailable }
    /// Trading 212 (`/v1/connections`) is not in the contract yet, so it is always unavailable.
    var hasTrading212 = false

    static func from(client: any LifelineClient) -> OnboardingAPI {
        OnboardingAPI(
            signInWithApple: { token in try await client.signInWithApple(identityToken: token) },
            bankAuthLink: { provider in try await client.bankAuthLink(provider: provider) },
            bankSummary: { session in try await client.bankSummary(session: session) },
            importStatement: { file, name, provider in try await client.importStatement(file: file, fileName: name, provider: provider) },
            setManualFinance: { input in try await client.setManualFinance(input) },
            reversePostcode: { lat, lon in try await client.reversePostcode(lat: lat, lon: lon) },
            nextMove: { try await client.nextMove() },
            financeProfile: { try await client.financeProfile() },
            listSamples: { onUpdate in try await client.load(CachedOps.samples, onUpdate: onUpdate) },
            importSample: { id in try await client.importSample(id: id) },
            spending: { month in try await client.financeSpending(month: month) },
            bills: { try await client.bills() },
            subscriptions: { try await client.subscriptions() },
            overview: { try await client.financeOverview() },
            sources: { try await client.listSources() },
            habits: { try await client.habits() }
        )
    }

    static var notYetAvailable: APIError { APIError.server(
        status: 501, code: "not_implemented", message: L10n.tr("This is not available in this build yet."), source: "app"
    ) }
}

/// Contract examples for the operations the mock client does not serve yet.
enum OnboardingExamples {
    static var importResult: Components.Schemas.ImportResult {
        ContractExamples.decode("""
        {"import_id": "imp_1", "status": "done", "provider": "monzo", "transactions": 412,
         "first_date": "2026-04-01", "last_date": "2026-10-16", "months_covered": 6.5, "warnings": [],
         "stages": [
          {"name": "read", "label": "Reading your statement", "done": true},
          {"name": "categorise", "label": "Sorting your spending", "done": true},
          {"name": "find_bills", "label": "Finding bills and subscriptions", "done": true},
          {"name": "build_profile", "label": "Building your profile", "done": true},
          {"name": "next_move", "label": "Finding your next move", "done": true}]}
        """)
    }

    static var reversePostcode: Components.Schemas.ReversePostcode {
        ContractExamples.decode("""
        {"postcode": "LS6 1AN", "region": "yorkshire-and-the-humber", "town": "Leeds", "status": "mock"}
        """)
    }

    static var me: Components.Schemas.Me {
        ContractExamples.decode("""
        {"id": "usr_8f3a2c", "display_name": "Priya", "auth_provider": "apple", "created_at": "2026-10-17T12:00:00Z",
         "has_finance_data": true, "finance_inputs": ["statement"]}
        """)
    }
}
