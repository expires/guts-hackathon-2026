import Foundation
import Observation

/// Circles (ADR 0052): friends share habit ratios and improvement, never amounts.
@MainActor
@Observable
final class CirclesViewModel {
    let service: any PlayService
    let isSampleData: Bool
    private(set) var circles: [PlayWire.Circle] = []
    private(set) var phase: LoadPhase = .loading(.init(message: L10n.tr("Loading your circles")))
    private(set) var selectedID: String?
    private(set) var newName = ""
    private(set) var joinCode = ""
    private(set) var busyText: String?
    private(set) var errorText: String?

    init(service: any PlayService, isSampleData: Bool) {
        self.service = service
        self.isSampleData = isSampleData
    }

    var state: CirclesViewState {
        GameMapping.circles(
            circles, phase: phase, selectedID: selectedID, newName: newName, joinCode: joinCode,
            busyText: busyText, errorText: errorText, isSampleData: isSampleData
        )
    }

    var actions: CirclesActions {
        CirclesActions(
            onSelect: { [weak self] in self?.selectedID = $0 },
            onNameChange: { [weak self] in self?.newName = String($0.prefix(40)) },
            onCreate: { [weak self] in Task { await self?.create() } },
            onJoinCodeChange: { [weak self] in self?.joinCode = CircleCode.normalise($0) },
            onJoin: { [weak self] in Task { await self?.join() } },
            onLeave: { [weak self] id in Task { await self?.leave(id) } },
            onRetry: { [weak self] in Task { await self?.load() } }
        )
    }

    /// Disk first, then network (ADR 0060): the list shows at once when it was loaded before.
    func load() async {
        if circles.isEmpty { phase = .loading(.init(message: L10n.tr("Loading your circles"))) }
        do {
            try await service.loadCircles { [weak self] circles in
                self?.circles = circles
                self?.phase = .ready
            }
        } catch {
            phase = .failed(.from(APIError.map(error)))
        }
    }

    func create() async {
        let name = newName.trimmingCharacters(in: .whitespaces)
        guard !name.isEmpty, busyText == nil else { return }
        await run(L10n.tr("Making your circle")) {
            let circle = try await self.service.createCircle(name: name)
            self.upsert(circle)
            self.newName = ""
            self.selectedID = circle.id
        }
    }

    func join() async {
        guard CircleCode.isValid(joinCode), busyText == nil else { return }
        let code = joinCode
        await run(L10n.tr("Joining circle \(code)")) {
            let circle = try await self.service.joinCircle(code: code)
            self.upsert(circle)
            self.joinCode = ""
            self.selectedID = circle.id
        }
    }

    func leave(_ id: String) async {
        await run(L10n.tr("Leaving the circle")) {
            try await self.service.leaveCircle(id: id)
            self.circles.removeAll { $0.id == id }
            if self.selectedID == id { self.selectedID = nil }
        }
    }

    private func upsert(_ circle: PlayWire.Circle) {
        if let index = circles.firstIndex(where: { $0.id == circle.id }) {
            circles[index] = circle
        } else {
            circles.append(circle)
        }
    }

    private func run(_ busy: String, _ work: @MainActor () async throws -> Void) async {
        busyText = busy
        errorText = nil
        defer { busyText = nil }
        do {
            try await work()
        } catch {
            errorText = APIError.map(error).userMessage
        }
    }
}
