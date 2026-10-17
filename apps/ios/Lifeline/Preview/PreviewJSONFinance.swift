// GENERATED from contracts/openapi.yaml `components.examples` (finance, next move, plan, lives).
// Do not hand-edit. Regenerate with the W6 script when the contract examples change.

extension PreviewJSON {
    static let financeOverview = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "balance": 8040.22,
 "net_worth": 7627.72,
 "accounts": [
  {
   "id": "acc_cur",
   "name": "Everyday",
   "kind": "current",
   "provider": "Sample Bank",
   "balance": 1840.22,
   "currency": "GBP"
  },
  {
   "id": "acc_sav",
   "name": "Rainy day",
   "kind": "savings",
   "provider": "Sample Bank",
   "balance": 6200.0,
   "currency": "GBP"
  },
  {
   "id": "acc_cc",
   "name": "Credit card",
   "kind": "credit",
   "provider": "Sample Bank",
   "balance": -412.5,
   "currency": "GBP"
  }
 ],
 "balance_history": [
  {
   "date": "2026-08-31",
   "value": 7420.1
  },
  {
   "date": "2026-09-30",
   "value": 7790.55
  },
  {
   "date": "2026-10-17",
   "value": 8040.22
  }
 ],
 "net_worth_history": [
  {
   "date": "2026-08-31",
   "value": 6980.0
  },
  {
   "date": "2026-09-30",
   "value": 7350.4
  },
  {
   "date": "2026-10-17",
   "value": 7627.72
  }
 ]
}
"""#

    static let spending = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "month": "2026-10",
 "total": 1236.4,
 "categories": [
  {
   "category": "housing",
   "label": "Rent and home",
   "emoji": "🏠",
   "amount": 850.0,
   "share": 0.687,
   "transactions": 1,
   "change_pct": 0.0
  },
  {
   "category": "groceries",
   "label": "Groceries",
   "emoji": "🛒",
   "amount": 214.3,
   "share": 0.173,
   "transactions": 9,
   "change_pct": 6.2
  },
  {
   "category": "eating_out",
   "label": "Eating out",
   "emoji": "🍜",
   "amount": 172.1,
   "share": 0.139,
   "transactions": 7,
   "change_pct": -12.5
  }
 ]
}
"""#

    static let subscriptions = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "monthly_total": 37.98,
 "count": 2,
 "items": [
  {
   "id": "sub_netflix",
   "merchant": "Netflix",
   "emoji": "📺",
   "category": "subscriptions",
   "amount": 12.99,
   "cadence": "monthly",
   "monthly_cost": 12.99,
   "next_payment": "2026-10-28",
   "price_rise": {
    "from_amount": 10.99,
    "to_amount": 12.99,
    "since": "2026-06-28"
   }
  },
  {
   "id": "sub_gym",
   "merchant": "PureGym",
   "emoji": "🏋️",
   "category": "health",
   "amount": 24.99,
   "cadence": "monthly",
   "monthly_cost": 24.99,
   "next_payment": "2026-11-01"
  }
 ]
}
"""#

    static let bills = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "total_next_30_days": 887.98,
 "items": [
  {
   "id": "bill_rent",
   "name": "Rent",
   "emoji": "🏠",
   "kind": "rent",
   "amount": 850.0,
   "due_date": "2026-11-01",
   "status": "due_soon"
  },
  {
   "id": "bill_netflix",
   "name": "Netflix",
   "emoji": "📺",
   "kind": "subscription",
   "amount": 12.99,
   "due_date": "2026-10-28",
   "status": "upcoming"
  }
 ]
}
"""#

    static let budgets = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "month": "2026-10",
 "items": [
  {
   "category": "eating_out",
   "label": "Eating out",
   "emoji": "🍜",
   "limit": 150.0,
   "spent": 172.1,
   "progress": 1.147,
   "status": "over"
  },
  {
   "category": "groceries",
   "label": "Groceries",
   "emoji": "🛒",
   "limit": 300.0,
   "spent": 214.3,
   "progress": 0.714,
   "status": "ok"
  }
 ]
}
"""#

    static let goals = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "items": [
  {
   "id": "goal_house",
   "name": "House deposit",
   "emoji": "🏡",
   "target": 20000.0,
   "saved": 6200.0,
   "progress": 0.31,
   "target_date": "2029-06-01",
   "monthly_needed": 429.0
  }
 ]
}
"""#

    static let goal = #"""
{
 "id": "goal_holiday",
 "name": "Holiday",
 "emoji": "🏖️",
 "target": 1500.0,
 "saved": 0.0,
 "progress": 0.0,
 "target_date": "2027-07-01",
 "monthly_needed": 166.67
}
"""#

    static let financeProfile = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "profile": {
  "age": 34,
  "region": "yorkshire-and-the-humber",
  "annual_income": 38000.0,
  "savings": 6200.0,
  "other_debt": 412.5,
  "housing": "rent",
  "monthly_rent": 850.0
 },
 "character": {
  "name": "You",
  "emoji": "🙂",
  "sex": "female",
  "occupation": "analyst",
  "region": "yorkshire-and-the-humber",
  "town": "Leeds",
  "birth_year": 1992,
  "annual_income": 38000.0,
  "savings": 6200.0,
  "debt": 412.5,
  "housing": "rent",
  "property_value": 0.0,
  "mortgage_balance": 0.0
 },
 "personal_facts": [
  {
   "id": "subs_monthly",
   "concept_id": "subscriptions",
   "text": "You spend £47 a month on 6 subscriptions.",
   "facts": {
    "monthly_total": 47.0,
    "count": 6.0
   }
  }
 ]
}
"""#

    static let spendPrediction = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "date": "2026-10-17",
 "predicted": 38.4,
 "low": 12.0,
 "high": 71.5,
 "baseline": 24.1,
 "reasons": [
  {
   "feature": "weekday",
   "label": "It is Friday",
   "effect": 9.8
  },
  {
   "feature": "payday",
   "label": "You were paid 2 days ago",
   "effect": 6.2
  },
  {
   "feature": "rain",
   "label": "Rain is forecast (6 mm)",
   "effect": -1.7
  }
 ],
 "weather": {
  "summary": "Light rain",
  "temp_max_c": 13.5,
  "rain_mm": 6.0,
  "status": "live"
 },
 "is_bank_holiday": false,
 "days_to_payday": 27,
 "guess": {
  "amount": 30.0,
  "made_at": "2026-10-17T08:05:00Z"
 },
 "model": {
  "name": "ridge regression on log spend",
  "trained_on_days": 180,
  "mae": 11.3,
  "baseline_mae": 14.9,
  "interval_coverage": 0.81
 }
}
"""#

    static let guesses = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "points_total": 412,
 "streak": 3,
 "best_streak": 5,
 "items": [
  {
   "date": "2026-10-16",
   "guess": 25.0,
   "predicted": 27.9,
   "actual": 24.1,
   "points": 96,
   "beat_model": true
  }
 ]
}
"""#

    static let predictionEvaluation = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "method": "Walk-forward: train on days before each test day, predict the next day",
 "n_days": 90,
 "mae": 11.3,
 "baseline_mae": 14.9,
 "baseline": "Average spend for that weekday",
 "interval_coverage": 0.81,
 "days": [
  {
   "date": "2026-10-16",
   "predicted": 27.9,
   "low": 9.0,
   "high": 55.2,
   "actual": 24.1,
   "baseline": 22.0
  }
 ]
}
"""#

    static let lives = #"""
{
 "lives": [
  {
   "id": "lf_8f3a2c",
   "name": "Amira",
   "emoji": "👩🏽‍⚕️",
   "mode": "preset",
   "year": 2008,
   "age": 26,
   "alive": true,
   "index": 101.4,
   "net_worth": -11000.0,
   "ribbons": 0
  }
 ]
}
"""#

    static let nextMove = #"""
{
 "meta": {
  "data_status": "mock",
  "source": "fixtures",
  "as_of": "2026-10-17",
  "label": "Sample data"
 },
 "question": "Where should my money go this month?",
 "top": {
  "id": "mv_fix_mortgage",
  "kind": "fix_mortgage",
  "action": "Fix for 5 years",
  "headline": "Your deal ends in 165 days",
  "impact_per_year": 1240.0,
  "worst_case_per_year": -310.0,
  "confidence": 0.7,
  "confidence_label": "7 in 10 twins in similar past periods did better",
  "evidence": [
   {
    "text": "5-year fixes are 4.21% today, 2-year fixes 4.38%.",
    "facts": {
     "fix_5y_pct": 4.21,
     "fix_2y_pct": 4.38
    },
    "source": {
     "source": "boe",
     "series_id": "IUMBV42",
     "status": "live"
    }
   },
   {
    "text": "In 2021-2023, Bank Rate rose from 0.1% to 5.25%.",
    "facts": {
     "bank_rate_start": 0.1,
     "bank_rate_end": 5.25
    },
    "source": {
     "source": "boe",
     "series_id": "IUMBEDR",
     "status": "live"
    }
   },
   {
    "text": "Your payment would be £1,050 a month on a £180,000 balance.",
    "facts": {
     "monthly_payment": 1050.0,
     "balance": 180000.0
    }
   }
  ],
  "sources": [
   {
    "source": "boe",
    "series_id": "IUMBV42",
    "status": "live"
   },
   {
    "source": "boe",
    "series_id": "IUMBV34",
    "status": "live"
   },
   {
    "source": "boe",
    "series_id": "IUMBEDR",
    "status": "live"
   }
  ],
  "options": [
   {
    "id": "fix_5y",
    "label": "Fix for 5 years",
    "is_recommended": true
   },
   {
    "id": "fix_2y",
    "label": "Fix for 2 years",
    "is_recommended": false
   },
   {
    "id": "tracker",
    "label": "Tracker",
    "is_recommended": false
   }
  ],
  "deadline": "2027-03-31",
  "days_left": 165,
  "testable": true,
  "test_period": {
   "start": 2021,
   "end": 2023,
   "label": "2021-2023 rate shock"
  },
  "concept_id": "fixed-vs-variable"
 },
 "runners_up": [
  {
   "id": "mv_cancel_subs",
   "kind": "cancel_subscription",
   "action": "Cancel 2 unused subscriptions",
   "headline": "You pay £22 a month for 2 services you have not used since July",
   "impact_per_year": 264.0,
   "worst_case_per_year": 264.0,
   "confidence": 0.9,
   "confidence_label": "Based on your own payments",
   "evidence": [
    {
     "text": "Netflix rose from £10.99 to £12.99 in June.",
     "facts": {
      "from": 10.99,
      "to": 12.99
     }
    },
    {
     "text": "No activity with these merchants for 3 months.",
     "facts": {
      "months": 3.0
     }
    },
    {
     "text": "You spend £47 a month on 6 subscriptions.",
     "facts": {
      "monthly": 47.0,
      "count": 6.0
     }
    }
   ],
   "sources": [],
   "options": [
    {
     "id": "cancel",
     "label": "Cancel both",
     "is_recommended": true
    },
    {
     "id": "keep",
     "label": "Keep them",
     "is_recommended": false
    }
   ],
   "testable": false,
   "concept_id": "subscriptions"
  }
 ],
 "backtest": {
  "method": "Walk-forward over past deal-end dates, 1995-2023",
  "n": 58,
  "hit_rate": 0.69,
  "baseline": "Always fix for 2 years",
  "baseline_hit_rate": 0.41
 },
 "generated_at": "2026-10-17T12:00:00Z"
}
"""#

    static let testMoveResult = #"""
{
 "move_id": "mv_fix_mortgage",
 "period": {
  "start": 2021,
  "end": 2023,
  "label": "2021-2023 rate shock"
 },
 "character": {
  "name": "You",
  "emoji": "🙂",
  "sex": "female",
  "occupation": "analyst",
  "region": "yorkshire-and-the-humber",
  "town": "Leeds",
  "birth_year": 1992,
  "annual_income": 38000.0,
  "savings": 6200.0,
  "debt": 0.0,
  "housing": "mortgage",
  "property_value": 240000.0,
  "mortgage_balance": 180000.0
 },
 "outcomes": [
  {
   "option_id": "fix_5y",
   "label": "Fix for 5 years",
   "is_recommended": true,
   "life_id": "lf_t5y001",
   "net_worth_path": [
    {
     "date": "2021-12-31",
     "value": 66000.0
    },
    {
     "date": "2022-12-31",
     "value": 71200.0
    },
    {
     "date": "2023-12-31",
     "value": 77900.0
    }
   ],
   "end_net_worth": 77900.0,
   "total_cost": 37800.0,
   "missed_payments": 0,
   "worst_year": 2022,
   "worst_year_change": 5200.0,
   "index": 104.2
  },
  {
   "option_id": "fix_2y",
   "label": "Fix for 2 years",
   "is_recommended": false,
   "life_id": "lf_t2y001",
   "net_worth_path": [
    {
     "date": "2021-12-31",
     "value": 66000.0
    },
    {
     "date": "2022-12-31",
     "value": 70100.0
    },
    {
     "date": "2023-12-31",
     "value": 73720.0
    }
   ],
   "end_net_worth": 73720.0,
   "total_cost": 41980.0,
   "missed_payments": 0,
   "worst_year": 2023,
   "worst_year_change": 3620.0,
   "index": 100.0
  }
 ],
 "summary": "Fixing for 5 years left you £4,180 better off by 2023.",
 "evidence_sentence": "7 in 10 twins in similar past periods did better.",
 "sources": [
  {
   "source": "boe",
   "series_id": "IUMBV42",
   "status": "live"
  },
  {
   "source": "boe",
   "series_id": "IUMBV34",
   "status": "live"
  },
  {
   "source": "boe",
   "series_id": "IUMBEDR",
   "status": "live"
  }
 ]
}
"""#

    static let planItem = #"""
{
 "id": "pl_1",
 "move_id": "mv_fix_mortgage",
 "kind": "fix_mortgage",
 "action": "Fix for 5 years",
 "impact_per_year": 1240.0,
 "added_at": "2026-10-17T12:00:00Z",
 "status": "todo"
}
"""#

    static let plan = #"""
{
 "items": [
  {
   "id": "pl_1",
   "move_id": "mv_fix_mortgage",
   "kind": "fix_mortgage",
   "action": "Fix for 5 years",
   "impact_per_year": 1240.0,
   "added_at": "2026-10-17T12:00:00Z",
   "status": "todo"
  }
 ],
 "total_impact_per_year": 1240.0
}
"""#

}
