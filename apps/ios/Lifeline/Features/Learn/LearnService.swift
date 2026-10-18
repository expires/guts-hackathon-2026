import Foundation

// Learn course (ADR 0068): the network side of the feature.
// `LiveClient` and `MockClient` conform to `LearnService` (their files, BOSS-owned).
// Tests and previews pass a `MockLearnService` directly.

/// Short names for the generated contract types. ViewModels, the service layer and tests use these. Views never do.
enum LearnWire {
    typealias Path = Components.Schemas.LearnPath
    typealias Unit = Components.Schemas.Unit
    typealias Summary = Components.Schemas.LessonSummary
    typealias Lesson = Components.Schemas.LearnLesson
    typealias Card = Components.Schemas.LessonCard
    typealias Fact = Components.Schemas.LessonFact
    typealias Question = Components.Schemas.LessonQuestion
    typealias Choice = Components.Schemas.LessonChoice
    typealias AttemptResult = Components.Schemas.LessonAttemptResult
    typealias AnswerResult = Components.Schemas.LessonAnswerResult

    /// 409 code for a lesson whose previous lesson is not passed.
    static let lockedCode = "lesson_locked"
}

/// `GET /v1/learn`, `GET /v1/learn/lessons/{id}`, `POST /v1/learn/lessons/{id}/attempts`. Every call sends `language`.
protocol LearnService: Sendable {
    func learnPath(language: AppLanguage) async throws -> LearnWire.Path
    /// Throws `APIError.server(409, "lesson_locked", ...)` for a locked lesson.
    func learnLesson(id: String, language: AppLanguage) async throws -> LearnWire.Lesson
    /// `answers`: question id to choice id.
    func attemptLearnLesson(id: String, answers: [String: String], language: AppLanguage) async throws -> LearnWire.AttemptResult
}

enum LearnServices {
    static func make(for client: any LifelineClient) -> any LearnService {
        if let service = client as? any LearnService { return service }
        return MockLearnService.shared
    }
}

/// Disk cache entries (ADR 0060). The path and lessons hold the user's progress, so they are user data
/// (cleared on sign-out and demo reset). One file per language.
enum LearnCache {
    static func path(_ service: any LearnService, language: AppLanguage) -> CachedOp<LearnWire.Path> {
        CachedOp(key: "getLearnPath." + language.rawValue, scope: .user) { _ in
            try await service.learnPath(language: language)
        }
    }

    static func lesson(_ service: any LearnService, id: String, language: AppLanguage) -> CachedOp<LearnWire.Lesson> {
        CachedOp(key: "getLearnLesson." + id + "." + language.rawValue, scope: .user) { _ in
            try await service.learnLesson(id: id, language: language)
        }
    }

    /// Stores the path from an attempt result, so the next open shows the new progress at once.
    static func store(_ path: LearnWire.Path, language: AppLanguage, in client: any LifelineClient) async {
        await client.diskCache?.write(path, key: "getLearnPath." + language.rawValue, scope: .user)
    }
}
