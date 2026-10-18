"""Penny's fixed texts and step labels in the 8 app languages (ADR 0063).

Machine-written translations, labelled as such in the README; native speakers may review later.
Numbers stay Western digits with £ and %, so the number verifier is unchanged. Samaritans 116 123 is the same
in every language (it is a UK service).
"""

from __future__ import annotations

import re
from typing import Literal

Lang = Literal["en", "fr", "es", "pt", "it", "zh-Hans", "hi", "ne"]
LANGS: tuple[Lang, ...] = ("en", "fr", "es", "pt", "it", "zh-Hans", "hi", "ne")

LANGUAGE_NAMES: dict[Lang, str] = {
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "it": "Italian",
    "zh-Hans": "Simplified Chinese",
    "hi": "Hindi",
    "ne": "Nepali",
}

OUT_OF_SCOPE: dict[Lang, str] = {
    "en": "Sorry, I cannot pick shares or crypto, or give regulated advice such as pensions, tax returns or legal "
    "questions. A regulated adviser can help with that. I can help with your budget and your next move.",
    "fr": "Désolée, je ne peux pas choisir d'actions ou de crypto, ni donner de conseil réglementé (retraite, "
    "déclaration d'impôts, questions juridiques). Un conseiller agréé peut vous aider. Je peux vous aider avec votre "
    "budget et votre prochaine décision.",
    "es": "Lo siento, no puedo elegir acciones ni cripto, ni dar asesoramiento regulado (pensiones, declaración de "
    "impuestos o temas legales). Un asesor regulado puede ayudarte. Yo te ayudo con tu presupuesto y tu próximo "
    "paso.",
    "pt": "Desculpe, não posso escolher ações ou cripto, nem dar aconselhamento regulado (pensões, declaração de "
    "impostos ou questões jurídicas). Um consultor regulado pode ajudar. Eu ajudo com o seu orçamento e o seu "
    "próximo passo.",
    "it": "Mi dispiace, non posso scegliere azioni o cripto, né dare consulenza regolamentata (pensioni, "
    "dichiarazione dei redditi o questioni legali). Un consulente autorizzato può aiutarti. Io ti aiuto con il "
    "budget e la tua prossima mossa.",
    "zh-Hans": "抱歉，我不能推荐股票或加密货币，也不能提供受监管的建议，例如养老金、报税或法律问题。"
    "持牌顾问可以帮助你。我可以帮你做预算和下一步理财决定。",
    "hi": "माफ़ कीजिए, मैं शेयर या क्रिप्टो नहीं चुन सकती, और पेंशन, टैक्स रिटर्न या कानूनी सवालों जैसी विनियमित सलाह "
    "नहीं दे सकती। एक विनियमित सलाहकार इसमें मदद कर सकता है। मैं आपके बजट और अगले कदम में मदद कर सकती हूँ।",
    "ne": "माफ गर्नुहोस्, म सेयर वा क्रिप्टो छान्न सक्दिनँ, र पेन्सन, कर विवरण वा कानुनी प्रश्नजस्ता नियमित सल्लाह "
    "दिन सक्दिनँ। दर्ता भएका सल्लाहकारले मद्दत गर्न सक्छन्। म तपाईंको बजेट र अर्को कदममा मद्दत गर्न सक्छु।",
}

DISTRESS: dict[Lang, tuple[str, str]] = {
    "en": (
        "I am sorry things feel this hard. You do not have to sort this out alone.",
        "Your university hardship fund and student support team can help with money fast. If you need to talk or "
        "feel unsafe, call Samaritans free on 116 123, day or night.",
    ),
    "fr": (
        "Je suis désolée que ce soit si difficile. Vous n'avez pas à gérer cela seul.",
        "Le fonds d'aide (hardship fund) et le service d'accompagnement des étudiants de votre université peuvent "
        "vous aider vite. Si vous avez besoin de parler ou ne vous sentez pas en sécurité, appelez gratuitement "
        "Samaritans au 116 123, jour et nuit.",
    ),
    "es": (
        "Siento que esto sea tan difícil. No tienes que resolverlo solo.",
        "El fondo de ayuda (hardship fund) y el servicio de apoyo al estudiante de tu universidad pueden ayudarte "
        "rápido. Si necesitas hablar o no te sientes seguro, llama gratis a Samaritans al 116 123, de día o de noche.",
    ),
    "pt": (
        "Sinto muito que esteja tão difícil. Você não precisa resolver isso sozinho.",
        "O fundo de apoio (hardship fund) e a equipe de apoio ao estudante da sua universidade podem ajudar "
        "rápido. Se precisar conversar ou não se sentir seguro, ligue grátis para Samaritans no 116 123, dia e "
        "noite.",
    ),
    "it": (
        "Mi dispiace che sia così difficile. Non devi affrontarlo da solo.",
        "Il fondo di sostegno (hardship fund) e il servizio di supporto agli studenti della tua università possono "
        "aiutarti in fretta. Se hai bisogno di parlare o non ti senti al sicuro, chiama gratis Samaritans al "
        "116 123, giorno e notte.",
    ),
    "zh-Hans": (
        "很抱歉你现在这么难受。你不必独自面对。",
        "你所在大学的困难补助基金（hardship fund）和学生支持团队可以很快帮你解决钱的问题。"
        "如果你想找人聊聊或感到不安全，请随时免费拨打 Samaritans 116 123。",
    ),
    "hi": (
        "मुझे दुख है कि हालात इतने कठिन लग रहे हैं। आपको यह अकेले नहीं संभालना है।",
        "आपकी यूनिवर्सिटी का हार्डशिप फंड (hardship fund) और स्टूडेंट सपोर्ट टीम पैसों में जल्दी मदद कर सकते हैं। "
        "अगर आपको बात करनी है या आप सुरक्षित महसूस नहीं करते, तो Samaritans को 116 123 पर मुफ़्त कॉल करें, दिन या रात।",
    ),
    "ne": (
        "यति गाह्रो भएकोमा म दुःखी छु। तपाईंले यो एक्लै सम्हाल्नु पर्दैन।",
        "तपाईंको विश्वविद्यालयको हार्डसिप कोष (hardship fund) र विद्यार्थी सहयोग टोलीले पैसामा छिटो मद्दत गर्न सक्छन्। "
        "कुरा गर्नु परे वा असुरक्षित लागे, Samaritans लाई 116 123 मा निःशुल्क फोन गर्नुहोस्, दिन होस् वा रात।",
    ),
}

UNAVAILABLE: dict[Lang, str] = {
    "en": "Penny is unavailable right now. Try again.",
    "fr": "Penny n'est pas disponible pour le moment. Réessayez.",
    "es": "Penny no está disponible ahora. Inténtalo de nuevo.",
    "pt": "A Penny não está disponível agora. Tente de novo.",
    "it": "Penny non è disponibile in questo momento. Riprova.",
    "zh-Hans": "Penny 暂时无法使用。请再试一次。",
    "hi": "Penny अभी उपलब्ध नहीं है। फिर से कोशिश करें।",
    "ne": "Penny अहिले उपलब्ध छैन। फेरि प्रयास गर्नुहोस्।",
}

NOT_CONFIRMED: dict[Lang, str] = {
    "en": "I could not confirm that number from your data or an official source, so I will not guess it. "
    "Ask me again, or check the Money tab.",
    "fr": "Je n'ai pas pu confirmer ce chiffre avec vos données ou une source officielle, je ne vais donc pas le "
    "deviner. Reposez la question ou consultez l'onglet Argent.",
    "es": "No pude confirmar ese número con tus datos ni con una fuente oficial, así que no lo voy a adivinar. "
    "Pregúntame otra vez o mira la pestaña Dinero.",
    "pt": "Não consegui confirmar esse número com os seus dados ou uma fonte oficial, então não vou adivinhar. "
    "Pergunte de novo ou veja a aba Dinheiro.",
    "it": "Non ho potuto confermare quel numero con i tuoi dati o una fonte ufficiale, quindi non lo indovino. "
    "Chiedimelo di nuovo o guarda la scheda Soldi.",
    "zh-Hans": "我无法用你的数据或官方来源确认这个数字，所以不会猜测。请再问一次，或查看“钱”页面。",
    "hi": "मैं इस संख्या की पुष्टि आपके डेटा या किसी आधिकारिक स्रोत से नहीं कर सकी, इसलिए अनुमान नहीं लगाऊँगी। "
    "फिर से पूछें या Money टैब देखें।",
    "ne": "म यो संख्या तपाईंको डेटा वा आधिकारिक स्रोतबाट पुष्टि गर्न सकिनँ, त्यसैले अनुमान लगाउँदिनँ। "
    "फेरि सोध्नुहोस् वा Money ट्याब हेर्नुहोस्।",
}

NO_OFFICIAL_SOURCE: dict[Lang, str] = {
    "en": "I could not find an official source for that, so I will not give a number. "
    "GOV.UK or your student finance provider will have the exact figure.",
    "fr": "Je n'ai pas trouvé de source officielle, je ne donne donc pas de chiffre. GOV.UK ou votre organisme de "
    "financement étudiant aura le montant exact.",
    "es": "No encontré una fuente oficial, así que no daré un número. GOV.UK o tu proveedor de financiación "
    "estudiantil tendrá la cifra exacta.",
    "pt": "Não encontrei uma fonte oficial, então não vou dar um número. O GOV.UK ou o seu órgão de financiamento "
    "estudantil terá o valor exato.",
    "it": "Non ho trovato una fonte ufficiale, quindi non do un numero. GOV.UK o il tuo ente di finanziamento per "
    "studenti avrà la cifra esatta.",
    "zh-Hans": "我没有找到官方来源，所以不会给出数字。GOV.UK 或你的学生贷款机构会有准确数字。",
    "hi": "मुझे इसका कोई आधिकारिक स्रोत नहीं मिला, इसलिए मैं कोई संख्या नहीं दूँगी। GOV.UK या आपका स्टूडेंट फ़ाइनेंस "
    "प्रदाता सही आँकड़ा बताएगा।",
    "ne": "मैले यसको आधिकारिक स्रोत भेटिनँ, त्यसैले संख्या दिन्नँ। GOV.UK वा तपाईंको विद्यार्थी वित्त प्रदायकसँग सही आँकडा हुन्छ।",
}

NO_INSTRUCTIONS: dict[Lang, str] = {
    "en": "I cannot share how I am set up. I can help with your money and your Next Move.",
    "fr": "Je ne peux pas expliquer comment je suis configurée. Je peux vous aider avec votre argent et votre "
    "prochaine décision.",
    "es": "No puedo compartir cómo estoy configurada. Puedo ayudarte con tu dinero y tu próximo paso.",
    "pt": "Não posso partilhar como estou configurada. Posso ajudar com o seu dinheiro e o seu próximo passo.",
    "it": "Non posso dire come sono configurata. Posso aiutarti con i tuoi soldi e la tua prossima mossa.",
    "zh-Hans": "我不能透露我的设置。我可以帮你管理钱和下一步理财决定。",
    "hi": "मैं यह नहीं बता सकती कि मुझे कैसे सेट किया गया है। मैं आपके पैसे और अगले कदम में मदद कर सकती हूँ।",
    "ne": "म कसरी सेट गरिएको छु भन्न सक्दिनँ। म तपाईंको पैसा र अर्को कदममा मद्दत गर्न सक्छु।",
}

TEMPLATE_INTRO: dict[Lang, str] = {
    "en": "Here are the numbers I found.",
    "fr": "Voici les chiffres que j'ai trouvés.",
    "es": "Estos son los números que encontré.",
    "pt": "Aqui estão os números que encontrei.",
    "it": "Ecco i numeri che ho trovato.",
    "zh-Hans": "这是我找到的数字。",
    "hi": "ये रहे वे आँकड़े जो मुझे मिले।",
    "ne": "मैले भेटेका आँकडा यी हुन्।",
}

MAKE_A_BUDGET: dict[Lang, str] = {
    "en": "Make a budget", "fr": "Faire un budget", "es": "Hacer un presupuesto", "pt": "Fazer um orçamento",
    "it": "Fare un budget", "zh-Hans": "做个预算", "hi": "बजट बनाएँ", "ne": "बजेट बनाउनुहोस्",
}  # fmt: skip

# English step label -> translations. Keys are the labels chat.py and EngineToolSet produce.
STEPS: dict[str, dict[Lang, str]] = {
    "Checking your next move…": {"fr": "Je vérifie votre prochaine décision…",
        "es": "Reviso tu próximo paso…", "pt": "Verificando o seu próximo passo…",
        "it": "Controllo la tua prossima mossa…", "zh-Hans": "正在查看你的下一步…",
        "hi": "आपका अगला कदम देख रही हूँ…", "ne": "तपाईंको अर्को कदम हेर्दै…"},
    "Replaying the test period…": {"fr": "Je rejoue la période de test…",
        "es": "Repito el periodo de prueba…", "pt": "Repetindo o período de teste…",
        "it": "Rigioco il periodo di prova…", "zh-Hans": "正在重放测试期…",
        "hi": "टेस्ट अवधि दोबारा चला रही हूँ…", "ne": "परीक्षण अवधि फेरि चलाउँदै…"},
    "Reading your accounts…": {"fr": "Je lis vos comptes…", "es": "Leo tus cuentas…",
        "pt": "Lendo as suas contas…", "it": "Leggo i tuoi conti…", "zh-Hans": "正在读取你的账户…",
        "hi": "आपके खाते पढ़ रही हूँ…", "ne": "तपाईंका खाता पढ्दै…"},
    "Predicting your spending…": {"fr": "Je prévois vos dépenses…", "es": "Calculo tu gasto…",
        "pt": "Prevendo os seus gastos…", "it": "Prevedo le tue spese…", "zh-Hans": "正在预测你的支出…",
        "hi": "आपका ख़र्च अनुमानित कर रही हूँ…", "ne": "तपाईंको खर्च अनुमान गर्दै…"},
    "Projecting your cash…": {"fr": "Je projette votre trésorerie…", "es": "Proyecto tu dinero…",
        "pt": "Projetando o seu dinheiro…", "it": "Proietto la tua liquidità…",
        "zh-Hans": "正在预测你的现金…", "hi": "आपके पैसों का अनुमान लगा रही हूँ…",
        "ne": "तपाईंको नगद अनुमान गर्दै…"},
    "Replaying your life…": {"fr": "Je rejoue votre vie…", "es": "Repito tu vida…",
        "pt": "Repetindo a sua vida…", "it": "Rigioco la tua vita…", "zh-Hans": "正在重放你的人生…",
        "hi": "आपकी ज़िंदगी दोबारा चला रही हूँ…", "ne": "तपाईंको जीवन फेरि चलाउँदै…"},
    "Playing each choice forward…": {"fr": "Je joue chaque choix…", "es": "Juego cada opción…",
        "pt": "Jogando cada escolha…", "it": "Gioco ogni scelta…", "zh-Hans": "正在推演每个选择…",
        "hi": "हर विकल्प आगे चला रही हूँ…", "ne": "हरेक विकल्प अगाडि चलाउँदै…"},
    "Checking the news…": {"fr": "Je consulte l'actualité…", "es": "Reviso las noticias…",
        "pt": "Vendo as notícias…", "it": "Controllo le notizie…", "zh-Hans": "正在查看新闻…",
        "hi": "ख़बरें देख रही हूँ…", "ne": "समाचार हेर्दै…"},
    "Checking Bank of England…": {"fr": "Je consulte la Bank of England…",
        "es": "Consulto el Bank of England…", "pt": "Consultando o Bank of England…",
        "it": "Controllo la Bank of England…", "zh-Hans": "正在查看英格兰银行…",
        "hi": "Bank of England देख रही हूँ…", "ne": "Bank of England हेर्दै…"},
    "Checking Bank of England rates…": {"fr": "Je consulte les taux de la Bank of England…",
        "es": "Consulto los tipos del Bank of England…", "pt": "Consultando as taxas do Bank of England…",
        "it": "Controllo i tassi della Bank of England…", "zh-Hans": "正在查看英格兰银行利率…",
        "hi": "Bank of England की दरें देख रही हूँ…", "ne": "Bank of England का दरहरू हेर्दै…"},
    "Checking the official rules…": {"fr": "Je vérifie les règles officielles…",
        "es": "Reviso las normas oficiales…", "pt": "Verificando as regras oficiais…",
        "it": "Controllo le regole ufficiali…", "zh-Hans": "正在查看官方规定…",
        "hi": "आधिकारिक नियम देख रही हूँ…", "ne": "आधिकारिक नियम हेर्दै…"},
    "Searching the web…": {"fr": "Je cherche sur le web…", "es": "Busco en la web…",
        "pt": "Pesquisando na web…", "it": "Cerco sul web…", "zh-Hans": "正在网上搜索…",
        "hi": "वेब पर खोज रही हूँ…", "ne": "वेबमा खोज्दै…"},
    "Checking your balance…": {"fr": "Je vérifie votre solde…", "es": "Reviso tu saldo…",
        "pt": "Verificando o seu saldo…", "it": "Controllo il tuo saldo…", "zh-Hans": "正在查看你的余额…",
        "hi": "आपका बैलेंस देख रही हूँ…", "ne": "तपाईंको ब्यालेन्स हेर्दै…"},
    "Checking your habits…": {"fr": "Je vérifie vos habitudes…", "es": "Reviso tus hábitos…",
        "pt": "Verificando os seus hábitos…", "it": "Controllo le tue abitudini…",
        "zh-Hans": "正在查看你的习惯…", "hi": "आपकी आदतें देख रही हूँ…", "ne": "तपाईंका बानी हेर्दै…"},
    "Checking inflation…": {"fr": "Je vérifie l'inflation…", "es": "Reviso la inflación…",
        "pt": "Verificando a inflação…", "it": "Controllo l'inflazione…", "zh-Hans": "正在查看通胀…",
        "hi": "महँगाई देख रही हूँ…", "ne": "मूल्यवृद्धि हेर्दै…"},
    "Checking exchange rates…": {"fr": "Je vérifie les taux de change…",
        "es": "Reviso los tipos de cambio…", "pt": "Verificando as taxas de câmbio…",
        "it": "Controllo i tassi di cambio…", "zh-Hans": "正在查看汇率…",
        "hi": "विनिमय दरें देख रही हूँ…", "ne": "विनिमय दर हेर्दै…"},
    "Checking your forecast…": {"fr": "Je vérifie vos prévisions…", "es": "Reviso tu previsión…",
        "pt": "Verificando a sua previsão…", "it": "Controllo la tua previsione…",
        "zh-Hans": "正在查看你的预测…", "hi": "आपका पूर्वानुमान देख रही हूँ…", "ne": "तपाईंको पूर्वानुमान हेर्दै…"},
    "Trying your what-if…": {"fr": "J'essaie votre scénario…", "es": "Pruebo tu supuesto…",
        "pt": "Testando a sua hipótese…", "it": "Provo la tua ipotesi…", "zh-Hans": "正在试算你的假设…",
        "hi": "आपका 'क्या होगा अगर' आज़मा रही हूँ…", "ne": "तपाईंको 'यदि' परीक्षण गर्दै…"},
    "Working…": {"fr": "Je travaille…", "es": "Trabajando…", "pt": "Trabalhando…",
        "it": "Ci lavoro…", "zh-Hans": "处理中…", "hi": "काम कर रही हूँ…", "ne": "काम गर्दै…"},
}  # fmt: skip

# C5: the onboarding chat answers; if a model answer was only a refusal ("I can't see your numbers"), this line
# replaces it after one retry.
ONBOARDING_ANSWER: dict[Lang, str] = {
    "en": "Ask me about budgets, loans, rent, part-time work or uni life, and I will explain how it works for "
    "students.",
    "fr": "Posez-moi vos questions sur le budget, les prêts, le loyer, les petits boulots ou la vie étudiante, et je "
    "vous explique comment ça marche pour les étudiants.",
    "es": "Pregúntame sobre presupuestos, préstamos, alquiler, trabajo a tiempo parcial o la vida universitaria, y "
    "te explico cómo funciona para estudiantes.",
    "pt": "Pergunte-me sobre orçamento, empréstimos, aluguel, trabalho de meio período ou vida universitária, e eu "
    "explico como funciona para estudantes.",
    "it": "Chiedimi di budget, prestiti, affitto, lavoro part-time o vita universitaria, e ti spiego come funziona "
    "per gli studenti.",
    "zh-Hans": "问我关于预算、贷款、房租、兼职或大学生活的问题，我会解释对学生来说是怎么运作的。",
    "hi": "बजट, लोन, किराया, पार्ट-टाइम काम या यूनिवर्सिटी जीवन के बारे में पूछें, मैं बताऊँगी कि छात्रों के लिए यह कैसे "
    "काम करता है।",
    "ne": "बजेट, ऋण, भाडा, पार्ट-टाइम काम वा विश्वविद्यालय जीवनबारे सोध्नुहोस्, म विद्यार्थीका लागि यो कसरी काम गर्छ भनेर "
    "बताउँछु।",
}

REPLAYING: dict[Lang, str] = {
    "en": "Replaying", "fr": "Je rejoue", "es": "Repito", "pt": "Repetindo", "it": "Rigioco",
    "zh-Hans": "正在重放", "hi": "दोबारा चला रही हूँ", "ne": "फेरि चलाउँदै",
}  # fmt: skip
_REPLAY = re.compile(r"^Replaying (?P<years>\d{4}(?:–\d{4})?)…$")


def lang_of(value: object) -> Lang:
    for lang in LANGS:
        if value == lang:
            return lang
    return "en"


def step(label: str, lang: Lang) -> str:
    """Translate a step label. Unknown labels stay as they are (they still describe a real tool call)."""
    if lang == "en":
        return label
    m = _REPLAY.match(label)
    if m:
        return f"{REPLAYING[lang]} {m.group('years')}…"
    return STEPS.get(label, {}).get(lang, label)


def language_line(lang: Lang) -> str | None:
    """Per-request instruction (in the user turn, so the cached system prompt stays the same)."""
    if lang == "en":
        return None
    return (
        f"ANSWER LANGUAGE: {LANGUAGE_NAMES[lang]}. Write every bubble and every suggestion in "
        f"{LANGUAGE_NAMES[lang]}. Keep numbers as Western digits with £ and % (for example £1,240 and 4.5%)."
    )


# V5 speed: Penny's first bubble while the what-if forecast reruns (no numbers; the checked answer follows).
WHAT_IF_ACK: dict[Lang, str] = {
    "en": "Let me rerun your forecast with that change.",
    "fr": "Je recalcule ta prévision avec ce changement.",
    "es": "Vuelvo a calcular tu previsión con ese cambio.",
    "pt": "Vou recalcular a tua previsão com essa mudança.",
    "it": "Ricalcolo la tua previsione con questa modifica.",
    "zh-Hans": "我用这个变化重新计算一下你的预测。",
    "hi": "मैं इस बदलाव के साथ आपका पूर्वानुमान फिर से निकालती हूँ।",
    "ne": "म यो परिवर्तनसहित तपाईंको पूर्वानुमान फेरि निकाल्छु।",
}
