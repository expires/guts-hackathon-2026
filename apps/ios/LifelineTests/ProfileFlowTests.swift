import Foundation
import Testing
@testable import Lifeline

private final class Cell<T>: @unchecked Sendable {
    var value: T
    init(_ value: T) { self.value = value }
}

/// "Play as yourself", "Your profile" and the shared connect step, against closure APIs and the fixtures.
@MainActor
@Suite("Profile flow")
struct ProfileFlowTests {
    private func connectionsAPI(_ scenario: Cell<ProfileFixtures.Scenario>, log: Cell<[String]> = Cell([])) -> ConnectionsAPI {
        let mock = MockClient(data: .recorded)
        return ConnectionsAPI(
            profileStats: { ProfileFixtures.stats(scenario.value) },
            connections: { try await mock.listConnections() },
            connectTrading212: { key, _ in
                log.value.append("t212:\(key)")
                scenario.value = scenario.value == .monzoAndT212 ? .monzoAndT212 : .t212Only
            },
            disconnect: { provider in
                log.value.append("disconnect:\(provider)")
                scenario.value = .nothing
            },
            importStatement: { _, name, _ in log.value.append("statement:\(name)") },
            monzo: .init(
                bankAuthLink: { _ in
                    ContractExamples.decode(#"{"url": "https://auth.example.test/?state=abc", "state": "abc", "provider": "monzo", "status": "live"}"#)
                },
                monzoConnected: { true },
                syncMonzo: {
                    scenario.value = .monzoAndT212
                    return ContractExamples.decode(#"{"synced": true, "oldest": "2026-07-21", "count": 151}"#)
                }
            )
        )
    }

    // MARK: Profile picker

    @Test func pickingASampleImportsItThenOpensTheStats() async {
        let scenario = Cell(ProfileFixtures.Scenario.nothing)
        let imported = Cell<[String]>([])
        let model = ProfilePickerViewModel(api: .init(
            listSamples: { MockExamples.samples },
            importSample: { id in imported.value.append(id); scenario.value = .sampleStudent },
            profileStats: { ProfileFixtures.stats(scenario.value) }
        ))
        var opened = 0
        model.onPickedSample = { opened += 1 }
        await model.load()
        #expect(model.state.cards.first?.id == ProfilePickerViewModel.youID)
        #expect(model.state.cards.count == MockExamples.samples.count + 1)
        #expect(model.state.cards.allSatisfy { !$0.isActive })

        let id = MockExamples.samples[0].id
        await model.pick(id)
        #expect(imported.value == [id])
        #expect(opened == 1)
        let active = model.state.cards.filter(\.isActive)
        #expect(active.count == 1 && active.first?.badge == "Sample data")
        #expect(model.state.cards.dropFirst().allSatisfy { $0.badge == "Sample data" })

        // The stats page then shows the sample as sample data.
        let stats = ProfileStatsViewModel.makeState(ProfileFixtures.stats(scenario.value))
        #expect(stats.connections.first { $0.id == "sample" }?.statusText == "Sample data")
        #expect(stats.sections.first { $0.id == "habits" }?.isAvailable == true)
        #expect(stats.canPlay)
    }

    @Test func pickingYouOpensTheConnectStepAndMarksYouActiveWhenDataIsConnected() async {
        let model = ProfilePickerViewModel(api: .init(
            listSamples: { MockExamples.samples },
            importSample: { _ in },
            profileStats: { ProfileFixtures.stats(.monzoAndT212) }
        ))
        var youPicked = 0
        model.onPickYou = { youPicked += 1 }
        await model.load()
        #expect(model.state.cards.first?.isActive == true)
        await model.pick(ProfilePickerViewModel.youID)
        #expect(youPicked == 1)
    }

    @Test func aFailedImportShowsAMessageAndStaysOnThePicker() async {
        let model = ProfilePickerViewModel(api: .init(
            listSamples: { MockExamples.samples },
            importSample: { _ in throw APIError.server(status: 503, code: "store_unavailable", message: "Try again.", source: "api") },
            profileStats: { ProfileFixtures.stats(.nothing) }
        ))
        var opened = 0
        model.onPickedSample = { opened += 1 }
        await model.load()
        await model.pick(MockExamples.samples[0].id)
        #expect(opened == 0 && model.state.errorMessage != nil && model.state.busyID == nil)
    }

    // MARK: Connect step

    @Test func theConnectStepHasExactlyFourOptionsAndNoStudentPicker() async {
        let scenario = Cell(ProfileFixtures.Scenario.t212Only)
        let model = ConnectionsViewModel(api: connectionsAPI(scenario))
        await model.load()
        #expect(model.state.rows.map(\.kind) == [.monzo, .trading212, .statement, .manual])
        let byKind = Dictionary(uniqueKeysWithValues: model.state.rows.map { ($0.kind, $0) })
        #expect(byKind[.trading212]?.statusText == "Connected")
        #expect(byKind[.trading212]?.detail == "8 holdings")
        #expect(byKind[.trading212]?.canDisconnect == true)
        #expect(byKind[.monzo]?.statusText == "Not connected")
        #expect(byKind[.monzo]?.canDisconnect == false)
        #expect(byKind[.statement]?.canDisconnect == false && byKind[.manual]?.canDisconnect == false)
        #expect(model.state.continueTitle == nil)
    }

    @Test func connectingTrading212RefreshesTheRowsAndTheStats() async {
        let scenario = Cell(ProfileFixtures.Scenario.nothing)
        let log = Cell<[String]>([])
        let model = ConnectionsViewModel(api: connectionsAPI(scenario, log: log), continueTitle: "Continue")
        var changed = 0
        model.onChanged = { changed += 1 }
        await model.load()
        #expect(model.state.rows.allSatisfy { !$0.isConnected })

        await model.connect(.trading212)
        #expect(model.state.trading212.isPresented)
        await model.connectTrading212(key: " ", secret: "s")
        #expect(model.state.trading212.errorMessage != nil && log.value.isEmpty)
        await model.connectTrading212(key: " abc ", secret: "def")
        #expect(log.value == ["t212:abc"])
        #expect(!model.state.trading212.isPresented)
        #expect(model.state.rows.first { $0.kind == .trading212 }?.isConnected == true)
        #expect(model.state.notice == "Trading 212 is connected.")
        #expect(changed == 1)

        // The stats page loads again and now has investments.
        let stats = ProfileStatsViewModel(load: { ProfileFixtures.stats(scenario.value) })
        await stats.reload()
        let investments = stats.state.sections.first { $0.id == "investments" }
        #expect(investments?.isAvailable == true)
        #expect(investments?.sourceLine == "From Trading 212")
        #expect(stats.state.sections.first { $0.id == "habits" }?.isAvailable == false)
    }

    @Test func aWrongTrading212KeyKeepsTheSheetWithAMessage() async {
        let scenario = Cell(ProfileFixtures.Scenario.nothing)
        var api = connectionsAPI(scenario)
        api.connectTrading212 = { _, _ in
            throw APIError.server(status: 400, code: "provider_auth", message: "Trading212 did not accept those details.", source: "trading212")
        }
        let model = ConnectionsViewModel(api: api)
        await model.load()
        await model.connect(.trading212)
        await model.connectTrading212(key: "k", secret: "s")
        #expect(model.state.trading212.isPresented)
        #expect(model.state.trading212.errorMessage == "Trading212 did not accept those details.")
    }

    @Test func disconnectAsksFirstThenCallsTheServer() async {
        let scenario = Cell(ProfileFixtures.Scenario.monzoAndT212)
        let log = Cell<[String]>([])
        let model = ConnectionsViewModel(api: connectionsAPI(scenario, log: log))
        await model.load()
        model.requestDisconnect(.statement)
        #expect(model.state.pendingDisconnect == nil, "a statement is not a connection")
        model.requestDisconnect(.trading212)
        #expect(model.state.pendingDisconnect == .trading212 && log.value.isEmpty)
        model.actions.onCancelDisconnect()
        #expect(model.state.pendingDisconnect == nil && log.value.isEmpty)
        model.requestDisconnect(.trading212)
        await model.confirmDisconnect()
        #expect(log.value == ["disconnect:trading212"])
        #expect(model.state.rows.allSatisfy { !$0.isConnected })
    }

    @Test func statementAndManualHooksOpenTheirPickers() async {
        let model = ConnectionsViewModel(api: connectionsAPI(Cell(.nothing)))
        var picked = 0, typed = 0
        model.pickStatement = { picked += 1 }
        model.enterNumbers = { typed += 1 }
        await model.load()
        await model.connect(.statement)
        await model.connect(.manual)
        #expect(picked == 1 && typed == 1)
    }

    @Test func aStatementIsSentAndTheRowsRefresh() async {
        let log = Cell<[String]>([])
        let model = ConnectionsViewModel(api: connectionsAPI(Cell(.nothing), log: log))
        await model.load()
        await model.importStatement(data: Data("date,amount".utf8), fileName: "monzo.csv")
        #expect(log.value == ["statement:monzo.csv"])
        #expect(model.state.notice == "Your statement is added.")
        await model.importStatement(data: Data(count: ConnectionsViewModel.maxStatementBytes + 1), fileName: "big.csv")
        #expect(model.state.errorMessage != nil)
    }

    // MARK: Monzo (the shared flow)

    @Test func monzoUsesTheSameSafariAndApprovalFlowAsOnboarding() async {
        let scenario = Cell(ProfileFixtures.Scenario.nothing)
        let model = ConnectionsViewModel(api: connectionsAPI(scenario))
        let opened = Cell<[URL]>([])
        model.openInSafari = { opened.value.append($0) }
        model.monzoFlow.connectInterval = .milliseconds(1)
        model.monzoFlow.pollInterval = .milliseconds(1)
        var changed = 0
        model.onChanged = { changed += 1 }
        await model.load()
        await model.connect(.monzo)
        #expect(opened.value == [URL(string: "https://auth.example.test/?state=abc")!])
        #expect(model.state.monzoWait == .signingIn)
        print("DBG test before wait, task nil?", model.monzoTask == nil, ObjectIdentifier(model))
        await model.monzoTask?.value
        print("DBG test after wait", model.state.notice as Any, ObjectIdentifier(model))
        #expect(model.state.monzoWait == nil)
        #expect(model.state.rows.first { $0.kind == .monzo }?.isConnected == true)
        #expect(model.state.rows.first { $0.kind == .monzo }?.detail == "Transactions since 21 Jul 2026 (151)")
        #expect(model.state.notice == "Monzo is connected.", "\(String(describing: model.state.notice)) \(String(describing: model.state.errorMessage))")
        #expect(changed == 1)
    }

    @Test func monzoOnboardingAndConnectionsShareOneFlowType() {
        // Onboarding's ViewModel keeps its Monzo behaviour through the same MonzoConnectFlow.
        let onboarding = OnboardingViewModel(api: OnboardingAPI.from(client: MockClient(data: .recorded)), appleAvailable: false, isSampleData: true)
        onboarding.monzoPollLimit = 7
        #expect(onboarding.monzoPollLimit == 7)
        #expect(OnboardingViewModel.monzoErrorMessage(code: "access_denied") == MonzoConnectFlow.errorMessage(code: "access_denied"))
    }

    @Test func monzoCancelClosesThePopUp() async {
        let model = ConnectionsViewModel(api: {
            var api = connectionsAPI(Cell(.nothing))
            api.monzo.monzoConnected = { false }
            return api
        }())
        model.openInSafari = { _ in }
        model.monzoFlow.connectInterval = .seconds(5)
        await model.load()
        await model.connect(.monzo)
        #expect(model.state.monzoWait == .signingIn)
        model.actions.onMonzoCancel()
        #expect(model.state.monzoWait == nil)
    }

    // MARK: Missing hints jump to the right option

    @Test func missingSectionsHintAndJumpToTheRightConnectOption() {
        let none = ProfileStatsViewModel.makeState(ProfileFixtures.stats(.nothing))
        #expect(none.sections.map(\.id) == ["habits", "spending", "net_worth", "investments"])
        #expect(none.sections.allSatisfy { !$0.isAvailable && $0.missingHint != nil })
        #expect(none.sections.first { $0.id == "habits" }?.missingHint == "Connect Monzo, upload a statement or use a sample student to see your habits.")
        #expect(none.sections.first { $0.id == "investments" }?.jump == .trading212)
        #expect(none.sections.first { $0.id == "habits" }?.jump == .monzo)
        #expect(!none.canPlay && none.playTitle == "Connect your money" && none.playMissing != nil)

        let t212 = ProfileStatsViewModel.makeState(ProfileFixtures.stats(.t212Only))
        #expect(t212.canPlay && t212.playTitle == "Play as yourself")
        #expect(t212.playMissing?.contains("your habits") == true)
        #expect(t212.sections.first { $0.id == "net_worth" }?.isAvailable == true)

        let model = ProfileStatsViewModel(load: { ProfileFixtures.stats(.t212Only) })
        var jumped: [ConnectKind?] = []
        model.onConnect = { jumped.append($0) }
        model.actions.onConnect(t212.sections[0].jump)
        #expect(jumped == [.monzo])
    }

    @Test func playAsYourselfWithoutDataLeadsToTheConnectStep() async {
        let model = ProfileStatsViewModel(load: { ProfileFixtures.stats(.nothing) })
        var played = 0
        var connected: [ConnectKind?] = []
        model.onPlay = { played += 1 }
        model.onConnect = { connected.append($0) }
        await model.reload()
        model.actions.onPlay()
        #expect(played == 0 && connected.count == 1)

        let withData = ProfileStatsViewModel(load: { ProfileFixtures.stats(.monzoAndT212) })
        withData.onPlay = { played += 1 }
        await withData.reload()
        withData.actions.onPlay()
        #expect(played == 1)
    }

    // MARK: Stats mapping

    @Test func fullStatsShowEveryNumberFromTheResponseAndItsSource() {
        let state = ProfileStatsViewModel.makeState(ProfileFixtures.stats(.monzoAndT212))
        #expect(state.connections.map(\.statusText) == ["Live", "Live", "Not connected", "Not connected", "Not connected"])
        let spending = state.sections.first { $0.id == "spending" }
        #expect(spending?.sourceLine == "From Monzo")
        guard case let .spending(body) = spending?.content else { Issue.record("spending"); return }
        #expect(body.categories.map(\.label) == ["Groceries", "Eating out", "Transport"])
        #expect(body.outText == "£586 out" && body.inText == "£1,250 in")
        #expect(body.periodText == "September 2026")
        #expect(body.subscriptionsText == "2 subscriptions, £38 a month")
        let worth = state.sections.first { $0.id == "net_worth" }
        #expect(worth?.sourceLine == "From Monzo and Trading 212")
        guard case let .investments(inv) = state.sections.first(where: { $0.id == "investments" })?.content else {
            Issue.record("investments"); return
        }
        #expect(inv.countText == "8 holdings" && inv.mix.map(\.shareText) == ["79%", "16%", "5%"])
        #expect(inv.holdings.first?.name == "Vanguard S&P 500")
    }

    @Test func monthNamesAreSpelledOut() {
        #expect(ProfileStatsViewModel.monthName("2026-10") == "October 2026")
        #expect(ProfileStatsViewModel.monthName("garbage") == "garbage")
    }

    // MARK: Mock client

    @Test func theMockClientFollowsConnectAndDisconnect() async throws {
        let client = MockClient(data: .recorded)
        #expect(try await client.profileStats().connections.first { $0.id == .sample }?.connected == true)
        _ = try await client.connectTrading212(key: "k", secret: "s")
        let stats = try await client.profileStats()
        #expect(stats.connections.first { $0.id == .trading212 }?.connected == true)
        #expect(stats.connections.first { $0.id == .sample }?.connected == false)
        _ = try await client.disconnectProvider("trading212")
        #expect(try await client.profileStats().connections.allSatisfy { !$0.connected })
    }

    @Test func fixturesDecodeForEveryScenario() {
        for scenario in ProfileFixtures.Scenario.allCases {
            let stats = ProfileFixtures.stats(scenario)
            #expect(stats.connections.count == 5 && stats.sections.count == 4)
        }
    }
}
