"""Penny's scope (ADR 0073): money and student-finance questions, and general student-life questions.

Only questions outside both (coding help, homework answers, celebrity news, recipes with no money angle) get one
fixed friendly line plus 2 related money chips. This module is the cheap first check: a keyword classifier for
clear off-topic requests, before any model call. When it is not sure, the model decides (its `off_topic` flag).

A question with a money word ("cheap recipes", "laptop discount") is never off topic here.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Literal

from lifeline_explain import i18n
from lifeline_explain.safety_intl import MONEY_CONTEXT as _MONEY_INTL

Topic = Literal["code", "homework", "celebrity", "food", "general"]

_MONEY = re.compile(
    r"£|\b(money|budget\w*|cheap\w*|costs?|costing|price[sd]?|pricing|afford\w*|spend\w*|spent|sav(e|es|ing|ings)|"
    r"bank\w*|loans?|rent|bills?|pay|paid|payment|wages?|salary|job|jobs|income|debts?|bursar(y|ies)|grants?|"
    r"scholarships?|fees?|discounts?|deals?|student finance|isa|tax|overdraft|credit|interest|cash|pounds?|"
    r"expensive|refund\w*|subscriptions?|financ\w*)\b|"
    r"\b(prix|coût|budget|argent|bourse|loyer|precio|coste|costo|dinero|beca|alquiler|preço|custo|dinheiro|"
    r"aluguel|renda|prezzo|soldi|affitto|borsa di studio)\b|"
    r"钱|预算|价格|便宜|费用|房租|贷款|奖学金|पैसे|पैसा|बजट|किराया|खर्च|ख़र्च|लोन|छात्रवृत्ति|भाडा|ऋण",
    re.IGNORECASE,
)

_CODE = re.compile(
    r"\b(python|javascript|typescript|java|c\+\+|c#|golang|kotlin|swiftui|sql|html|css|django|leetcode|"
    r"regex|stack ?overflow)\b|"
    r"\b(write|fix|debug|explain|review|refactor|compile|run)\b[^.?!]{0,40}\b(code|script|program|function|"
    r"algorithm)\b|\b(my|this|the) (code|script)\b|\bcoding\b|\bdebug\w*",
    re.IGNORECASE,
)
_HOMEWORK = re.compile(
    r"\b(write|do|finish|complete|answer|solve|draft)\b[^.?!]{0,30}\b(my|this|the|an?|our)\b[^.?!]{0,30}"
    r"\b(essay|homework|assignment|coursework|dissertation|thesis|lab report|problem set|exam questions?|"
    r"equation|quiz answers?)\b|"
    r"\b(fais|faire|écris|écrire) (mes|mon|ma) (devoirs|dissertation|rédaction)\b|"
    r"\b(haz|hacer|escribe|escribir) (mi|mis) (tarea|tareas|ensayo|redacción)\b|"
    r"\b(faça|fazer|escreva|escrever) (meu|minha|meus) (dever|trabalho|redação|ensaio)\b|"
    r"\b(fai|fare|scrivi|scrivere) (i miei|il mio|la mia) (compiti|tema|saggio)\b|"
    r"(帮我|替我)(写|做)[^。？]{0,8}(作业|论文|作文)|(होमवर्क|निबंध|असाइनमेंट)[^।?]{0,20}(लिख|कर) (दो|दीजिए|दें)|"
    r"(गृहकार्य|निबन्ध)[^।?]{0,20}(लेखिदिनु|गरिदिनु)",
    re.IGNORECASE,
)
_CELEBRITY = re.compile(
    r"\b(celebrit(y|ies)|gossip|kardashians?|taylor swift|beyonc[eé]|love island|famous people|who is dating|"
    r"red carpet|royal family gossip|célébrit\w*|people news|celebridad\w*|celebridade\w*|celebrità|"
    r"pettegolez\w*|chisme\w*|fofoca\w*)\b|明星|八卦|सेलिब्रिटी",
    re.IGNORECASE,
)
_FOOD = re.compile(
    r"\b(recipes?|how (do i|to|can i) (cook|bake) (a |an |the )?\w+|ingredients for|recette\w*|recetas?|"
    r"receitas?|ricett\w*)\b|食谱|菜谱|怎么做菜|रेसिपी|पकाने की विधि|पकाउने तरिका",
    re.IGNORECASE,
)

# Student-life words that make a coding, celebrity or food mention a uni question ("a coding society").
_STUDENT_LIFE = re.compile(
    r"\b(societ(y|ies)|club|course|module|workshop|careers?|internships?|campus|uni|university|freshers|"
    r"student union|halls?|canteen|dining hall)\b",
    re.IGNORECASE,
)

_RULES: tuple[tuple[Topic, re.Pattern[str]], ...] = (
    ("homework", _HOMEWORK),
    ("code", _CODE),
    ("celebrity", _CELEBRITY),
    ("food", _FOOD),
)


def _norm(text: str) -> str:
    out = unicodedata.normalize("NFKC", text)
    return "".join(ch for ch in out if unicodedata.category(ch) not in {"Cc", "Cf"}).replace("’", "'")


def has_money_angle(message: str) -> bool:
    msg = _norm(message)
    return bool(_MONEY.search(msg) or _MONEY_INTL.search(msg))


def topic_of(message: str) -> Topic:
    """The off-topic subject of a message (for the chips). "general" when no rule matches."""
    msg = _norm(message)
    for topic, rule in _RULES:
        if rule.search(msg):
            return topic
    return "general"


def off_topic_rule(message: str) -> bool:
    """True for a clear request outside money and student life (coding help, homework answers, celebrity news,
    recipes). Never True when the message has a money angle. Student-life questions never match."""
    topic = topic_of(message)
    if topic == "general" or has_money_angle(message):
        return False
    return topic == "homework" or not _STUDENT_LIFE.search(_norm(message))


def chips(message: str, lang: i18n.Lang) -> list[str]:
    """Exactly 2 related money questions for an off-topic message, in the answer language."""
    return list(i18n.OFF_TOPIC_CHIPS[topic_of(message)][lang])
