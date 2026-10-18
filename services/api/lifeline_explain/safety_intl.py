"""Safety patterns for the 7 non-English app languages (ADR 0063, V6 final F-2, F-3, F-4).

Machine-written, errs on the side of care. Latin-script patterns use word boundaries; Chinese and Devanagari
patterns are plain substrings (word boundaries do not work for those scripts).
Brand names and tickers (Tesla, Bitcoin, NVDA) are language-neutral; their local spellings are listed too.
"""

from __future__ import annotations

import re

# ---------- F-2: picks ----------

# Buy, sell or invest verbs.
PICK_VERBS = re.compile(
    r"\b(achet\w*|vend(s|ez|re)|investi(r|ssez|ssons|s)|"  # fr
    r"compr(a|as|e|es|en|ar|are|ate|ad|o|ei|ou|i|ando)|vend(a|e|er|ere|i|o)|"  # es, pt, it
    r"invi[eé]rt\w*|invertir|invest(a|ir|ire|i|o)"  # es, pt, it
    r")\b|买|購買|购买|入手|卖出|抛售|投资|खरीद|ख़रीद|बेच|निवेश|किन्|लगानी",
    re.IGNORECASE,
)
# Asset-class words: investing only.
PICK_ASSETS = re.compile(
    r"\b(actions?|crypto\w*|bourse|acciones|cripto\w*|bolsa|ações|acções|azioni|borsa|etf|bitcoin|tesla)\b|"
    r"股票|加密货币|比特币|特斯拉|以太坊|英伟达|狗狗币|शेयर|स्टॉक|क्रिप्टो|बिटकॉइन|बिटकोइन|टेस्ला|सेयर|बिटक्वाइन"
)
# Named assets (local spellings of language-neutral names).
NAMED_LOCAL = re.compile(r"比特币|特斯拉|以太坊|英伟达|狗狗币|बिटकॉइन|बिटकोइन|बिटक्वाइन|टेस्ला|एनवीडिया|इथेरियम")
# Question words that ask for a pick ("which share should I buy?").
PICK_QUESTION = re.compile(
    r"\b(quel(le)?s?|lequel|qu[eé]|cu[aá]l(es)?|quais?|qual|quali|quale|devo|dois-je|debo|conviene)\b|"
    r"哪|什么|应该|कौन|क्या|कुन",
    re.IGNORECASE,
)

# ---------- F-3: personal money claims ----------

PERSONAL_CLAIM = re.compile(
    r"\b(vous avez|tu as|vous dépensez|tu dépenses|vous devez|tu dois|votre (solde|compte|budget|épargne|revenu|"
    r"loyer|dette)|ton (solde|compte|budget|loyer)|tes (dépenses|économies)|"
    r"tienes|gastas|debes|usted tiene|tu (saldo|cuenta|presupuesto|ahorro|ingreso|alquiler|deuda)|su saldo|"
    r"você tem|você gasta|você deve|tens|o seu (saldo|orçamento|rendimento|aluguel)|seu saldo|"
    r"hai|spendi|il tuo (saldo|conto|budget|risparmio|affitto|debito)|la tua (spesa|rata))\b|"
    r"你的(余额|账户|存款|预算|收入|支出|债务|钱)|你有|你每月花|你花了|你欠|"
    r"आपका (बैलेंस|खाता|बजट|ख़र्च|खर्च)|आपकी (बचत|आय)|आपके पास|आप हर महीने|आप पर|"
    r"तपाईंको (ब्यालेन्स|खाता|बजेट|बचत|खर्च)|तपाईंसँग|तपाईं हरेक महिना",
    re.IGNORECASE,
)
HYPOTHETICAL = re.compile(
    r"\b(si|supposons|par exemple|imaginons|supongamos|por ejemplo|imagina|suponha|por exemplo|"
    r"supponiamo|ad esempio|per esempio)\b|如果|假如|比如|例如|अगर|यदि|मान लीजिए|उदाहरण|उदाहरणका लागि",
    re.IGNORECASE,
)
MONEY_CONTEXT = re.compile(
    r"\b(solde|compte|argent|dépens\w*|saldo|cuenta|dinero|gast\w*|conta|dinheiro|conto|soldi|spes\w*)\b|"
    r"余额|账户|钱|花|बैलेंस|खाता|पैसे|ख़र्च|खर्च|ब्यालेन्स|पैसा",
    re.IGNORECASE,
)

# ---------- F-4: hardship and "can't cope" ----------

HARDSHIP = re.compile(
    r"je n'en peux plus|je ne m'en sors plus|(rien|plus rien) à manger|pas d'argent pour (manger|la nourriture|"
    r"le loyer)|(je ne peux pas|je n'arrive pas à) payer (mon|le) loyer|"
    r"no puedo más|no aguanto más|no tengo dinero para (comer|comida|el alquiler)|no puedo pagar el alquiler|"
    r"não aguento mais|não tenho dinheiro para (comer|comida|o aluguel|a renda)|não consigo pagar (o aluguel|a "
    r"renda)|"
    r"non ce la faccio più|non ho soldi per (mangiare|il cibo|l'affitto)|non riesco a pagare l'affitto|"
    r"撑不下去|受不了了|没钱吃饭|没有钱吃饭|交不起房租|付不起房租|活不下去|"
    r"अब और नहीं सह|सहन नहीं होता|खाने के (लिए )?पैसे नहीं|किराया नहीं दे|"
    r"अब सहन सक्दिन|सहन गर्न सक्दिन|खाना किन्ने पैसा छैन|खानलाई पैसा छैन|भाडा तिर्न सक्दिन",
    re.IGNORECASE,
)

# Sentence split for checks: Latin, Chinese and Devanagari full stops.
SENTENCES = re.compile(r"(?<=[.?!])\s+|(?<=[。！？।])\s*")
