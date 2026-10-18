import Foundation
import Observation

/// "Who are you playing as?" Picking a sample student imports it (it stays labelled Sample data) and opens the
/// stats page. Picking You opens the connect step.
@MainActor
@Observable
final class ProfilePickerViewModel {
    static let youID = "you"

    struct API: Sendable {
        var listSamples: @Sendable () async throws -> [SampleStatement]
        var importSample: @Sendable (_ id: String) async throws -> Void
        var profileStats: @Sendable () async throws -> ProfileStats

        static func from(client: any LifelineClient) -> API {
            API(
                listSamples: { try await client.listSamples() },
                importSample: { id in _ = try await client.importSample(id: id) },
                profileStats: { try await client.profileStats() }
            )
        }
    }

    private let api: API
    private(set) var state = ProfilePickerViewState()
    private var samples: [SampleStatement] = []
    private var stats: ProfileStats?

    /// You was picked: the connect step.
    @ObservationIgnored var onPickYou: @MainActor () -> Void = {}
    /// A sample student was imported: the stats page.
    @ObservationIgnored var onPickedSample: @MainActor () -> Void = {}
    @ObservationIgnored var onClose: @MainActor () -> Void = {}

    init(api: API) {
        self.api = api
    }

    var actions: ProfilePickerActions {
        ProfilePickerActions(
            onPick: { [weak self] id in Task { await self?.pick(id) } },
            onClose: { [weak self] in self?.onClose() },
            onRetry: { [weak self] in Task { await self?.load() } },
            onDismissError: { [weak self] in self?.state.errorMessage = nil }
        )
    }

    func load() async {
        // The list of students and the active profile load together. Stats may fail: nobody is active then.
        async let list = try? api.listSamples()
        async let current = try? api.profileStats()
        let (newSamples, newStats) = await (list, current)
        if let newStats { stats = newStats }
        guard let newSamples else {
            if samples.isEmpty { state.phase = .failed(.from(APIError.connectionsUnavailable)) }
            return
        }
        samples = newSamples
        state.cards = Self.makeCards(samples: samples, stats: stats)
        state.phase = .ready
    }

    func pick(_ id: String) async {
        guard state.busyID == nil else { return }
        state.errorMessage = nil
        if id == Self.youID {
            onPickYou()
            return
        }
        state.busyID = id
        defer { state.busyID = nil }
        do {
            try await api.importSample(id)
            stats = try? await api.profileStats()
            state.cards = Self.makeCards(samples: samples, stats: stats)
            onPickedSample()
        } catch {
            state.errorMessage = APIError.map(error).userMessage
        }
    }

    // MARK: Pure mapping

    /// You first, then the students in the server's order. Active: the loaded sample, or You when real data is
    /// connected, or nobody.
    static func makeCards(samples: [SampleStatement], stats: ProfileStats?) -> [ProfilePickerViewState.Card] {
        let sample = stats?.connections.first { $0.id == .sample && $0.connected }
        let hasOwn = stats?.connections.contains { $0.connected && $0.id != .sample } ?? false
        let activeSample = sample?.sampleId
        let you = ProfilePickerViewState.Card(
            id: youID, title: L10n.tr("You"), subtitle: L10n.tr("Your own money"),
            detail: L10n.tr("Monzo, Trading 212, a statement or your numbers"),
            avatar: nil, isYou: true, isActive: sample == nil && hasOwn, badge: nil
        )
        let students = samples.map { s -> ProfilePickerViewState.Card in
            let name = s.name.flatMap { $0.isEmpty ? nil : $0 }
            let kind = [s.title, s.age.map { L10n.tr("age \($0)") }].compactMap { $0 }.joined(separator: ", ")
            return .init(
                id: s.id, title: name ?? s.title, subtitle: name == nil ? (s.age.map { L10n.tr("Age \($0)") } ?? "") : kind,
                detail: [s.uni, s.city].compactMap { $0 }.filter { !$0.isEmpty }.joined(separator: ", "),
                avatar: s.avatar, isYou: false, isActive: s.id == activeSample, badge: L10n.tr("Sample data"),
                isTeam: s.team ?? false
            )
        }
        return [you] + students
    }
}
