import Foundation

/// App-wide feature flags (ADR 0072). Shared by every feature; moved from Features/Rooms by the iOS CUT worker.
enum FeatureFlags {
    /// PENNY_V3_BUILD.md F ("The cut"): cut features keep their code and tests, but their entry points
    /// show only when this is true. False in every build. The launch argument `-showsCutFeatures` sets it
    /// for a local check.
    static let showsCutFeatures: Bool = ProcessInfo.processInfo.arguments.contains("-showsCutFeatures")
}
