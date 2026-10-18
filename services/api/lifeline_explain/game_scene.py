"""Penny on game screens: a Life event and a room round (Same Decision, Money Quiz).

Rules (prompt AND code):
- Answer from the GAME DATA only. Its numbers are game numbers from the engine (event choices, game money).
- Multiplayer (ChatContext.multiplayer, or any room round): explain each option's trade-off, never pick one.
  `guard_bubbles` drops a sentence that recommends a specific option, in all 8 app languages.
- A room round before its reveal: option labels and context text only, nothing about the outcomes.
- An open Money Quiz question: explain the idea only. A sentence that names a choice or gives the answer is dropped.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

from lifeline_contracts.chat import ChatContext, ChatFact
from lifeline_contracts.domain import SourceRef
from lifeline_explain import i18n
from lifeline_explain import safety_intl as intl
from lifeline_explain.chat_tools import GameScene, ToolOutput, source_key

GAME_SCREENS = frozenset({"life_event", "room_round"})
ROOM_TOOL = "room_round"
BubbleKind = Literal["answer", "caveat", "question", "general_knowledge"]

GAME_NUMBERS: dict[i18n.Lang, str] = {
    "en": "game numbers",
    "fr": "chiffres du jeu",
    "es": "cifras del juego",
    "pt": "números do jogo",
    "it": "numeri del gioco",
    "zh-Hans": "游戏数字",
    "hi": "गेम के आंकड़े",
    "ne": "खेलका अंकहरू",
}

NO_PICK_TEXT: dict[i18n.Lang, str] = {
    "en": "I cannot pick for you in a group game. Each option has its own trade-off, so compare the game numbers "
          "and choose what fits your plan.",
    "fr": "Je ne peux pas choisir pour toi dans une partie à plusieurs. Chaque option a son compromis, compare les "
          "chiffres du jeu et choisis ce qui te convient.",
    "es": "No puedo elegir por ti en una partida en grupo. Cada opción tiene su compromiso, compara las cifras del "
          "juego y elige lo que encaje con tu plan.",
    "pt": "Não posso escolher por você num jogo em grupo. Cada opção tem a sua troca, compare os números do jogo e "
          "escolha o que combina com o seu plano.",
    "it": "Non posso scegliere per te in una partita di gruppo. Ogni opzione ha il suo compromesso, confronta i "
          "numeri del gioco e scegli quello che fa per te.",
    "zh-Hans": "在多人游戏里我不能替你选。每个选项都有取舍，比较一下游戏数字，选适合你计划的那个。",
    "hi": "ग्रुप गेम में मैं आपके लिए नहीं चुन सकती। हर विकल्प में कुछ मिलता है और कुछ छूटता है, गेम के आंकड़े "
          "देखें और अपनी योजना के हिसाब से चुनें।",
    "ne": "समूह खेलमा म तपाईंको लागि छान्न सक्दिनँ। हरेक विकल्पमा केही पाइन्छ र केही छुट्छ, खेलका अंकहरू हेर्नुहोस् "
          "र आफ्नो योजनासँग मिल्ने छान्नुहोस्।",
}  # fmt: skip

QUIZ_OPEN_TEXT: dict[i18n.Lang, str] = {
    "en": "I cannot give the answer while the question is open. Think about what the question is testing, and "
          "I can explain it after the reveal.",
    "fr": "Je ne peux pas donner la réponse tant que la question est ouverte. Réfléchis à ce qu'elle teste, je "
          "t'explique après la révélation.",
    "es": "No puedo dar la respuesta mientras la pregunta está abierta. Piensa en lo que pone a prueba y te lo "
          "explico después de la revelación.",
    "pt": "Não posso dar a resposta enquanto a pergunta está aberta. Pense no que ela testa, e eu explico depois "
          "da revelação.",
    "it": "Non posso dare la risposta mentre la domanda è aperta. Pensa a cosa mette alla prova, te lo spiego "
          "dopo la rivelazione.",
    "zh-Hans": "题目还在作答时我不能给出答案。想想这道题考的是什么，揭晓后我再给你解释。",
    "hi": "सवाल खुला है, तब तक मैं जवाब नहीं बता सकती। सोचें कि सवाल क्या जाँच रहा है, जवाब खुलने के बाद मैं "
          "समझा दूँगी।",
    "ne": "प्रश्न खुला रहँदा म उत्तर दिन सक्दिनँ। प्रश्नले के जाँच्दैछ सोच्नुहोस्, उत्तर खुलेपछि म बुझाइदिन्छु।",
}  # fmt: skip


def is_game_screen(rc: ChatContext | None) -> bool:
    return rc is not None and rc.screen in GAME_SCREENS


def no_pick(rc: ChatContext | None) -> bool:
    """Penny never picks an option: a multiplayer screen, or any room round (always played with others)."""
    return rc is not None and (rc.multiplayer or rc.screen == "room_round")


def rules_line(rc: ChatContext, lang: i18n.Lang, scene: GameScene | None) -> str:
    """Per-turn game rules for the user turn (the static system prompt has the general rule)."""
    term = GAME_NUMBERS[lang]
    parts = [
        f"GAME SCREEN ({rc.screen}): answer in 1 or 2 bubbles. Explain the trade-off of each option: what you get "
        f"and what you give up. Use only numbers from GAME DATA and call them \"{term}\". Never use or mention the "
        "user's real money.",
    ]
    if no_pick(rc):
        parts.append("MULTIPLAYER: never recommend, pick or rank an option, and never say which one is best. "
                     "The player decides.")
    if scene is not None and scene.tool == ROOM_TOOL and not scene.revealed:
        parts.append("BEFORE THE REVEAL: say nothing about the outcomes or the future game money of any option.")
    if scene is not None and scene.quiz_open:
        parts.append("QUIZ QUESTION OPEN: never give, hint at or rule out an answer. Explain the idea behind the "
                     "question only.")
    if scene is None:
        parts.append("No game data could be loaded: explain the kind of trade-off in words, with no numbers.")
    return " ".join(parts)


# ---------- the no-pick and quiz guard (code, all 8 languages) ----------

_BEST = r"(best|better|right|smartest|smarter|wisest|wiser|safest|safer|winning|correct|stronger|clear)"
_RECOMMEND = re.compile(
    # en
    r"\b(i('d| would| will)? (pick|choose|go (with|for)|recommend|suggest|take|vote for)|i recommend|"
    r"my (pick|choice|vote|recommendation|advice)|you should (pick|choose|go (with|for)|take|select|vote)|"
    rf"(is|are|be|seems?|looks?) (the |a )?{_BEST} (option|choice|pick|move|one|answer|bet|call)|"
    rf"the {_BEST} (option|choice|pick|move|one|answer|bet) is|"
    r"(correct|right) answer|answer is|is correct|comes out (best|ahead|on top)|go for it)\b|"
    r"^\s*(pick|choose|go (with|for)|take|select|opt for|stick with|vote for)\b|"
    # fr
    r"\b(je (prendrais|choisirais|recommande|conseille|suggère)|optez|tu devrais|vous devriez|"
    r"meilleure? (option|choix|réponse)|bonne réponse|la réponse est)\b|^\s*(choisis|choisissez|prends|prenez)\b|"
    # es
    r"\b(yo (elegiría|escogería|tomaría|iría)|recomiendo|te recomiendo|deberías|la mejor (opción|elección|respuesta)|"
    r"respuesta correcta|la respuesta es)\b|^\s*(elige|elija|escoge|opta por)\b|"
    # pt
    r"\b(eu (escolheria|ficaria com|iria)|recomendo|você deveria|deverias|a melhor (opção|escolha|resposta)|"
    r"resposta (certa|correta)|a resposta é)\b|^\s*(escolha|escolhe|opte por)\b|"
    # it
    r"\b(sceglierei|consiglio|ti consiglio|dovresti|la (scelta|opzione|risposta) migliore|risposta (giusta|corretta)|"
    r"la risposta è)\b|^\s*(scegli|opta per)\b|"
    # zh, hi, ne (no word boundaries in these scripts)
    r"我(会)?选|应该选|你选|推荐|建议你|最好的选[择项]|答案是|正确答案|"
    r"चुनें|चुनिए|चुनो|चुनूँगी|चुनूंगी|चुनूँगा|सबसे अच्छा विकल्प|सबसे बढ़िया विकल्प|सही जवाब|सही उत्तर|जवाब है|उत्तर है|"
    r"छान्नुहोस्|सिफारिस|सबैभन्दा राम्रो विकल्प|उत्तर हो|लिनुपर्छ",
    re.IGNORECASE,
)
# "If you pick X, you keep £300" explains a trade-off; the conditional clause is not a recommendation.
_CONDITIONAL = re.compile(
    r"\b(if|when|si|se|cuando|quando|wenn)\b[^,;:]*|(如果|假如|要是)[^，,;；]*|(अगर|यदि|जब)[^,;।]*|[^,;।]*(भने)",
    re.IGNORECASE,
)


_OPTION_REF = re.compile(
    r"\b((option|choice|answer|opción|opção|opzione|choix|réponse|respuesta|resposta|risposta) ?[a-d1-4]|"
    r"(the )?(first|second|third|fourth|last|former|latter)( one| option| choice)?|"
    r"(la |le )?(premi(er|ère)|deuxième|second(e)?|dernière?)|"
    r"(la |el )?(primer[ao]?|segund[ao]|tercer[ao]?|últim[ao])|"
    r"(a |o )?(primeir[ao]|segund[ao]|terceir[ao]|últim[ao])|"
    r"(la |il )?(prim[ao]|second[ao]|terz[ao]|ultim[ao]))\b|"
    r"第一|第二|第三|第四|选项|पहला|पहली|दूसरा|दूसरी|तीसरा|विकल्प|पहिलो|दोस्रो|तेस्रो",
    re.IGNORECASE,
)


def _norm(text: str) -> str:
    out = unicodedata.normalize("NFKC", text).lower().replace("’", "'")
    return re.sub(r"\s+", " ", out).strip()


def _names_option(sentence: str, options: tuple[str, ...]) -> bool:
    s = _norm(sentence)
    for label in options:
        lab = _norm(label).strip(" .?!\"'")
        if len(lab) < 2:
            continue
        if re.search(rf"(?<![a-z0-9]){re.escape(lab)}(?![a-z0-9])", s):
            return True
    return False


def recommends_option(sentence: str, options: tuple[str, ...]) -> bool:
    """A sentence that tells the player which option to take: a recommend phrase plus a named or numbered option."""
    if not _RECOMMEND.search(_CONDITIONAL.sub(" ", _norm(sentence))):
        return False
    return _names_option(sentence, options) or bool(_OPTION_REF.search(_norm(sentence)))


def leaks_quiz_answer(sentence: str, options: tuple[str, ...]) -> bool:
    """Open quiz question: any sentence that names a choice, or says what the answer is, is dropped."""
    return _names_option(sentence, options) or recommends_option(sentence, options)


@dataclass(frozen=True)
class Guard:
    """Code checks on game screens. `no_pick`: multiplayer. `quiz_open`: an open Money Quiz question."""

    options: tuple[str, ...]
    no_pick: bool = False
    quiz_open: bool = False

    @property
    def active(self) -> bool:
        return self.no_pick or self.quiz_open

    def bad(self, sentence: str) -> bool:
        if self.quiz_open and leaks_quiz_answer(sentence, self.options):
            return True
        return self.no_pick and recommends_option(sentence, self.options)

    def changes(self, text: str) -> bool:
        return any(self.bad(s) for s in intl.SENTENCES.split(text) if s.strip())


def make_guard(rc: ChatContext | None, scene: GameScene | None) -> Guard | None:
    options = scene.options if scene is not None else ()
    if scene is None and rc is not None and rc.screen == "room_round":
        return Guard(options, no_pick=True)
    guard = Guard(options, no_pick=no_pick(rc), quiz_open=bool(scene and scene.quiz_open))
    return guard if guard.active else None


def guard_bubbles(
    bubbles: list[tuple[BubbleKind, str]], guard: Guard, lang: i18n.Lang
) -> list[tuple[BubbleKind, str]]:
    """Drop every sentence that picks an option (multiplayer) or gives away an open quiz answer. With nothing left,
    a fixed reply in the answer language."""
    out: list[tuple[BubbleKind, str]] = []
    for kind, text in bubbles:
        sentences = [s for s in intl.SENTENCES.split(text) if s.strip()]
        keep = [s for s in sentences if not guard.bad(s)]
        if len(keep) == len(sentences):
            out.append((kind, text))
        elif keep:
            out.append((kind, " ".join(keep)))
    if not any(k != "question" for k, _ in out):
        fixed = QUIZ_OPEN_TEXT[lang] if guard.quiz_open else NO_PICK_TEXT[lang]
        out = [("answer", fixed), *out][:2]
    return out


# ---------- scene builders (pure; W4 loads the data and checks access) ----------

_NUM = re.compile(r"(£)?(\d[\d,]*(?:\.\d+)?)(%)?")


def text_facts(prefix: str, texts: dict[str, str], source_id: str | None) -> list[ChatFact]:
    """Numbers written in engine text (event text, choice hints, a round's context) become facts, so Penny may
    repeat them. Same id scheme as the engine tools: `<prefix>.text.<path>.n<i>`."""
    out: list[ChatFact] = []
    for path, text in texts.items():
        for i, (pound, num, pct) in enumerate(_NUM.findall(text or ""), 1):
            value = float(num.replace(",", ""))
            unit: Any = "gbp" if pound else "percent" if pct else (
                "date_year" if value.is_integer() and 1900 <= value <= 2100 else "count")
            out.append(ChatFact(id=f"{prefix}.text.{path}.n{i}", value=value, unit=unit,
                                label=f"Number in {path.replace('.', ' ')}"[:120], source_id=source_id))
    return out


def room_decision_scene(item: dict[str, Any], revealed: bool) -> GameScene:
    """A Same Decision round from the room's server-side state. Before the reveal: the prompt and the option labels
    only. After it: each option's outcome in game money (facts)."""
    prompt = item.get("prompt") or {}
    ref = SourceRef(source="sim", series_id="same_decision", status="live", note="Game money, simulated")
    sid = source_key(ref)
    options = [{"id": str(o.get("id")), "label": str(o.get("label") or "")} for o in prompt.get("options") or []]
    labels = {o["id"]: o["label"] for o in options}
    result: dict[str, Any] = {
        "game": "same_decision", "year": prompt.get("year"), "context": prompt.get("context") or "",
        "question": prompt.get("text") or "", "options": options, "revealed": revealed,
    }  # fmt: skip
    facts = text_facts("room", {"context": result["context"], "question": result["question"]}, sid)
    if isinstance(prompt.get("year"), int):
        facts.append(ChatFact(id="room.year", value=float(prompt["year"]), unit="date_year",
                              label="Year of the decision", source_id=sid))  # fmt: skip
    if revealed:
        outcomes = []
        for o in item.get("outcomes") or []:
            oid = str(o.get("option_id"))
            change = float(o.get("game_money_change") or 0.0)
            outcomes.append({"option_id": oid, "label": labels.get(oid, oid), "game_money_change": round(change, 2),
                             "note": str(o.get("note") or "")})  # fmt: skip
            facts.append(ChatFact(id=f"room.{oid}.game_money_change", value=round(change, 2), unit="gbp",
                                  label=f"Game money change: {labels.get(oid, oid)}"[:120], source_id=sid))
        result["outcomes"] = outcomes
    out = ToolOutput(result=result, facts=facts, sources=[ref])
    return GameScene(tool=ROOM_TOOL, output=out, options=tuple(o["label"] for o in options), revealed=revealed)


def room_quiz_scene(item: dict[str, Any], revealed: bool) -> GameScene:
    """A Money Quiz question. While it is open: the question and its choices, never the correct one."""
    q = item.get("question") or {}
    choices = [str(c.get("text") or "") for c in q.get("choices") or []]
    ref = SourceRef(source="facts_table", series_id="money_quiz", status="cached")
    result: dict[str, Any] = {"game": "money_quiz", "question": q.get("text") or "", "choices": choices,
                              "source_label": q.get("source_label"), "answer_open": not revealed}  # fmt: skip
    if revealed:
        correct = next((str(c.get("text")) for c in q.get("choices") or [] if c.get("id") == item.get("correct")), None)
        result["correct_choice"] = correct
        result["explanation"] = item.get("explanation")
    # Numbers in the question text are facts; numbers in the choices are not (they could give the answer away).
    facts = text_facts("quiz", {"question": result["question"]}, source_key(ref))
    out = ToolOutput(result=result, facts=facts, sources=[ref])
    return GameScene(tool=ROOM_TOOL, output=out, options=tuple(choices), quiz_open=not revealed, revealed=revealed)


def life_event_scene(out: ToolOutput) -> GameScene:
    """The event_choices result for the open Life event (event text, choices, projections and their facts)."""
    result = out.result if isinstance(out.result, dict) else {}
    labels = tuple(str(c.get("label") or "") for c in result.get("choices") or [] if isinstance(c, dict))
    return GameScene(tool="event_choices", output=out, options=labels)
