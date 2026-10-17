import Foundation
import Testing
@testable import Lifeline

/// ADR 0060: every bundled fixed-content file decodes into its `CachedOp` type,
/// so the disk cache can show it on first launch.
@Suite("Bundled content")
struct BundledContentTests {
    /// Decodes one bundled file as the op's type. Throws the decoding error, so a failure names the field.
    private func decode<T>(_ op: CachedOp<T>) throws -> T? {
        guard let url = Bundle.main.url(forResource: "bundled-" + op.key, withExtension: "json") else { return nil }
        return try DiskCache.decoder.decode(T.self, from: Data(contentsOf: url))
    }

    /// Bundled keys with a known type. A new bundled file must be added here.
    private func decodeKnown(_ key: String) throws -> Bool {
        switch key {
        case CachedOps.characters.key: return try decode(CachedOps.characters) != nil
        case CachedOps.paths.key: return try decode(CachedOps.paths) != nil
        case CachedOps.concepts.key: return try decode(CachedOps.concepts) != nil
        case CachedOps.challenges.key: return try decode(CachedOps.challenges) != nil
        case CachedOps.samples.key: return try decode(CachedOps.samples) != nil
        case CachedOps.sources.key: return try decode(CachedOps.sources) != nil
        default:
            Issue.record("bundled-\(key).json has no CachedOp in this test")
            return false
        }
    }

    @Test func everyBundledFileDecodes() throws {
        let urls = Bundle.main.urls(forResourcesWithExtension: "json", subdirectory: nil) ?? []
        let keys = urls
            .map { $0.deletingPathExtension().lastPathComponent }
            .filter { $0.hasPrefix("bundled-") }
            .map { String($0.dropFirst("bundled-".count)) }
        #expect(!keys.isEmpty, "No Resources/Bundled files in the app bundle")
        for key in keys {
            #expect(try decodeKnown(key), "bundled-\(key).json")
        }
    }

    @Test func fixedContentIsBundled() throws {
        #expect(try decode(CachedOps.characters)?.presets.isEmpty == false)
        #expect(try decode(CachedOps.concepts)?.isEmpty == false)
        #expect(try decode(CachedOps.challenges) != nil)
        #expect(try decode(CachedOps.samples)?.isEmpty == false)
    }

    @Test func diskCacheSeedsSharedOpsFromTheBundle() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let cache = DiskCache(root: root)
        let concepts = await cache.read([Concept].self, key: CachedOps.concepts.key, scope: .shared)
        #expect(concepts?.isEmpty == false)
        // User data is never seeded.
        #expect(await cache.read(Me.self, key: CachedOps.me.key, scope: .user) == nil)
        await cache.clearAll()
    }

    @Test func clearUserKeepsFixedContentAndOwnerChangeWipesUserData() async throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString)
        let cache = DiskCache(root: root)
        await cache.setOwner("usr_a")
        await cache.write(MockExamples.me, key: CachedOps.me.key, scope: .user)
        await cache.write([String](), key: "listTest", scope: .shared)
        #expect(await cache.read(Me.self, key: CachedOps.me.key, scope: .user) != nil)

        await cache.setOwner("usr_a")
        #expect(await cache.read(Me.self, key: CachedOps.me.key, scope: .user) != nil)
        await cache.setOwner("usr_b")
        #expect(await cache.read(Me.self, key: CachedOps.me.key, scope: .user) == nil)

        await cache.write(MockExamples.me, key: CachedOps.me.key, scope: .user)
        await cache.clearUser()
        #expect(await cache.read(Me.self, key: CachedOps.me.key, scope: .user) == nil)
        #expect(await cache.read([String].self, key: "listTest", scope: .shared) != nil)
        await cache.clearAll()
    }
}
