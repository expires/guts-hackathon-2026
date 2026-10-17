import Foundation

// Instant screens (ADR 0060): the last known response for each read endpoint stays on the phone.
// A screen shows it at once, then a background refresh replaces it quietly.
//
// Usage in a ViewModel:
//     try? await client.load(CachedOps.financeHome) { home in self.apply(home) }
// `onUpdate` runs at once with the disk value (if any), then again with the network value when it differs.

/// Where a cached value lives.
enum CacheScope: String, Sendable {
    /// The signed-in user's data. Cleared on sign-out, demo reset, account delete and a user change.
    case user
    /// Fixed content (characters, paths, concepts, lessons, samples, sources). Same for every user.
    /// Seeded from `Resources/Bundled/bundled-<key>.json` (not sources) until the server copy arrives.
    case shared
}

/// One cacheable read operation. `T` is the client method's return type.
struct CachedOp<T: Codable & Hashable & Sendable>: Sendable {
    /// File name stem. Unique per operation and query.
    let key: String
    let scope: CacheScope
    let fetch: @Sendable (any LifelineClient) async throws -> T
}

/// Every cached read operation. Pass one to `LifelineClient.load(_:onUpdate:)`.
enum CachedOps {
    // User data
    static let me = CachedOp<Me>(key: "getMe", scope: .user) { try await $0.getMe() }
    static let financeHome = CachedOp<FinanceHome>(key: "getFinanceHome", scope: .user) { try await $0.financeHome() }
    static let financeOverview = CachedOp<FinanceOverview>(key: "getFinanceOverview", scope: .user) { try await $0.financeOverview() }
    static let financeProfile = CachedOp<FinanceProfile>(key: "getFinanceProfile", scope: .user) { try await $0.financeProfile() }
    static let nextMove = CachedOp<NextMoveResponse>(key: "getNextMove", scope: .user) { try await $0.nextMove() }
    static let plan = CachedOp<PlanResponse>(key: "getPlan", scope: .user) { try await $0.plan() }
    static let bills = CachedOp<BillsResponse>(key: "listBills", scope: .user) { try await $0.bills() }
    static let subscriptions = CachedOp<SubscriptionsResponse>(key: "listSubscriptions", scope: .user) { try await $0.subscriptions() }
    static let habits = CachedOp<HabitScore>(key: "getHabits", scope: .user) { try await $0.habits() }
    static let circles = CachedOp<[PlayCircle]>(key: "listCircles", scope: .user) { try await $0.listCircles() }
    static let chatThreads = CachedOp<ChatThreadsResponse>(key: "listChatThreads", scope: .user) { try await $0.listChatThreads() }

    /// `month` is YYYY-MM; nil means this month.
    static func spending(month: String? = nil) -> CachedOp<SpendingResponse> {
        CachedOp(key: "getFinanceSpending." + (month ?? "now"), scope: .user) { try await $0.financeSpending(month: month) }
    }

    // Fixed content
    static let characters = CachedOp<CharactersResponse>(key: "listCharacters", scope: .shared) { try await $0.listCharacters(seed: nil) }
    static let paths = CachedOp<[StudentPath]>(key: "listPaths", scope: .shared) { try await $0.listPaths() }
    static let concepts = CachedOp<[Concept]>(key: "listConcepts", scope: .shared) { try await $0.listConcepts() }
    static let challenges = CachedOp<[Challenge]>(key: "listChallenges", scope: .shared) { try await $0.listChallenges() }
    static let samples = CachedOp<[SampleStatement]>(key: "listSamples", scope: .shared) { try await $0.listSamples() }
    static let sources = CachedOp<[SourceStatus]>(key: "listSources", scope: .shared) { try await $0.listSources() }
}

/// Files under `Caches/LifelineCache/{user,shared}/<key>.json`, written with the contract's JSON keys.
/// The user folder remembers whose data it holds (`owner`); a different `GET /v1/me` id wipes it.
actor DiskCache {
    let root: URL
    private let bundle: Bundle
    private let fileManager = FileManager.default

    static let standard = DiskCache(
        root: (FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first
            ?? FileManager.default.temporaryDirectory).appendingPathComponent("LifelineCache", isDirectory: true)
    )

    init(root: URL, bundle: Bundle = .main) {
        self.root = root
        self.bundle = bundle
    }

    func read<T: Decodable>(_ type: T.Type, key: String, scope: CacheScope) -> T? {
        let data = (try? Data(contentsOf: file(key, scope))) ?? (scope == .shared ? bundled(key) : nil)
        guard let data else { return nil }
        return try? Self.decoder.decode(T.self, from: data)
    }

    func write<T: Encodable>(_ value: T, key: String, scope: CacheScope) {
        guard let data = try? Self.encoder.encode(value) else { return }
        let url = file(key, scope)
        try? fileManager.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: url, options: .atomic)
    }

    /// Sign-out, demo reset, account delete: forget the user's data. Fixed content stays.
    func clearUser() {
        try? fileManager.removeItem(at: root.appendingPathComponent(CacheScope.user.rawValue, isDirectory: true))
    }

    /// Everything, including fixed content (the bundle seeds come back).
    func clearAll() {
        try? fileManager.removeItem(at: root)
    }

    /// Records whose data the user folder holds. A different id first clears the folder.
    func setOwner(_ userID: String) {
        let url = file("owner", .user)
        if let current = try? String(contentsOf: url, encoding: .utf8), current == userID { return }
        clearUser()
        try? fileManager.createDirectory(at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? Data(userID.utf8).write(to: url, options: .atomic)
    }

    private func file(_ key: String, _ scope: CacheScope) -> URL {
        let safe = String(key.map { $0.isLetter || $0.isNumber || $0 == "." || $0 == "-" ? $0 : "_" })
        return root.appendingPathComponent(scope.rawValue, isDirectory: true).appendingPathComponent(safe + ".json")
    }

    /// `Resources/Bundled/bundled-<key>.json` (from `tools/record_mock.py --bundled`).
    private func bundled(_ key: String) -> Data? {
        guard let url = bundle.url(forResource: "bundled-" + key, withExtension: "json") else { return nil }
        return try? Data(contentsOf: url)
    }

    static let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.dateEncodingStrategy = .iso8601
        return encoder
    }()

    /// ISO 8601 date-times with or without a time zone (same rule as the contract examples).
    static let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.dateDecodingStrategy = .custom { decoder in
            let raw = try decoder.singleValueContainer().decode(String.self)
            let withZone = ISO8601DateFormatter()
            if let date = withZone.date(from: raw) { return date }
            withZone.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
            if let date = withZone.date(from: raw) { return date }
            let withoutZone = ISO8601DateFormatter()
            withoutZone.formatOptions = [.withFullDate, .withTime, .withColonSeparatorInTime, .withDashSeparatorInDate]
            withoutZone.timeZone = TimeZone(identifier: "UTC")
            if let date = withoutZone.date(from: raw) { return date }
            throw DecodingError.dataCorrupted(.init(codingPath: decoder.codingPath, debugDescription: "Bad date \(raw)"))
        }
        return decoder
    }()
}

extension LifelineClient {
    /// Cached first, then fresh (ADR 0060).
    ///
    /// 1. If the disk has a value, `onUpdate` runs with it at once.
    /// 2. The network value replaces it on disk. `onUpdate` runs again only when it differs.
    ///
    /// Throws only when nothing could be shown: no disk value and the network call failed.
    /// With a disk value, a network failure is silent (the screen keeps the cached data).
    /// `MockClient` has no disk cache: it calls `onUpdate` once with the mock value.
    func load<T>(_ op: CachedOp<T>, onUpdate: @escaping @MainActor @Sendable (T) -> Void) async throws {
        let disk = diskCache
        var shown: T?
        if let disk, let cached = await disk.read(T.self, key: op.key, scope: op.scope) {
            shown = cached
            await onUpdate(cached)
        }
        let fresh: T
        do {
            fresh = try await op.fetch(self)
        } catch {
            if shown == nil { throw error }
            return
        }
        if let disk {
            if let me = fresh as? Me { await disk.setOwner(me.id) }
            await disk.write(fresh, key: op.key, scope: op.scope)
        }
        if fresh != shown { await onUpdate(fresh) }
    }

    /// The value on disk, without a network call. Nil for `MockClient` or when nothing is stored.
    func cached<T>(_ op: CachedOp<T>) async -> T? {
        await diskCache?.read(T.self, key: op.key, scope: op.scope)
    }

    /// Fetches and stores without a callback (launch prefetch).
    func refresh<T>(_ op: CachedOp<T>) async {
        let fresh = try? await op.fetch(self)
        guard let fresh, let disk = diskCache else { return }
        if let me = fresh as? Me { await disk.setOwner(me.id) }
        await disk.write(fresh, key: op.key, scope: op.scope)
    }
}
