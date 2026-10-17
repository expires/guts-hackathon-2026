import Foundation
import Observation

/// Shared state for one player's running game. ViewModels read it and call its methods.
/// Views never see it (ADR 0011).
@MainActor
@Observable
final class GameSession {
    enum Phase: Equatable {
        case selecting
        case playing
    }

    let client: any LifelineClient

    private(set) var phase: Phase = .selecting
    private(set) var life: Life?
    private(set) var lastOutcome: Outcome?
    /// Lesson from the last result. The Lesson screen presents it, then clears it.
    var pendingLesson: Lesson?
    private(set) var isBusy = false
    /// Increments after each successful AGE. Drives `.sensoryFeedback`.
    private(set) var ageCount = 0
    var errorMessage: String?

    /// Entitlements. The Store feature sets them after a demo purchase.
    var ownsGodMode = false
    var hasRewindPass = false

    init(client: any LifelineClient) {
        self.client = client
    }

    /// True when the client returns canned data. Screens then show a "Sample data" badge.
    var usesSampleData: Bool { client.kind == .mock }

    /// The first open event. The event sheet shows it. AGE is blocked while it exists.
    var activeEvent: LifeEvent? { life?.pendingEvents.first }

    var canAge: Bool {
        guard let life else { return false }
        return life.alive && life.pendingEvents.isEmpty && !isBusy
    }

    /// Starts a life. Returns true on success.
    @discardableResult
    func startLife(_ request: CreateLifeRequest) async -> Bool {
        guard !isBusy else { return false }
        isBusy = true
        defer { isBusy = false }
        do {
            life = try await client.createLife(request)
            lastOutcome = nil
            pendingLesson = nil
            ageCount = 0
            phase = .playing
            return true
        } catch {
            errorMessage = APIError.map(error).userMessage
            return false
        }
    }

    /// Advances one year.
    func age() async {
        guard let life, canAge else { return }
        isBusy = true
        defer { isBusy = false }
        do {
            let result = try await client.age(lifeID: life.id)
            self.life = result.life
            lastOutcome = nil
            if let lesson = result.lesson { pendingLesson = lesson }
            ageCount += 1
        } catch {
            errorMessage = APIError.map(error).userMessage
            await refreshLife()
        }
    }

    /// Answers an open event.
    func choose(choiceID: String, eventID: String) async {
        guard let life, !isBusy else { return }
        isBusy = true
        defer { isBusy = false }
        do {
            let result = try await client.choose(lifeID: life.id, eventID: eventID, choiceID: choiceID)
            self.life = result.life
            lastOutcome = result.outcome
            if let lesson = result.lesson { pendingLesson = lesson }
        } catch {
            errorMessage = APIError.map(error).userMessage
            await refreshLife()
        }
    }

    /// Runs a tab action from `available_actions`.
    func act(tab: ActionRequest.TabPayload, actionID: String) async {
        guard let life, !isBusy else { return }
        isBusy = true
        defer { isBusy = false }
        do {
            let result = try await client.act(lifeID: life.id, request: .init(tab: tab, actionId: actionID))
            self.life = result.life
            lastOutcome = result.outcome
            if let lesson = result.lesson { pendingLesson = lesson }
        } catch {
            errorMessage = APIError.map(error).userMessage
            await refreshLife()
        }
    }

    /// Goes back to a past decision. Returns the result so the caller can show abandoned vs new.
    func rewind(decisionID: String) async -> RewindResult? {
        guard let life, !isBusy else { return nil }
        isBusy = true
        defer { isBusy = false }
        do {
            let result = try await client.rewind(lifeID: life.id, decisionID: decisionID)
            self.life = result.life
            lastOutcome = nil
            return result
        } catch {
            errorMessage = APIError.map(error).userMessage
            return nil
        }
    }

    /// Opens a stored life, for example a "Test it" option or a life from the Play tab.
    /// Returns true on success.
    @discardableResult
    func openLife(id: String) async -> Bool {
        guard !isBusy else { return false }
        isBusy = true
        defer { isBusy = false }
        do {
            life = try await client.getLife(id: id)
            lastOutcome = nil
            pendingLesson = nil
            ageCount = 0
            phase = .playing
            return true
        } catch {
            errorMessage = APIError.map(error).userMessage
            return false
        }
    }

    /// Leaves the current life and goes back to character select.
    func newLife() {
        life = nil
        lastOutcome = nil
        pendingLesson = nil
        phase = .selecting
    }

    func dismissOutcome() {
        lastOutcome = nil
    }

    /// Reloads the life after an error so the screen matches the server (for example after a 409).
    private func refreshLife() async {
        guard let id = life?.id, let fresh = try? await client.getLife(id: id) else { return }
        life = fresh
    }
}

extension GameSession {
    /// Session that already has a life, for the Playground and tests.
    static func preloaded(client: any LifelineClient = MockClient(), life: Life) -> GameSession {
        let session = GameSession(client: client)
        session.life = life
        session.phase = .playing
        return session
    }
}
