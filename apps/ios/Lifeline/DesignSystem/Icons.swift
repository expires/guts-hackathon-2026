import SwiftUI

/// The Lifeline icon set (`lifeline-design/screens/Icon.dc.html`), plus Penny the coin.
/// Assets live in `Assets.xcassets/Icons` as SVG with "Preserve Vector Data" and a dark-appearance variant.
/// Each icon has 3 optical stroke weights: 3 px at 48, 2.75 px at 32, 2.5 px at 24.
enum LLIcon: String, CaseIterable, Sendable {
    case tabMoney = "tab-money"
    case tabLife = "tab-life"
    case tabPlay = "tab-play"
    case tabYou = "tab-you"
    case home = "home"
    case car = "car"
    case bank = "bank"
    case card = "card"
    case savings = "savings"
    case pension = "pension"
    case cart = "cart"
    case subscriptions = "subscriptions"
    case bills = "bills"
    case budget = "budget"
    case goal = "goal"
    case investment = "investment"
    case debt = "debt"
    case job = "job"
    case study = "study"
    case health = "health"
    case family = "family"
    case relationships = "relationships"
    case activities = "activities"
    case travel = "travel"
    case pet = "pet"
    case happiness = "happiness"
    case rateRise = "rate-rise"
    case priceRise = "price-rise"
    case jobLoss = "job-loss"
    case payRise = "pay-rise"
    case crash = "crash"
    case flood = "flood"
    case burglary = "burglary"
    case baby = "baby"
    case wedding = "wedding"
    case inheritance = "inheritance"
    case boiler = "boiler"
    case motFail = "mot-fail"
    case age = "age"
    case rewind = "rewind"
    case test = "test"
    case why = "why"
    case check = "check"
    case lesson = "lesson"
    case ribbon = "ribbon"
    case trophy = "trophy"
    case streak = "streak"
    case lock = "lock"
    case demoPay = "demo-pay"
    case statusLive = "status-live"
    case statusCached = "status-cached"
    case statusMock = "status-mock"
    case faceBaby = "face-baby"
    case faceGirl = "face-girl"
    case faceBoy = "face-boy"
    case faceTeen = "face-teen"
    case faceTeenHijab = "face-teen-hijab"
    case faceWomanPuff = "face-woman-puff"
    case faceManBeard = "face-man-beard"
    case facePriya = "face-priya"
    case faceManGlasses = "face-man-glasses"
    case faceBlueHair = "face-blue-hair"
    case faceOlderWoman = "face-older-woman"
    case faceOlderMan = "face-older-man"
    case pennyThinking = "penny-thinking"
    case pennyHappy = "penny-happy"
    case pennyNeutral = "penny-neutral"
    case pennySmiling = "penny-smiling"

    /// Asset name for a display size. Sizes up to 24 use the 24 weight, up to 32 the 32 weight.
    func assetName(size: CGFloat, active: Bool = false) -> String {
        let suffix = size <= 24 ? "-24" : (size <= 32 ? "-32" : "")
        let state = active && isTab ? "-active" : ""
        if rawValue.hasPrefix("penny") { return "icon-" + rawValue }
        return "icon-" + rawValue + state + suffix
    }

    var isTab: Bool { rawValue.hasPrefix("tab-") }

    /// Maps an emoji from the API or a fixture to an icon. The app never shows emoji (handoff rule).
    static func from(emoji: String?, fallback: LLIcon = .activities) -> LLIcon {
        guard let emoji, !emoji.isEmpty else { return fallback }
        if let exact = emojiMap[emoji] { return exact }
        // Drop skin tones and variation selectors, then try again.
        let base = String(String.UnicodeScalarView(emoji.unicodeScalars.filter {
            !(0x1F3FB...0x1F3FF).contains($0.value) && $0.value != 0xFE0F
        }))
        if let match = emojiMap[base] { return match }
        if let first = base.unicodeScalars.first, let single = emojiMap[String(first)] { return single }
        return fallback
    }

    /// Character emoji from the API to a face icon.
    static func face(emoji: String?) -> LLIcon {
        let icon = from(emoji: emoji, fallback: .facePriya)
        return icon.rawValue.hasPrefix("face-") ? icon : .facePriya
    }

    static let emojiMap: [String: LLIcon] = [
        "🙂": .facePriya,
        "👩🏽‍⚕️": .facePriya,
        "👩‍⚕️": .facePriya,
        "🧑‍⚕️": .facePriya,
        "👨🏻‍💼": .faceManGlasses,
        "👨🏻‍🏫": .faceManGlasses,
        "👩🏽": .faceWomanPuff,
        "👩": .faceWomanPuff,
        "👨": .faceManBeard,
        "👷🏼‍♂️": .faceManBeard,
        "👵": .faceOlderWoman,
        "👵🏻": .faceOlderWoman,
        "🧓": .faceOlderMan,
        "👴": .faceOlderMan,
        "👶": .faceBaby,
        "🍼": .baby,
        "👧🏽": .faceGirl,
        "🧒": .faceBoy,
        "🧑🏻": .faceTeen,
        "🧑🏽‍🎓": .faceTeen,
        "🙋": .faceBlueHair,
        "🤷": .faceTeenHijab,
        "🙅": .faceTeenHijab,
        "🧙": .faceBlueHair,
        "🏦": .bank,
        "🏛️": .bank,
        "🏧": .bank,
        "💷": .savings,
        "💰": .savings,
        "💵": .savings,
        "💸": .debt,
        "🪙": .savings,
        "🐖": .savings,
        "🐷": .savings,
        "💳": .card,
        "📈": .investment,
        "📉": .crash,
        "💎": .investment,
        "🧮": .budget,
        "📊": .budget,
        "🧾": .bills,
        "📄": .bills,
        "📜": .bills,
        "📋": .bills,
        "📦": .subscriptions,
        "📺": .subscriptions,
        "🔁": .subscriptions,
        "🔄": .subscriptions,
        "🎟️": .subscriptions,
        "🎫": .subscriptions,
        "🛒": .cart,
        "🛍️": .cart,
        "🏪": .cart,
        "🍜": .family,
        "🍝": .family,
        "🍕": .family,
        "🍔": .family,
        "🍳": .family,
        "🍿": .activities,
        "🎯": .goal,
        "🏁": .goal,
        "🎁": .goal,
        "💱": .investment,
        "🔒": .lock,
        "🔐": .lock,
        "🔑": .home,
        "🛡️": .lock,
        "🛟": .savings,
        "⚖️": .why,
        "🏠": .home,
        "🏡": .home,
        "🏘️": .home,
        "🏚️": .home,
        "🏢": .home,
        "🏗️": .home,
        "🧱": .home,
        "🛋️": .home,
        "🚪": .home,
        "🛏️": .home,
        "🛌": .home,
        "🔧": .boiler,
        "🛠️": .boiler,
        "🔨": .boiler,
        "🔩": .boiler,
        "🧰": .boiler,
        "🔥": .boiler,
        "🧊": .boiler,
        "🥶": .boiler,
        "⚡": .bills,
        "💡": .bills,
        "🔋": .bills,
        "💧": .flood,
        "🌊": .flood,
        "☂️": .flood,
        "🌪️": .flood,
        "🌫️": .flood,
        "🧹": .home,
        "🧺": .home,
        "🕯️": .home,
        "💼": .job,
        "📝": .job,
        "✍️": .job,
        "💻": .job,
        "📞": .job,
        "📟": .job,
        "📨": .job,
        "📬": .job,
        "🪧": .jobLoss,
        "😴": .jobLoss,
        "🚀": .payRise,
        "⬆️": .payRise,
        "⬇️": .jobLoss,
        "🎓": .study,
        "📚": .study,
        "📖": .study,
        "📒": .study,
        "🏫": .study,
        "🧠": .study,
        "🏋️": .health,
        "💪": .health,
        "🏃": .health,
        "🧘": .health,
        "🩺": .health,
        "🏥": .health,
        "💊": .health,
        "😷": .health,
        "🤒": .health,
        "🤧": .health,
        "🤕": .health,
        "🦷": .health,
        "🩹": .health,
        "🚭": .health,
        "🚬": .health,
        "⛑️": .health,
        "🤝": .relationships,
        "💍": .wedding,
        "💑": .relationships,
        "💘": .relationships,
        "💔": .relationships,
        "👨‍👩‍👧": .family,
        "🎈": .family,
        "🧸": .baby,
        "🎂": .family,
        "🎉": .activities,
        "🎊": .activities,
        "🥂": .wedding,
        "⛪": .wedding,
        "🕊️": .inheritance,
        "🤲": .inheritance,
        "🙏": .inheritance,
        "🐶": .pet,
        "🐕": .pet,
        "🦴": .pet,
        "🚗": .car,
        "🚙": .car,
        "🛞": .car,
        "⛽": .car,
        "🅿️": .car,
        "🚲": .travel,
        "🚴": .travel,
        "🛵": .travel,
        "🚌": .travel,
        "🚆": .travel,
        "🚚": .travel,
        "✈️": .travel,
        "🏖️": .travel,
        "🏝️": .travel,
        "🗺️": .travel,
        "🗽": .travel,
        "🎲": .activities,
        "🎰": .activities,
        "🎣": .activities,
        "🎧": .activities,
        "🎬": .activities,
        "🎄": .activities,
        "🧩": .activities,
        "🎗️": .ribbon,
        "✨": .ribbon,
        "🌱": .goal,
        "🌿": .goal,
        "🌼": .goal,
        "⚠️": .crash,
        "🚨": .burglary,
        "💥": .crash,
        "🧨": .crash,
        "🔎": .why,
        "🔍": .why,
        "💬": .why,
        "😐": .faceTeen,
        "😞": .faceTeen,
        "😩": .faceTeen,
        "😰": .faceTeen,
        "😱": .faceTeen,
        "😬": .faceTeen,
        "😕": .faceTeen,
        "😌": .happiness,
        "🙌": .happiness,
        "✅": .check,
        "🆕": .check
    ]
}

/// One icon at a display size. Decorative by default (hidden from VoiceOver).
struct LLIconImage: View {
    let icon: LLIcon
    var size: CGFloat = 24
    var active = false

    init(_ icon: LLIcon, size: CGFloat = 24, active: Bool = false) {
        self.icon = icon
        self.size = size
        self.active = active
    }

    var body: some View {
        Image(icon.assetName(size: size, active: active))
            .resizable()
            .renderingMode(.original)
            .interpolation(.high)
            .frame(width: size, height: size)
            .accessibilityHidden(true)
    }
}

extension Label where Title == Text, Icon == LLIconImage {
    /// Label with a Lifeline icon instead of an SF Symbol.
    init(_ title: String, icon: LLIcon, size: CGFloat = 24) {
        self.init { Text(title) } icon: { LLIconImage(icon, size: size) }
    }
}

extension Button where Label == SwiftUI.Label<Text, LLIconImage> {
    /// Button with a Lifeline icon instead of an SF Symbol.
    init(_ title: String, icon: LLIcon, action: @escaping () -> Void) {
        self.init(action: action) { SwiftUI.Label(title, icon: icon) }
    }
}

/// Chevron used in list rows (the design draws it, it is not in the icon set).
struct Chevron: View {
    var direction: Direction = .right
    enum Direction { case left, right }

    var body: some View {
        Path { p in
            p.move(to: CGPoint(x: 2, y: 2))
            p.addLine(to: CGPoint(x: 10, y: 10))
            p.addLine(to: CGPoint(x: 2, y: 18))
        }
        .stroke(Theme.Palette.ink, style: StrokeStyle(lineWidth: 3, lineCap: .round, lineJoin: .round))
        .frame(width: 12, height: 20)
        .scaleEffect(x: direction == .left ? -1 : 1)
        .accessibilityHidden(true)
    }
}
