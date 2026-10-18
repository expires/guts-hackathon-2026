import Foundation
import Observation

/// The Learn course path (ADR 0068). One instance per Play tab: the Play card and the path screen read it,
/// and each lesson attempt updates it from the server's response.
@MainActor
@Observable
final class LearnPathViewModel {
    /// A lesson the path screen opens.
    struct LessonRoute: Identifiable, Hashable {
        var id: String
        var title: String
    }

    let service: any LearnService
    let isSampleData: Bool
    private let client: (any LifelineClient)?
    private let language: @MainActor () -> AppLanguage
    private(set) var path: LearnWire.Path?
    private(set) var phase: LoadPhase = .loading(.init(message: L10n.tr("Loading your lessons")))
    private(set) var lockedMessage: String?
    /// Set when the player taps an open or passed lesson. The glue presents it.
    var openLesson: LessonRoute?
    @ObservationIgnored var onClose: @MainActor () -> Void = {}
    /// The language of `path`. A change reloads.
    @ObservationIgnored private var loadedLanguage: AppLanguage?
    @ObservationIgnored private var lockedTask: Task<Void, Never>?

    init(
        service: any LearnService,
        client: (any LifelineClient)? = nil,
        isSampleData: Bool = false,
        language: @escaping @MainActor () -> AppLanguage = { .current }
    ) {
        self.service = service
        self.client = client
        self.isSampleData = isSampleData
        self.language = language
    }

    /// The service for this client, with the disk cache when the client has one.
    convenience init(client: any LifelineClient) {
        self.init(service: LearnServices.make(for: client), client: client, isSampleData: client.kind == .mock)
    }

    var state: LearnPathViewState {
        LearnMapping.pathState(path, phase: phase, lockedMessage: lockedMessage, isSampleData: isSampleData)
    }

    var entry: LearnEntryState {
        LearnMapping.entry(path)
    }

    var actions: LearnPathActions {
        LearnPathActions(
            onSelect: { [weak self] id in self?.select(id) },
            onDismissLocked: { [weak self] in self?.lockedMessage = nil },
            onRetry: { [weak self] in Task { await self?.load() } },
            onClose: { [weak self] in self?.onClose() }
        )
    }

    /// Disk first, then network (ADR 0060). The cached path shows at once.
    func load() async {
        let language = language()
        if loadedLanguage != language { path = nil }
        if path == nil { phase = .loading(.init(message: L10n.tr("Loading your lessons"))) }
        do {
            let op = LearnCache.path(service, language: language)
            if let client {
                try await client.load(op) { [weak self] value in self?.apply(value, language: language) }
            } else {
                apply(try await service.learnPath(language: language), language: language)
            }
        } catch {
            if path == nil { phase = .failed(.from(APIError.map(error))) }
        }
    }

    /// A lesson attempt returns the whole path: show it and store it for the next open.
    func apply(_ path: LearnWire.Path, language: AppLanguage? = nil) {
        let language = language ?? self.language()
        self.path = path
        loadedLanguage = language
        phase = .ready
        #if DEBUG
        let missing = LearnMapping.missingSymbols(in: path)
        if !missing.isEmpty { print("Learn: no SF Symbol for", missing.joined(separator: ", ")) }
        #endif
    }

    /// Stores an attempt's path on disk too (the lesson screen calls this after grading).
    func applyAttempt(_ path: LearnWire.Path) {
        let language = language()
        apply(path, language: language)
        if let client { Task { await LearnCache.store(path, language: language, in: client) } }
    }

    func select(_ id: String) {
        // No locks (PENNY_V3_BUILD E1): every lesson opens.
        guard let lesson = LearnMapping.lesson(id, in: path) else { return }
        lockedMessage = nil
        openLesson = LessonRoute(id: lesson.id, title: lesson.title)
    }

    /// Opens the next lesson after a pass ("Next lesson" on the result).
    func openNext(_ id: String) {
        let title = LearnMapping.lesson(id, in: path)?.title ?? ""
        openLesson = LessonRoute(id: id, title: title)
    }

    /// The server refused a lesson (409 `lesson_locked`): show its reason on the path.
    func showLocked(_ message: String) {
        lockedMessage = message
        lockedTask?.cancel()
        lockedTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(4))
            guard !Task.isCancelled else { return }
            self?.lockedMessage = nil
        }
    }

    func unitTitle(for lessonID: String) -> String? {
        path?.units.first { unit in unit.lessons.contains { $0.id == lessonID } }?.title
    }
}
