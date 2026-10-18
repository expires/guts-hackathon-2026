"""Text for the sources hub "Where Penny's data comes from" (ADR 0073) in the 8 app languages.

Machine-written translations (ADR 0063). Source names that are proper names (Bank of England, ONS, Nomis, Octopus
Energy, Frankfurter) stay as they are. Numbers are formatted by the API route, not here.
"""

from __future__ import annotations

from lifeline_explain.i18n import Lang

SUMMARY: dict[Lang, str] = {
    "en": "Penny uses your statement plus {n} live UK sources. Here is what each one does.",
    "fr": "Penny utilise votre relevé et {n} sources britanniques en direct. Voici le rôle de chacune.",
    "es": "Penny usa tu extracto y {n} fuentes del Reino Unido en directo. Esto es lo que hace cada una.",
    "pt": "A Penny usa o seu extrato e {n} fontes do Reino Unido em tempo real. Veja o que cada uma faz.",
    "it": "Penny usa il tuo estratto conto e {n} fonti britanniche in tempo reale. Ecco cosa fa ciascuna.",
    "zh-Hans": "Penny 使用你的账单和 {n} 个英国实时数据来源。下面是每个来源的作用。",
    "hi": "Penny आपके स्टेटमेंट और {n} लाइव UK स्रोतों का उपयोग करती है। हर स्रोत क्या करता है, यह रहा।",
    "ne": "Penny ले तपाईंको स्टेटमेन्ट र {n} वटा प्रत्यक्ष UK स्रोत प्रयोग गर्छ। हरेकले के गर्छ, यहाँ छ।",
}

# Card names that are not proper names.
NAMES: dict[str, dict[Lang, str]] = {
    "statement": {"en": "Your statement", "fr": "Votre relevé", "es": "Tu extracto", "pt": "O seu extrato",
                  "it": "Il tuo estratto conto", "zh-Hans": "你的账单", "hi": "आपका स्टेटमेंट",
                  "ne": "तपाईंको स्टेटमेन्ट"},
    "official": {"en": "Official facts", "fr": "Faits officiels", "es": "Datos oficiales", "pt": "Factos oficiais",
                 "it": "Dati ufficiali", "zh-Hans": "官方信息", "hi": "आधिकारिक तथ्य", "ne": "आधिकारिक तथ्य"},
    "boe-mpc": {"en": "Bank of England MPC dates", "fr": "Dates du MPC de la Bank of England",
                "es": "Fechas del MPC del Bank of England", "pt": "Datas do MPC do Bank of England",
                "it": "Date del MPC della Bank of England", "zh-Hans": "英格兰银行货币政策委员会日期",
                "hi": "Bank of England MPC की तारीखें", "ne": "Bank of England MPC का मितिहरू"},
}  # fmt: skip

GIVES: dict[str, dict[Lang, str]] = {
    "statement": {
        "en": "Your money now, your usual spending and your bills. Only you see it.",
        "fr": "Votre argent actuel, vos dépenses habituelles et vos factures. Vous seul le voyez.",
        "es": "Tu dinero actual, tu gasto habitual y tus facturas. Solo tú lo ves.",
        "pt": "O seu dinheiro agora, os seus gastos habituais e as suas contas. Só você vê.",
        "it": "I tuoi soldi ora, le tue spese abituali e le tue bollette. Li vedi solo tu.",
        "zh-Hans": "你现在的钱、平常的支出和账单。只有你能看到。",
        "hi": "आपके अभी के पैसे, आपका आम ख़र्च और आपके बिल। इसे सिर्फ़ आप देखते हैं।",
        "ne": "तपाईंको अहिलेको पैसा, सामान्य खर्च र बिलहरू। यो तपाईंले मात्र देख्नुहुन्छ।",
    },
    "official": {
        "en": "Student loan, tax and ISA rules, checked against gov.uk, SAAS and Student Finance pages.",
        "fr": "Règles du prêt étudiant, des impôts et des ISA, vérifiées sur gov.uk, SAAS et Student Finance.",
        "es": "Normas de préstamos estudiantiles, impuestos e ISA, comprobadas en gov.uk, SAAS y Student Finance.",
        "pt": "Regras de empréstimo estudantil, impostos e ISA, verificadas no gov.uk, SAAS e Student Finance.",
        "it": "Regole su prestito studentesco, tasse e ISA, verificate su gov.uk, SAAS e Student Finance.",
        "zh-Hans": "学生贷款、税务和 ISA 规定，已对照 gov.uk、SAAS 和 Student Finance 页面核实。",
        "hi": "स्टूडेंट लोन, टैक्स और ISA के नियम, gov.uk, SAAS और Student Finance पेजों से जाँचे गए।",
        "ne": "विद्यार्थी ऋण, कर र ISA का नियम, gov.uk, SAAS र Student Finance पृष्ठबाट जाँचिएका।",
    },
    "boe": {
        "en": "Bank Rate and the average easy-access savings rate.",
        "fr": "Le taux directeur et le taux moyen de l'épargne disponible.",
        "es": "El tipo oficial y el tipo medio del ahorro de acceso inmediato.",
        "pt": "A taxa básica e a taxa média de poupança de acesso imediato.",
        "it": "Il tasso ufficiale e il tasso medio dei risparmi ad accesso immediato.",
        "zh-Hans": "基准利率和随时存取储蓄的平均利率。",
        "hi": "बैंक रेट और आसानी से निकलने वाली बचत की औसत ब्याज दर।",
        "ne": "बैंक दर र सजिलै झिक्न मिल्ने बचतको औसत ब्याज दर।",
    },
    "ons": {
        "en": "UK inflation (CPI), used when your next money is more than 6 weeks away.",
        "fr": "L'inflation au Royaume-Uni (CPI), utilisée quand votre prochain versement est à plus de 6 semaines.",
        "es": "La inflación del Reino Unido (CPI), usada cuando tu próximo ingreso está a más de 6 semanas.",
        "pt": "A inflação do Reino Unido (CPI), usada quando o seu próximo dinheiro está a mais de 6 semanas.",
        "it": "L'inflazione nel Regno Unito (CPI), usata quando i prossimi soldi arrivano tra più di 6 settimane.",
        "zh-Hans": "英国通胀率（CPI），在你下一笔钱到账超过 6 周时使用。",
        "hi": "UK महँगाई (CPI), जब आपका अगला पैसा 6 हफ़्ते से ज़्यादा दूर हो तब उपयोग होती है।",
        "ne": "UK मूल्यवृद्धि (CPI), तपाईंको अर्को पैसा 6 हप्ताभन्दा टाढा हुँदा प्रयोग हुन्छ।",
    },
    "nomis": {
        "en": "Typical UK pay, so Penny can talk about jobs and pay with real numbers.",
        "fr": "Le salaire type au Royaume-Uni, pour parler d'emploi et de salaire avec de vrais chiffres.",
        "es": "El salario típico del Reino Unido, para hablar de trabajo y sueldo con cifras reales.",
        "pt": "O salário típico do Reino Unido, para falar de trabalho e salário com números reais.",
        "it": "La paga tipica nel Regno Unito, per parlare di lavoro e stipendio con numeri reali.",
        "zh-Hans": "英国典型工资，让 Penny 用真实数字谈工作和收入。",
        "hi": "UK में आम वेतन, ताकि Penny नौकरी और वेतन पर असली आँकड़ों से बात कर सके।",
        "ne": "UK को सामान्य तलब, ताकि Penny ले काम र तलबबारे वास्तविक अङ्कमा कुरा गर्न सकोस्।",
    },
    "octopus": {
        "en": "The typical energy bill, to plan for bills.",
        "fr": "La facture d'énergie type, pour prévoir vos factures.",
        "es": "La factura de energía típica, para planificar tus facturas.",
        "pt": "A conta de energia típica, para planear as contas.",
        "it": "La bolletta energetica tipica, per pianificare le bollette.",
        "zh-Hans": "典型能源账单，用来规划账单。",
        "hi": "आम बिजली-गैस बिल, बिलों की योजना के लिए।",
        "ne": "सामान्य ऊर्जा बिल, बिलको योजना बनाउन।",
    },
    "frankfurter": {
        "en": "Exchange rates, so international students can compare prices with home.",
        "fr": "Les taux de change, pour que les étudiants étrangers comparent les prix avec leur pays.",
        "es": "Los tipos de cambio, para que los estudiantes internacionales comparen precios con su país.",
        "pt": "As taxas de câmbio, para estudantes internacionais compararem preços com o seu país.",
        "it": "I tassi di cambio, così gli studenti internazionali confrontano i prezzi con casa.",
        "zh-Hans": "汇率，方便国际学生和家乡的价格做比较。",
        "hi": "विनिमय दरें, ताकि अंतरराष्ट्रीय छात्र घर की कीमतों से तुलना कर सकें।",
        "ne": "विनिमय दर, ताकि अन्तर्राष्ट्रिय विद्यार्थीले घरको मूल्यसँग तुलना गर्न सकून्।",
    },
    "boe-mpc": {
        "en": "The date of the next Bank of England rate decision.",
        "fr": "La date de la prochaine décision de taux de la Bank of England.",
        "es": "La fecha de la próxima decisión de tipos del Bank of England.",
        "pt": "A data da próxima decisão de taxas do Bank of England.",
        "it": "La data della prossima decisione sui tassi della Bank of England.",
        "zh-Hans": "英格兰银行下一次利率决议的日期。",
        "hi": "Bank of England के अगले ब्याज दर फ़ैसले की तारीख।",
        "ne": "Bank of England को अर्को ब्याज दर निर्णयको मिति।",
    },
}

# Screen names, in the order a card lists them.
SCREENS: dict[str, dict[Lang, str]] = {
    "forecast": {"en": "Forecast", "fr": "Prévision", "es": "Previsión", "pt": "Previsão", "it": "Previsione",
                 "zh-Hans": "预测", "hi": "पूर्वानुमान", "ne": "पूर्वानुमान"},
    "spending": {"en": "Spending", "fr": "Dépenses", "es": "Gastos", "pt": "Gastos", "it": "Spese",
                 "zh-Hans": "支出", "hi": "ख़र्च", "ne": "खर्च"},
    "bills": {"en": "Bills", "fr": "Factures", "es": "Facturas", "pt": "Contas", "it": "Bollette",
              "zh-Hans": "账单", "hi": "बिल", "ne": "बिल"},
    "helps": {"en": "One thing that helps", "fr": "Une chose qui aide", "es": "Algo que ayuda",
              "pt": "Uma coisa que ajuda", "it": "Una cosa che aiuta", "zh-Hans": "一件有帮助的事",
              "hi": "एक चीज़ जो मदद करे", "ne": "मद्दत गर्ने एउटा कुरा"},
    "maths": {"en": "The maths", "fr": "Le calcul", "es": "Las cuentas", "pt": "As contas", "it": "I calcoli",
              "zh-Hans": "计算过程", "hi": "हिसाब", "ne": "हिसाब"},
    "penny": {"en": "Penny", "fr": "Penny", "es": "Penny", "pt": "Penny", "it": "Penny", "zh-Hans": "Penny",
              "hi": "Penny", "ne": "Penny"},
    "learn": {"en": "Learn", "fr": "Apprendre", "es": "Aprender", "pt": "Aprender", "it": "Impara",
              "zh-Hans": "学习", "hi": "सीखें", "ne": "सिक्नुहोस्"},
}  # fmt: skip

LABELS: dict[str, dict[Lang, str]] = {
    "bank_rate": {"en": "Bank Rate", "fr": "Taux directeur", "es": "Tipo oficial", "pt": "Taxa básica",
                  "it": "Tasso ufficiale", "zh-Hans": "基准利率", "hi": "बैंक रेट", "ne": "बैंक दर"},
    "savings_rate": {"en": "Easy-access savings rate", "fr": "Taux de l'épargne disponible",
                     "es": "Tipo del ahorro de acceso inmediato", "pt": "Taxa de poupança de acesso imediato",
                     "it": "Tasso dei risparmi ad accesso immediato", "zh-Hans": "随时存取储蓄利率",
                     "hi": "आसान-निकासी बचत दर", "ne": "सजिलो-निकासी बचत दर"},
    "cpi": {"en": "CPI annual rate", "fr": "Taux annuel du CPI", "es": "Tasa anual del CPI",
            "pt": "Taxa anual do CPI", "it": "Tasso annuo del CPI", "zh-Hans": "CPI 年增长率",
            "hi": "CPI वार्षिक दर", "ne": "CPI वार्षिक दर"},
    "median_pay": {"en": "Median full-time pay", "fr": "Salaire médian à temps plein",
                   "es": "Salario medio a tiempo completo", "pt": "Salário mediano a tempo inteiro",
                   "it": "Paga mediana a tempo pieno", "zh-Hans": "全职工资中位数", "hi": "पूर्णकालिक औसत वेतन",
                   "ne": "पूर्णकालीन मध्यम तलब"},
    "energy": {"en": "Typical energy bill", "fr": "Facture d'énergie type", "es": "Factura de energía típica",
               "pt": "Conta de energia típica", "it": "Bolletta energetica tipica", "zh-Hans": "典型能源账单",
               "hi": "आम ऊर्जा बिल", "ne": "सामान्य ऊर्जा बिल"},
    "gbp_usd": {"en": "Pounds to US dollars", "fr": "Livres en dollars US", "es": "Libras a dólares",
                "pt": "Libras para dólares", "it": "Sterline in dollari", "zh-Hans": "英镑兑美元",
                "hi": "पाउंड से अमेरिकी डॉलर", "ne": "पाउन्डबाट अमेरिकी डलर"},
    "next_decision": {"en": "Next rate decision", "fr": "Prochaine décision de taux",
                      "es": "Próxima decisión de tipos", "pt": "Próxima decisão de taxas",
                      "it": "Prossima decisione sui tassi", "zh-Hans": "下一次利率决议", "hi": "अगला दर फ़ैसला",
                      "ne": "अर्को दर निर्णय"},
    "plan2_threshold": {"en": "Student loan threshold (Plan 2)", "fr": "Seuil du prêt étudiant (Plan 2)",
                        "es": "Umbral del préstamo (Plan 2)", "pt": "Limiar do empréstimo (Plan 2)",
                        "it": "Soglia del prestito (Plan 2)", "zh-Hans": "学生贷款还款门槛（Plan 2）",
                        "hi": "स्टूडेंट लोन सीमा (Plan 2)", "ne": "विद्यार्थी ऋण सीमा (Plan 2)"},
    "isa_allowance": {"en": "ISA allowance", "fr": "Plafond ISA", "es": "Límite ISA", "pt": "Limite ISA",
                      "it": "Limite ISA", "zh-Hans": "ISA 额度", "hi": "ISA सीमा", "ne": "ISA सीमा"},
}  # fmt: skip

A_YEAR: dict[Lang, str] = {
    "en": "a year", "fr": "par an", "es": "al año", "pt": "por ano", "it": "all'anno", "zh-Hans": "每年",
    "hi": "प्रति वर्ष", "ne": "प्रति वर्ष",
}  # fmt: skip
