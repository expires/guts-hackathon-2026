import Foundation
import Testing
@testable import Lifeline

/// Accounts: connect, errors, return URLs and the Monzo history retry. All on MockClient with an instant sleeper.
@MainActor
@Suite("Accounts view model")
struct AccountsViewModelTests {
    private let instant: AccountsViewModel.Sleeper = { _ in }

    @Test func startsWithNothingConnected() async {
        let model = AccountsViewModel(client: MockClient(), sleep: instant)
        await model.load()
        let rows = model.state.rows
        #expect(rows.map(\.id) == ["monzo", "trading212"])
        #expect(rows.allSatisfy { !$0.isConnected && $0.statusText == "Not connected" })
        #expect(model.state.phase == .ready)
    }

    @Test func connectingTrading212Works() async {
        let model = AccountsViewModel(client: MockClient(), sleep: instant)
        await model.load()
        model.actions.onConnectTrading212()
        #expect(model.state.trading212Form?.guidance == AccountsViewModel.trading212Guidance)
        await model.submitTrading212(apiKey: "abcd1234", apiSecret: "shh")
        let row = model.state.rows.first { $0.id == "trading212" }
        #expect(row?.isConnected == true)
        #expect(row?.statusText == "Sample data", "Mock connections are labelled sample")
        #expect(row?.hintText == "Key …1234")
        #expect(model.state.trading212Form == nil, "Sheet closes on success")
        #expect(model.state.banner?.kind == .success)
    }

    @Test func rejectedTrading212KeyShowsPlainEnglish() async {
        let model = AccountsViewModel(client: MockClient(), sleep: instant)
        await model.load()
        model.actions.onConnectTrading212()
        await model.submitTrading212(apiKey: "invalid", apiSecret: "nope")
        #expect(model.state.trading212Form?.errorText == "Key rejected. Check both the key and the secret.")
        #expect(model.state.trading212Form?.isSubmitting == false)
        #expect(model.state.rows.first { $0.id == "trading212" }?.isConnected == false)
    }

    @Test func emptyTrading212FieldsAreNotSent() async {
        let model = AccountsViewModel(client: MockClient(), sleep: instant)
        await model.load()
        model.actions.onConnectTrading212()
        await model.submitTrading212(apiKey: " ", apiSecret: "x")
        #expect(model.state.trading212Form?.errorText == "Enter both the key and the secret.")
    }

    @Test func providerErrorsMapToPlainEnglish() {
        func server(_ code: String) -> APIError { .server(status: 400, code: code, message: "raw", source: "x") }
        #expect(AccountsViewModel.trading212Message(server("provider_auth")) == "Key rejected. Check both the key and the secret.")
        #expect(AccountsViewModel.trading212Message(server("rate_limited")) == "Trading212 is busy. Try again in a minute.")
        #expect(AccountsViewModel.trading212Message(server("unavailable")) == "Trading212 is not answering right now. Try again soon.")
        #expect(AccountsViewModel.trading212Message(.network).contains("Cannot reach"))
    }

    @Test func disconnectNeedsConfirmation() async {
        let model = AccountsViewModel(client: MockClient(), sleep: instant)
        await model.load()
        await model.submitTrading212(apiKey: "abcd1234", apiSecret: "shh")
        model.actions.onRequestDisconnect("trading212")
        #expect(model.state.disconnectPrompt?.title == "Disconnect Trading212?")
        model.actions.onCancelDisconnect()
        #expect(model.state.rows.first { $0.id == "trading212" }?.isConnected == true)
        model.actions.onRequestDisconnect("trading212")
        await model.confirmDisconnect()
        #expect(model.state.rows.first { $0.id == "trading212" }?.isConnected == false)
        #expect(AccountsViewModel.prompt(for: .monzo).message.contains("deletes the history"))
    }

    // MARK: Return URLs

    @Test func parsesTheReturnUrls() {
        let ok = URL(string: "lifeline://connected?status=ok&provider=monzo&session=mock_abc")!
        #expect(DeepLink.parse(ok) == .connection(.connected(provider: "monzo", session: "mock_abc")))
        let failed = URL(string: "lifeline://connected?status=error&code=bad_state")!
        #expect(DeepLink.parse(failed) == .connection(.failed(code: "bad_state")))
        #expect(DeepLink.parse(URL(string: "lifeline://join/ab12cd")!) == .join(code: "AB12CD"))
        #expect(DeepLink.parse(URL(string: "https://example.com/connected?status=ok")!) == nil)
        #expect(DeepLink.parse(URL(string: "lifeline://connected?status=weird")!) == nil)
        #expect(ConnectionReturn.message(for: "bad_state") == "That sign-in link has expired. Start again.")
        #expect(ConnectionReturn.message(for: "zzz") == "Could not connect Monzo. Try again.")
    }

    @Test func returnOpensAccountsAndIsTakenOnce() {
        let coordinator = AppCoordinator()
        coordinator.handle(URL(string: "lifeline://connected?status=ok&provider=monzo&session=s1")!)
        #expect(coordinator.sheet == .accounts)
        #expect(coordinator.takePendingReturn() == .connected(provider: "monzo", session: "s1"))
        #expect(coordinator.takePendingReturn() == nil)
    }

    @Test func returnGoesToThePlayYourselfFormWhenItIsWaiting() {
        let coordinator = AppCoordinator()
        coordinator.bankFlowAwaitingReturn = true
        coordinator.handle(URL(string: "lifeline://connected?status=ok&provider=monzo&session=s1")!)
        #expect(coordinator.sheet == nil, "No Accounts sheet over the form")
        #expect(coordinator.takeBankFlowReturn() == .connected(provider: "monzo", session: "s1"))
    }

    @Test func joinLinkIsKept() {
        let coordinator = AppCoordinator()
        coordinator.handle(URL(string: "lifeline://join/XY12Z9")!)
        #expect(coordinator.takeJoinCode() == "XY12Z9")
    }

    @Test func successfulReturnRefreshesAndShowsToast() async {
        let client = MockClient()
        _ = try? await client.connectMonzoToken("t")
        let model = AccountsViewModel(client: client, sleep: instant)
        await model.handle(.connected(provider: "monzo", session: "s"))
        #expect(model.state.rows.first { $0.id == "monzo" }?.isConnected == true)
        #expect(model.state.banner == .init(kind: .success, text: "Monzo connected."))
    }

    @Test func failedReturnShowsPlainEnglish() async {
        let model = AccountsViewModel(client: MockClient(), sleep: instant)
        await model.handle(.failed(code: "provider_auth"))
        #expect(model.state.banner == .init(kind: .error, text: "Monzo did not accept the sign-in. Try again."))
    }

    @Test func bankFlowFinishesOnReturn() async {
        let model = BankConnectViewModel(client: MockClient())
        await model.handle(.connected(provider: "monzo", session: "s1"))
        #expect(model.state.step == .connected)
        let failing = BankConnectViewModel(client: MockClient())
        await failing.handle(.failed(code: "bad_state"))
        guard case let .failed(error) = failing.state.step else { Issue.record("expected failed"); return }
        #expect(error.message == "That sign-in link has expired. Start again.")
    }

    // MARK: History retry

    @Test func syncRetriesUntilApproved() async {
        let client = MockClient(monzoSyncsBeforeApproval: 2)
        let model = AccountsViewModel(client: client, sleep: instant)
        await model.connectMonzo()
        #expect(model.state.rows.first { $0.id == "monzo" }?.historyKind == .waitingForApproval)
        #expect(model.state.approvalNote == AccountsViewModel.approvalMessage)
        #expect(model.state.showsImportNow)
        await model.waitForSync()
        #expect(model.syncAttempts == 3, "Two refusals, then success")
        #expect(model.state.rows.first { $0.id == "monzo" }?.historyKind == .imported)
        #expect(model.state.rows.first { $0.id == "monzo" }?.historyText == "History imported back to 18 Oct 2024")
        #expect(model.state.approvalNote == nil)
        #expect(!model.syncTimedOut)
    }

    @Test func syncStopsAfterFiveMinutes() async {
        let client = MockClient(monzoSyncsBeforeApproval: 10_000)
        let model = AccountsViewModel(client: client, sleep: instant)
        await model.connectMonzo()
        await model.waitForSync()
        #expect(model.syncAttempts == 60, "Every 5 seconds for 5 minutes")
        #expect(model.syncTimedOut)
        #expect(model.state.showsImportNow, "Manual import stays available")
    }

    @Test func leavingTheScreenStopsTheRetry() async {
        let client = MockClient(monzoSyncsBeforeApproval: 10_000)
        let slow: AccountsViewModel.Sleeper = { try await Task.sleep(for: $0) }
        let model = AccountsViewModel(client: client, sleep: slow)
        await model.connectMonzo()
        model.stopSync()
        await model.waitForSync()
        #expect(model.syncAttempts == 0)
        #expect(!model.syncTimedOut)
    }

    @Test func importNowRunsOneAttemptAndResumes() async {
        let client = MockClient(monzoSyncsBeforeApproval: 1)
        let slow: AccountsViewModel.Sleeper = { try await Task.sleep(for: $0) }
        let model = AccountsViewModel(client: client, sleep: slow)
        await model.connectMonzo()
        model.stopSync()
        await model.importNow()
        #expect(model.syncAttempts == 1)
        #expect(model.state.rows.first { $0.id == "monzo" }?.historyKind == .waitingForApproval)
        await model.importNow()
        #expect(model.state.rows.first { $0.id == "monzo" }?.historyKind == .imported)
        model.stopSync()
    }

    @Test func disconnectingMonzoStopsRetry() async {
        let client = MockClient(monzoSyncsBeforeApproval: 10_000)
        let slow: AccountsViewModel.Sleeper = { try await Task.sleep(for: $0) }
        let model = AccountsViewModel(client: client, sleep: slow)
        await model.connectMonzo()
        model.actions.onRequestDisconnect("monzo")
        await model.confirmDisconnect()
        await model.waitForSync()
        #expect(model.state.rows.first { $0.id == "monzo" }?.isConnected == false)
        #expect(!AccountsViewModel.monzoNeedsSync(model.connections))
    }
}
