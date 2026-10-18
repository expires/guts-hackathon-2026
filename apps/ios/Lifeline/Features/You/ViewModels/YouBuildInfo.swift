import Foundation

/// "Version" row on the You tab: app name, version, checkpoint, build time and features.
/// Read from Info.plist keys set by build settings (`project.yml`):
/// `LifelineCheckpoint`, `LifelineBuildTime` (ISO 8601), `LifelineFeatures` (comma-separated),
/// `CFBundleShortVersionString`, plus the bundle id (".dev" suffix means "<product> Dev").
/// Missing keys are left out of the row.
struct YouBuildInfo: Equatable, Sendable {
    /// "Penny" or "Penny Dev" (`Brand.productName`).
    var appName: String
    /// "1.0".
    var version: String
    /// "3". Nil when the key is missing or empty.
    var checkpoint: String?
    /// "17 Oct 2026, 18:04". Nil when the key is missing, empty or not ISO 8601.
    var builtText: String?
    var features: [String]
    /// `CFBundleVersion`, for example "12". Nil when missing.
    var build: String? = nil

    /// "Penny 1.0 (build 12)", or "Penny 1.0" without a build number.
    var title: String {
        "\(appName) \(version)" + (build.map { " (build \($0))" } ?? "")
    }

    /// Only the lines that have a value: "Checkpoint 3", "Built 17 Oct 2026, 18:04", "Features: Penny, Accounts".
    var detailLines: [String] {
        var lines: [String] = []
        if let checkpoint { lines.append(L10n.tr("Checkpoint \(checkpoint)")) }
        if let builtText { lines.append(L10n.tr("Built \(builtText)")) }
        if !features.isEmpty { lines.append("Features: " + features.joined(separator: ", ")) }
        return lines
    }

    static func current(bundle: Bundle = .main) -> YouBuildInfo {
        make(info: bundle.infoDictionary ?? [:], bundleID: bundle.bundleIdentifier)
    }

    /// Pure mapping, used by tests and fixtures.
    static func make(info: [String: Any], bundleID: String?, timeZone: TimeZone = .current) -> YouBuildInfo {
        func value(_ key: String) -> String? {
            guard let text = (info[key] as? String)?.trimmingCharacters(in: .whitespacesAndNewlines),
                  !text.isEmpty, !text.hasPrefix("$(") else { return nil }
            return text
        }
        let isDev = bundleID?.hasSuffix(".dev") ?? false
        let features = value("LifelineFeatures")?
            .split(separator: ",")
            .map { $0.trimmingCharacters(in: .whitespaces) }
            .filter { !$0.isEmpty } ?? []
        return YouBuildInfo(
            appName: isDev ? "\(Brand.productName) Dev" : Brand.productName,
            version: value("CFBundleShortVersionString") ?? "1.0",
            checkpoint: value("LifelineCheckpoint"),
            builtText: value("LifelineBuildTime").flatMap { builtText($0, timeZone: timeZone) },
            features: features,
            build: value("CFBundleVersion")
        )
    }

    /// ISO 8601 (with or without fractional seconds) to "17 Oct 2026, 18:04".
    static func builtText(_ iso: String, timeZone: TimeZone) -> String? {
        let plain = ISO8601DateFormatter()
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        guard let date = plain.date(from: iso) ?? fractional.date(from: iso) else { return nil }
        let out = DateFormatter()
        out.locale = Locale(identifier: "en_GB")
        out.timeZone = timeZone
        out.dateFormat = "d MMM yyyy, HH:mm"
        return out.string(from: date)
    }
}
