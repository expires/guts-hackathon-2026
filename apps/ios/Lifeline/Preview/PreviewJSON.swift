// GENERATED from contracts/openapi.yaml `components.examples`. Do not hand-edit.
// Canned responses for MockClient, previews and UI tests.

enum PreviewJSON {
    static let characters = #"""
{
 "presets": [
  {
   "id": "nurse-leeds",
   "name": "Amira",
   "emoji": "👩🏽‍⚕️",
   "sex": "female",
   "occupation": "nurse",
   "region": "yorkshire-and-the-humber",
   "town": "Leeds",
   "birth_year": 1982,
   "annual_income": 24800.0,
   "savings": 3200.0,
   "debt": 1500.0,
   "housing": "rent",
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "blurb": "NHS nurse renting in Leeds."
  },
  {
   "id": "banker-london",
   "name": "Tom",
   "emoji": "👨🏻‍💼",
   "sex": "male",
   "occupation": "banker",
   "region": "london",
   "town": "London",
   "birth_year": 1979,
   "annual_income": 92000.0,
   "savings": 41000.0,
   "debt": 0.0,
   "housing": "mortgage",
   "property_value": 410000.0,
   "mortgage_balance": 290000.0,
   "blurb": "Investment banker with a flat in Canary Wharf."
  }
 ],
 "random": {
  "id": "random-424242",
  "name": "Jordan",
  "emoji": "👩🏽‍⚕️",
  "sex": "female",
  "occupation": "plumber",
  "region": "yorkshire-and-the-humber",
  "town": "Bradford",
  "birth_year": 1982,
  "annual_income": 24800.0,
  "savings": 3200.0,
  "debt": 1500.0,
  "housing": "rent",
  "property_value": 0.0,
  "mortgage_balance": 0.0,
  "blurb": "NHS nurse renting in Leeds."
 }
}
"""#
    static let life = #"""
{
 "id": "lf_8f3a2c",
 "seed": 424242,
 "mode": "preset",
 "character": {
  "id": "nurse-leeds",
  "name": "Amira",
  "emoji": "👩🏽‍⚕️",
  "sex": "female",
  "occupation": "nurse",
  "region": "yorkshire-and-the-humber",
  "town": "Leeds",
  "birth_year": 1982,
  "annual_income": 24800.0,
  "savings": 3200.0,
  "debt": 1500.0,
  "housing": "rent",
  "property_value": 0.0,
  "mortgage_balance": 0.0,
  "blurb": "NHS nurse renting in Leeds."
 },
 "start_year": 2006,
 "year": 2008,
 "age": 26,
 "alive": true,
 "stats": {
  "happiness": 72,
  "health": 88,
  "smarts": 64,
  "money": 41
 },
 "finances": {
  "cash": 1200.0,
  "savings": 3200.0,
  "investments": 0.0,
  "crypto": 0.0,
  "pension": 4100.0,
  "property_value": 0.0,
  "mortgage_balance": 0.0,
  "other_debt": 1500.0,
  "student_loan": 18000.0,
  "annual_income": 24800.0,
  "monthly_costs": 1450.0,
  "net_worth": -11000.0
 },
 "index": {
  "value": 101.4,
  "r_player": -0.36,
  "r_autopilot": -0.4,
  "missed_payments": 0,
  "max_drawdown": 0.05
 },
 "job": {
  "title": "Staff nurse",
  "employer": "Leeds Teaching Hospitals",
  "annual_income": 24800.0,
  "years_in_role": 2,
  "employer_status": "active"
 },
 "assets": [
  {
   "id": "as1",
   "kind": "pension",
   "name": "NHS pension",
   "value": 4100.0
  }
 ],
 "relationships": [
  {
   "id": "rl1",
   "kind": "parent",
   "name": "Mum",
   "emoji": "👩🏽",
   "closeness": 80
  }
 ],
 "pending_events": [
  {
   "id": "ev-2008-1",
   "template_id": "home.rent_rise",
   "area": "home",
   "year": 2008,
   "age": 26,
   "emoji": "🏠",
   "title": "Your rent is going up",
   "text": "Your landlord wants £45 more a month. Rents in your area rose 4.1% this year.",
   "text_source": "template",
   "choices": [
    {
     "id": "accept",
     "label": "Pay it",
     "emoji": "💷",
     "hint": "-£540 a year",
     "is_default": true
    },
    {
     "id": "move",
     "label": "Move somewhere cheaper",
     "emoji": "📦",
     "hint": "-£600 once, then -£360 a year",
     "is_default": false
    }
   ],
   "facts": {
    "rent_increase_monthly": 45.0,
    "rent_change_pct": 4.1
   },
   "sources": [
    {
     "source": "ons",
     "series_id": "IPHRP",
     "status": "cached",
     "note": "UK average used"
    }
   ],
   "concept_id": "inflation"
  }
 ],
 "available_actions": [
  {
   "tab": "job",
   "id": "ask_raise",
   "label": "Ask for a pay rise",
   "emoji": "🙋",
   "enabled": true,
   "paid": false
  },
  {
   "tab": "money",
   "id": "open_isa",
   "label": "Open a savings account",
   "emoji": "🏦",
   "hint": "Tax-free savings",
   "enabled": true,
   "paid": false
  }
 ],
 "history": [
  {
   "year": 2007,
   "age": 25,
   "text": "You started at Leeds General.",
   "net_worth": -12500.0,
   "autopilot_net_worth": -12500.0,
   "index": 100.0
  }
 ],
 "ribbons": [],
 "concepts_unlocked": [
  "compound-interest"
 ],
 "rewind": {
  "free_left": 1,
  "has_pass": false
 },
 "reached_present": false
}
"""#
    static let ageResult = #"""
{
 "life": {
  "id": "lf_8f3a2c",
  "seed": 424242,
  "mode": "preset",
  "character": {
   "id": "nurse-leeds",
   "name": "Amira",
   "emoji": "👩🏽‍⚕️",
   "sex": "female",
   "occupation": "nurse",
   "region": "yorkshire-and-the-humber",
   "town": "Leeds",
   "birth_year": 1982,
   "annual_income": 24800.0,
   "savings": 3200.0,
   "debt": 1500.0,
   "housing": "rent",
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "blurb": "NHS nurse renting in Leeds."
  },
  "start_year": 2006,
  "year": 2008,
  "age": 26,
  "alive": true,
  "stats": {
   "happiness": 72,
   "health": 88,
   "smarts": 64,
   "money": 41
  },
  "finances": {
   "cash": 1200.0,
   "savings": 3200.0,
   "investments": 0.0,
   "crypto": 0.0,
   "pension": 4100.0,
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "other_debt": 1500.0,
   "student_loan": 18000.0,
   "annual_income": 24800.0,
   "monthly_costs": 1450.0,
   "net_worth": -11000.0
  },
  "index": {
   "value": 101.4,
   "r_player": -0.36,
   "r_autopilot": -0.4,
   "missed_payments": 0,
   "max_drawdown": 0.05
  },
  "job": {
   "title": "Staff nurse",
   "employer": "Leeds Teaching Hospitals",
   "annual_income": 24800.0,
   "years_in_role": 2,
   "employer_status": "active"
  },
  "assets": [
   {
    "id": "as1",
    "kind": "pension",
    "name": "NHS pension",
    "value": 4100.0
   }
  ],
  "relationships": [
   {
    "id": "rl1",
    "kind": "parent",
    "name": "Mum",
    "emoji": "👩🏽",
    "closeness": 80
   }
  ],
  "pending_events": [
   {
    "id": "ev-2008-1",
    "template_id": "home.rent_rise",
    "area": "home",
    "year": 2008,
    "age": 26,
    "emoji": "🏠",
    "title": "Your rent is going up",
    "text": "Your landlord wants £45 more a month. Rents in your area rose 4.1% this year.",
    "text_source": "template",
    "choices": [
     {
      "id": "accept",
      "label": "Pay it",
      "emoji": "💷",
      "hint": "-£540 a year",
      "is_default": true
     },
     {
      "id": "move",
      "label": "Move somewhere cheaper",
      "emoji": "📦",
      "hint": "-£600 once, then -£360 a year",
      "is_default": false
     }
    ],
    "facts": {
     "rent_increase_monthly": 45.0,
     "rent_change_pct": 4.1
    },
    "sources": [
     {
      "source": "ons",
      "series_id": "IPHRP",
      "status": "cached",
      "note": "UK average used"
     }
    ],
    "concept_id": "inflation"
   }
  ],
  "available_actions": [
   {
    "tab": "job",
    "id": "ask_raise",
    "label": "Ask for a pay rise",
    "emoji": "🙋",
    "enabled": true,
    "paid": false
   },
   {
    "tab": "money",
    "id": "open_isa",
    "label": "Open a savings account",
    "emoji": "🏦",
    "hint": "Tax-free savings",
    "enabled": true,
    "paid": false
   }
  ],
  "history": [
   {
    "year": 2007,
    "age": 25,
    "text": "You started at Leeds General.",
    "net_worth": -12500.0,
    "autopilot_net_worth": -12500.0,
    "index": 100.0
   }
  ],
  "ribbons": [],
  "concepts_unlocked": [
   "compound-interest"
  ],
  "rewind": {
   "free_left": 1,
   "has_pass": false
  },
  "reached_present": false
 },
 "events": [
  {
   "id": "ev-2008-1",
   "template_id": "home.rent_rise",
   "area": "home",
   "year": 2008,
   "age": 26,
   "emoji": "🏠",
   "title": "Your rent is going up",
   "text": "Your landlord wants £45 more a month. Rents in your area rose 4.1% this year.",
   "text_source": "template",
   "choices": [
    {
     "id": "accept",
     "label": "Pay it",
     "emoji": "💷",
     "hint": "-£540 a year",
     "is_default": true
    },
    {
     "id": "move",
     "label": "Move somewhere cheaper",
     "emoji": "📦",
     "hint": "-£600 once, then -£360 a year",
     "is_default": false
    }
   ],
   "facts": {
    "rent_increase_monthly": 45.0,
    "rent_change_pct": 4.1
   },
   "sources": [
    {
     "source": "ons",
     "series_id": "IPHRP",
     "status": "cached",
     "note": "UK average used"
    }
   ],
   "concept_id": "inflation"
  }
 ]
}
"""#
    static let choiceResult = #"""
{
 "life": {
  "id": "lf_8f3a2c",
  "seed": 424242,
  "mode": "preset",
  "character": {
   "id": "nurse-leeds",
   "name": "Amira",
   "emoji": "👩🏽‍⚕️",
   "sex": "female",
   "occupation": "nurse",
   "region": "yorkshire-and-the-humber",
   "town": "Leeds",
   "birth_year": 1982,
   "annual_income": 24800.0,
   "savings": 3200.0,
   "debt": 1500.0,
   "housing": "rent",
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "blurb": "NHS nurse renting in Leeds."
  },
  "start_year": 2006,
  "year": 2008,
  "age": 26,
  "alive": true,
  "stats": {
   "happiness": 72,
   "health": 88,
   "smarts": 64,
   "money": 41
  },
  "finances": {
   "cash": 1200.0,
   "savings": 3200.0,
   "investments": 0.0,
   "crypto": 0.0,
   "pension": 4100.0,
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "other_debt": 1500.0,
   "student_loan": 18000.0,
   "annual_income": 24800.0,
   "monthly_costs": 1450.0,
   "net_worth": -11000.0
  },
  "index": {
   "value": 101.4,
   "r_player": -0.36,
   "r_autopilot": -0.4,
   "missed_payments": 0,
   "max_drawdown": 0.05
  },
  "job": {
   "title": "Staff nurse",
   "employer": "Leeds Teaching Hospitals",
   "annual_income": 24800.0,
   "years_in_role": 2,
   "employer_status": "active"
  },
  "assets": [
   {
    "id": "as1",
    "kind": "pension",
    "name": "NHS pension",
    "value": 4100.0
   }
  ],
  "relationships": [
   {
    "id": "rl1",
    "kind": "parent",
    "name": "Mum",
    "emoji": "👩🏽",
    "closeness": 80
   }
  ],
  "pending_events": [],
  "available_actions": [
   {
    "tab": "job",
    "id": "ask_raise",
    "label": "Ask for a pay rise",
    "emoji": "🙋",
    "enabled": true,
    "paid": false
   },
   {
    "tab": "money",
    "id": "open_isa",
    "label": "Open a savings account",
    "emoji": "🏦",
    "hint": "Tax-free savings",
    "enabled": true,
    "paid": false
   }
  ],
  "history": [
   {
    "year": 2007,
    "age": 25,
    "text": "You started at Leeds General.",
    "net_worth": -12500.0,
    "autopilot_net_worth": -12500.0,
    "index": 100.0
   }
  ],
  "ribbons": [],
  "concepts_unlocked": [
   "compound-interest"
  ],
  "rewind": {
   "free_left": 1,
   "has_pass": false
  },
  "reached_present": false
 },
 "outcome": {
  "event_id": "ev-2008-1",
  "choice_id": "move",
  "text": "You moved to a cheaper flat in Headingley.",
  "text_source": "template",
  "deltas": {
   "money": -600.0,
   "happiness": -3,
   "health": 0,
   "smarts": 0
  },
  "facts": {
   "one_off_cost": 600.0
  },
  "good": true
 },
 "lesson": {
  "concept_id": "inflation",
  "title": "Prices creep up",
  "chart": {
   "kind": "line",
   "title": "Rent change per year",
   "x_label": "Year",
   "y_label": "%",
   "points": [
    {
     "x": 2006.0,
     "y": 3.2
    },
    {
     "x": 2007.0,
     "y": 3.9
    },
    {
     "x": 2008.0,
     "y": 4.1
    }
   ],
   "source": {
    "source": "ons",
    "series_id": "IPHRP",
    "status": "cached"
   }
  },
  "sentences": [
   "When prices rise, the same money buys less.",
   "Your rent rose faster than your pay this year."
  ],
  "quiz": {
   "question": "If rent rises 4% and pay rises 2%, are you better off?",
   "options": [
    "Yes",
    "No",
    "Same"
   ],
   "answer_index": 1
  }
 },
 "concept_unlocked": "inflation"
}
"""#
    static let choiceResultDefault = #"""
{
 "life": {
  "id": "lf_8f3a2c",
  "seed": 424242,
  "mode": "preset",
  "character": {
   "id": "nurse-leeds",
   "name": "Amira",
   "emoji": "👩🏽‍⚕️",
   "sex": "female",
   "occupation": "nurse",
   "region": "yorkshire-and-the-humber",
   "town": "Leeds",
   "birth_year": 1982,
   "annual_income": 24800.0,
   "savings": 3200.0,
   "debt": 1500.0,
   "housing": "rent",
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "blurb": "NHS nurse renting in Leeds."
  },
  "start_year": 2006,
  "year": 2008,
  "age": 26,
  "alive": true,
  "stats": {
   "happiness": 72,
   "health": 88,
   "smarts": 64,
   "money": 41
  },
  "finances": {
   "cash": 1200.0,
   "savings": 3200.0,
   "investments": 0.0,
   "crypto": 0.0,
   "pension": 4100.0,
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "other_debt": 1500.0,
   "student_loan": 18000.0,
   "annual_income": 24800.0,
   "monthly_costs": 1450.0,
   "net_worth": -11000.0
  },
  "index": {
   "value": 101.4,
   "r_player": -0.36,
   "r_autopilot": -0.4,
   "missed_payments": 0,
   "max_drawdown": 0.05
  },
  "job": {
   "title": "Staff nurse",
   "employer": "Leeds Teaching Hospitals",
   "annual_income": 24800.0,
   "years_in_role": 2,
   "employer_status": "active"
  },
  "assets": [
   {
    "id": "as1",
    "kind": "pension",
    "name": "NHS pension",
    "value": 4100.0
   }
  ],
  "relationships": [
   {
    "id": "rl1",
    "kind": "parent",
    "name": "Mum",
    "emoji": "👩🏽",
    "closeness": 80
   }
  ],
  "pending_events": [],
  "available_actions": [
   {
    "tab": "job",
    "id": "ask_raise",
    "label": "Ask for a pay rise",
    "emoji": "🙋",
    "enabled": true,
    "paid": false
   },
   {
    "tab": "money",
    "id": "open_isa",
    "label": "Open a savings account",
    "emoji": "🏦",
    "hint": "Tax-free savings",
    "enabled": true,
    "paid": false
   }
  ],
  "history": [
   {
    "year": 2007,
    "age": 25,
    "text": "You started at Leeds General.",
    "net_worth": -12500.0,
    "autopilot_net_worth": -12500.0,
    "index": 100.0
   }
  ],
  "ribbons": [],
  "concepts_unlocked": [
   "compound-interest"
  ],
  "rewind": {
   "free_left": 1,
   "has_pass": false
  },
  "reached_present": false
 },
 "outcome": {
  "event_id": "ev-2008-1",
  "choice_id": "accept",
  "text": "You paid the higher rent.",
  "text_source": "template",
  "deltas": {
   "money": -540.0,
   "happiness": -1,
   "health": 0,
   "smarts": 0
  },
  "facts": {
   "yearly_cost": 540.0
  },
  "good": false
 }
}
"""#
    static let actionResult = #"""
{
 "life": {
  "id": "lf_8f3a2c",
  "seed": 424242,
  "mode": "preset",
  "character": {
   "id": "nurse-leeds",
   "name": "Amira",
   "emoji": "👩🏽‍⚕️",
   "sex": "female",
   "occupation": "nurse",
   "region": "yorkshire-and-the-humber",
   "town": "Leeds",
   "birth_year": 1982,
   "annual_income": 24800.0,
   "savings": 3200.0,
   "debt": 1500.0,
   "housing": "rent",
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "blurb": "NHS nurse renting in Leeds."
  },
  "start_year": 2006,
  "year": 2008,
  "age": 26,
  "alive": true,
  "stats": {
   "happiness": 72,
   "health": 88,
   "smarts": 64,
   "money": 41
  },
  "finances": {
   "cash": 1200.0,
   "savings": 3200.0,
   "investments": 0.0,
   "crypto": 0.0,
   "pension": 4100.0,
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "other_debt": 1500.0,
   "student_loan": 18000.0,
   "annual_income": 24800.0,
   "monthly_costs": 1450.0,
   "net_worth": -11000.0
  },
  "index": {
   "value": 101.4,
   "r_player": -0.36,
   "r_autopilot": -0.4,
   "missed_payments": 0,
   "max_drawdown": 0.05
  },
  "job": {
   "title": "Staff nurse",
   "employer": "Leeds Teaching Hospitals",
   "annual_income": 24800.0,
   "years_in_role": 2,
   "employer_status": "active"
  },
  "assets": [
   {
    "id": "as1",
    "kind": "pension",
    "name": "NHS pension",
    "value": 4100.0
   }
  ],
  "relationships": [
   {
    "id": "rl1",
    "kind": "parent",
    "name": "Mum",
    "emoji": "👩🏽",
    "closeness": 80
   }
  ],
  "pending_events": [
   {
    "id": "ev-2008-1",
    "template_id": "home.rent_rise",
    "area": "home",
    "year": 2008,
    "age": 26,
    "emoji": "🏠",
    "title": "Your rent is going up",
    "text": "Your landlord wants £45 more a month. Rents in your area rose 4.1% this year.",
    "text_source": "template",
    "choices": [
     {
      "id": "accept",
      "label": "Pay it",
      "emoji": "💷",
      "hint": "-£540 a year",
      "is_default": true
     },
     {
      "id": "move",
      "label": "Move somewhere cheaper",
      "emoji": "📦",
      "hint": "-£600 once, then -£360 a year",
      "is_default": false
     }
    ],
    "facts": {
     "rent_increase_monthly": 45.0,
     "rent_change_pct": 4.1
    },
    "sources": [
     {
      "source": "ons",
      "series_id": "IPHRP",
      "status": "cached",
      "note": "UK average used"
     }
    ],
    "concept_id": "inflation"
   }
  ],
  "available_actions": [
   {
    "tab": "job",
    "id": "ask_raise",
    "label": "Ask for a pay rise",
    "emoji": "🙋",
    "enabled": true,
    "paid": false
   },
   {
    "tab": "money",
    "id": "open_isa",
    "label": "Open a savings account",
    "emoji": "🏦",
    "hint": "Tax-free savings",
    "enabled": true,
    "paid": false
   }
  ],
  "history": [
   {
    "year": 2007,
    "age": 25,
    "text": "You started at Leeds General.",
    "net_worth": -12500.0,
    "autopilot_net_worth": -12500.0,
    "index": 100.0
   }
  ],
  "ribbons": [],
  "concepts_unlocked": [
   "compound-interest"
  ],
  "rewind": {
   "free_left": 1,
   "has_pass": false
  },
  "reached_present": false
 },
 "outcome": {
  "event_id": "action",
  "choice_id": "open_isa",
  "text": "You opened a savings account.",
  "text_source": "template",
  "deltas": {
   "money": -600.0,
   "happiness": -3,
   "health": 0,
   "smarts": 0
  },
  "facts": {
   "one_off_cost": 600.0
  },
  "good": true
 }
}
"""#
    static let rewindResult = #"""
{
 "life": {
  "id": "lf_8f3a2c",
  "seed": 424242,
  "mode": "preset",
  "character": {
   "id": "nurse-leeds",
   "name": "Amira",
   "emoji": "👩🏽‍⚕️",
   "sex": "female",
   "occupation": "nurse",
   "region": "yorkshire-and-the-humber",
   "town": "Leeds",
   "birth_year": 1982,
   "annual_income": 24800.0,
   "savings": 3200.0,
   "debt": 1500.0,
   "housing": "rent",
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "blurb": "NHS nurse renting in Leeds."
  },
  "start_year": 2006,
  "year": 2008,
  "age": 26,
  "alive": true,
  "stats": {
   "happiness": 72,
   "health": 88,
   "smarts": 64,
   "money": 41
  },
  "finances": {
   "cash": 1200.0,
   "savings": 3200.0,
   "investments": 0.0,
   "crypto": 0.0,
   "pension": 4100.0,
   "property_value": 0.0,
   "mortgage_balance": 0.0,
   "other_debt": 1500.0,
   "student_loan": 18000.0,
   "annual_income": 24800.0,
   "monthly_costs": 1450.0,
   "net_worth": -11000.0
  },
  "index": {
   "value": 101.4,
   "r_player": -0.36,
   "r_autopilot": -0.4,
   "missed_payments": 0,
   "max_drawdown": 0.05
  },
  "job": {
   "title": "Staff nurse",
   "employer": "Leeds Teaching Hospitals",
   "annual_income": 24800.0,
   "years_in_role": 2,
   "employer_status": "active"
  },
  "assets": [
   {
    "id": "as1",
    "kind": "pension",
    "name": "NHS pension",
    "value": 4100.0
   }
  ],
  "relationships": [
   {
    "id": "rl1",
    "kind": "parent",
    "name": "Mum",
    "emoji": "👩🏽",
    "closeness": 80
   }
  ],
  "pending_events": [
   {
    "id": "ev-2008-1",
    "template_id": "home.rent_rise",
    "area": "home",
    "year": 2008,
    "age": 26,
    "emoji": "🏠",
    "title": "Your rent is going up",
    "text": "Your landlord wants £45 more a month. Rents in your area rose 4.1% this year.",
    "text_source": "template",
    "choices": [
     {
      "id": "accept",
      "label": "Pay it",
      "emoji": "💷",
      "hint": "-£540 a year",
      "is_default": true
     },
     {
      "id": "move",
      "label": "Move somewhere cheaper",
      "emoji": "📦",
      "hint": "-£600 once, then -£360 a year",
      "is_default": false
     }
    ],
    "facts": {
     "rent_increase_monthly": 45.0,
     "rent_change_pct": 4.1
    },
    "sources": [
     {
      "source": "ons",
      "series_id": "IPHRP",
      "status": "cached",
      "note": "UK average used"
     }
    ],
    "concept_id": "inflation"
   }
  ],
  "available_actions": [
   {
    "tab": "job",
    "id": "ask_raise",
    "label": "Ask for a pay rise",
    "emoji": "🙋",
    "enabled": true,
    "paid": false
   },
   {
    "tab": "money",
    "id": "open_isa",
    "label": "Open a savings account",
    "emoji": "🏦",
    "hint": "Tax-free savings",
    "enabled": true,
    "paid": false
   }
  ],
  "history": [
   {
    "year": 2007,
    "age": 25,
    "text": "You started at Leeds General.",
    "net_worth": -12500.0,
    "autopilot_net_worth": -12500.0,
    "index": 100.0
   }
  ],
  "ribbons": [],
  "concepts_unlocked": [
   "compound-interest"
  ],
  "rewind": {
   "free_left": 1,
   "has_pass": false
  },
  "reached_present": false
 },
 "abandoned_index": 96.2,
 "abandoned_net_worth": -12100.0
}
"""#
    static let summary = #"""
{
 "life_id": "lf_8f3a2c",
 "name": "Amira",
 "born": 1982,
 "died": 2061,
 "age": 79,
 "cause_of_death": "Old age",
 "final_index": 118.5,
 "net_worth": 312000.0,
 "autopilot_net_worth": 241000.0,
 "ribbons": [
  {
   "id": "steady",
   "title": "Steady Hand",
   "emoji": "🎗️",
   "reason": "No missed payments in 2008"
  }
 ],
 "key_moments": [
  {
   "year": 2008,
   "age": 26,
   "emoji": "📉",
   "text": "Kept saving through the crash"
  }
 ],
 "concepts_unlocked": 14,
 "timeline": [
  {
   "year": 2007,
   "age": 25,
   "text": "You started at Leeds General.",
   "net_worth": -12500.0,
   "autopilot_net_worth": -12500.0,
   "index": 100.0
  }
 ]
}
"""#
    static let concepts = #"""
{
 "concepts": [
  {
   "id": "inflation",
   "title": "Inflation",
   "emoji": "🎈",
   "area": "money",
   "summary": "Prices rise over time.",
   "lesson": {
    "concept_id": "inflation",
    "title": "Prices creep up",
    "chart": {
     "kind": "line",
     "title": "Rent change per year",
     "x_label": "Year",
     "y_label": "%",
     "points": [
      {
       "x": 2006.0,
       "y": 3.2
      },
      {
       "x": 2007.0,
       "y": 3.9
      },
      {
       "x": 2008.0,
       "y": 4.1
      }
     ],
     "source": {
      "source": "ons",
      "series_id": "IPHRP",
      "status": "cached"
     }
    },
    "sentences": [
     "When prices rise, the same money buys less.",
     "Your rent rose faster than your pay this year."
    ],
    "quiz": {
     "question": "If rent rises 4% and pay rises 2%, are you better off?",
     "options": [
      "Yes",
      "No",
      "Same"
     ],
     "answer_index": 1
    }
   }
  }
 ]
}
"""#
    static let challenges = #"""
{
 "challenges": [
  {
   "id": "home-by-30",
   "title": "Own a home by 30",
   "emoji": "🏡",
   "description": "Buy any home before you turn 30.",
   "character_id": "nurse-leeds",
   "start_year": 2006,
   "goal": {
    "type": "own_home_by_age",
    "age": 30.0
   }
  }
 ]
}
"""#
    static let decision = #"""
{
 "question": "Your mortgage deal ends in 3 months. Fix for 2 or 5 years?",
 "headline": "Fix for 5 years.",
 "action": "fix_5y",
 "reasons": [
  "Your payment stays at £1,050 a month until 2031.",
  "Rates in similar past periods rose more often than they fell."
 ],
 "evidence": {
  "twins_count": 40,
  "periods": [
   "1989-1991",
   "2006-2008",
   "2022-2024"
  ],
  "success_rate": 0.7,
  "sentence": "7 in 10 twins in similar past periods did better."
 },
 "alternatives": [
  {
   "action": "fix_2y",
   "score": 0.41,
   "success_rate": 0.3
  },
  {
   "action": "tracker",
   "score": 0.22,
   "success_rate": 0.2
  }
 ],
 "sources": [
  {
   "source": "boe",
   "series_id": "IUMBEDR",
   "status": "live"
  },
  {
   "source": "boe",
   "series_id": "IUMBV42",
   "status": "live"
  },
  {
   "source": "landregistry",
   "series_id": "ukhpi/yorkshire-and-the-humber",
   "status": "cached"
  }
 ],
 "disclaimer": "Education, not financial advice. Check with a regulated adviser.",
 "generated_at": "2026-10-17T12:00:00Z"
}
"""#
    static let decisionRequest = #"""
{
 "profile": {
  "age": 34,
  "region": "yorkshire-and-the-humber",
  "annual_income": 38000.0,
  "savings": 9000.0,
  "other_debt": 0.0,
  "housing": "mortgage",
  "property_value": 240000.0,
  "mortgage_balance": 180000.0,
  "mortgage_years_left": 25,
  "deal_ends_in_months": 3
 }
}
"""#
    static let evaluation = #"""
{
 "method": "Leave-one-period-out backtest, k-NN on standardised macro state",
 "n": 24,
 "hit_rate": 0.67,
 "baseline_hit_rate": 0.5,
 "baseline": "always fix 2 years",
 "periods": [
  {
   "start": 2006,
   "end": 2011,
   "recommended": "fix_5y",
   "realised_best": "fix_5y",
   "hit": true
  }
 ],
 "generated_at": "2026-10-17T12:00:00Z"
}
"""#
    static let room = #"""
{
 "code": "K7Q2ZP",
 "mode": "duel",
 "seed": 777001,
 "preset_id": "nurse-leeds",
 "start_year": 2021,
 "max_players": 2,
 "players": [
  {
   "id": "p1",
   "name": "Ash",
   "is_host": true,
   "finished": false
  }
 ],
 "join_url": "lifeline://join/K7Q2ZP",
 "qr_png_base64": "iVBORw0KGgo=",
 "status": "lobby"
}
"""#
    static let bankAuthLink = #"""
{
 "url": "https://auth.truelayer-sandbox.com/?response_type=code&state=abc",
 "state": "abc",
 "provider": "truelayer",
 "status": "mock"
}
"""#
    static let bankSummary = #"""
{
 "status": "mock",
 "provider": "truelayer",
 "profile": {
  "age": 34,
  "region": "yorkshire-and-the-humber",
  "annual_income": 38000.0,
  "savings": 9000.0,
  "other_debt": 0.0,
  "housing": "mortgage",
  "property_value": 240000.0,
  "mortgage_balance": 180000.0,
  "mortgage_years_left": 25,
  "deal_ends_in_months": 3
 },
 "accounts": 2
}
"""#
    static let purchaseVerifyResponse = #"""
{
 "product_id": "lifeline.rewindpass",
 "entitlement": "rewind_pass",
 "active": true,
 "demo": true,
 "label": "Demo payment"
}
"""#
    static let sources = #"""
{
 "sources": [
  {
   "id": "boe",
   "name": "Bank of England IADB",
   "status": "live",
   "fetched_at": "2026-10-17T11:00:00",
   "ttl_seconds": 86400,
   "coverage": "UK",
   "attribution": "Bank of England",
   "licence": "Bank of England terms",
   "needs_key": false
  },
  {
   "id": "companieshouse",
   "name": "Companies House",
   "status": "mock",
   "ttl_seconds": 86400,
   "coverage": "UK",
   "attribution": "Companies House",
   "licence": "OGL v3.0",
   "needs_key": true,
   "last_error": "COMPANIES_HOUSE_KEY not set"
  }
 ]
}
"""#
    static let token = #"""
{
 "access_token": "eyJhbGciOiJIUzI1NiJ9.demo.sig",
 "token_type": "bearer",
 "expires_in": 86400
}
"""#
}
