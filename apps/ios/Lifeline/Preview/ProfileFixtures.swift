import Foundation

/// Contract-shaped `GET /v1/profile/stats` answers for previews, the Playground and tests. Four states:
/// nothing connected, Trading 212 only, Monzo and Trading 212, a sample student.
enum ProfileFixtures {
    enum Scenario: String, CaseIterable, Sendable {
        case nothing, t212Only, monzoAndT212, sampleStudent
    }

    static func stats(_ scenario: Scenario) -> ProfileStats {
        ContractExamples.decode(json(scenario))
    }

    static func json(_ scenario: Scenario) -> String {
        switch scenario {
        case .nothing: #"""
{
 "connections": [
  {
   "id": "monzo",
   "title": "Monzo",
   "connected": false
  },
  {
   "id": "trading212",
   "title": "Trading 212",
   "connected": false
  },
  {
   "id": "statement",
   "title": "Statement",
   "connected": false
  },
  {
   "id": "manual",
   "title": "Your numbers",
   "connected": false
  },
  {
   "id": "sample",
   "title": "Sample student",
   "connected": false
  }
 ],
 "sections": [
  {
   "id": "habits",
   "title": "Your habits",
   "available": false,
   "sources": [],
   "missing_hint": "Connect Monzo, upload a statement or use a sample student to see your habits."
  },
  {
   "id": "spending",
   "title": "Your spending",
   "available": false,
   "sources": [],
   "missing_hint": "Connect Monzo, upload a statement or use a sample student to see your spending."
  },
  {
   "id": "net_worth",
   "title": "Net worth",
   "available": false,
   "sources": [],
   "missing_hint": "Connect Monzo or Trading 212, upload a statement or enter your numbers to see your net worth."
  },
  {
   "id": "investments",
   "title": "Investments",
   "available": false,
   "sources": [],
   "missing_hint": "Connect Trading 212 to see your investments."
  }
 ]
}
"""#
        case .t212Only: #"""
{
 "connections": [
  {
   "id": "monzo",
   "title": "Monzo",
   "connected": false
  },
  {
   "id": "trading212",
   "title": "Trading 212",
   "connected": true,
   "data_status": "live",
   "last_synced": "2026-10-17",
   "provides": "8 holdings"
  },
  {
   "id": "statement",
   "title": "Statement",
   "connected": false
  },
  {
   "id": "manual",
   "title": "Your numbers",
   "connected": false
  },
  {
   "id": "sample",
   "title": "Sample student",
   "connected": false
  }
 ],
 "sections": [
  {
   "id": "habits",
   "title": "Your habits",
   "available": false,
   "sources": [],
   "missing_hint": "Connect Monzo, upload a statement or use a sample student to see your habits."
  },
  {
   "id": "spending",
   "title": "Your spending",
   "available": false,
   "sources": [],
   "missing_hint": "Connect Monzo, upload a statement or use a sample student to see your spending."
  },
  {
   "id": "net_worth",
   "title": "Net worth",
   "available": true,
   "sources": [
    "trading212"
   ],
   "net_worth": {
    "net_worth": 2140.0,
    "cash": 0,
    "investments": 2140.0,
    "other": 0,
    "parts": [
     {
      "label": "Trading 212 Stocks & Shares",
      "amount": 2140.0
     }
    ]
   }
  },
  {
   "id": "investments",
   "title": "Investments",
   "available": true,
   "sources": [
    "trading212"
   ],
   "investments": {
    "total_value": 2140.0,
    "invested_value": 1935.5,
    "holdings_count": 8,
    "mix": [
     {
      "asset_class": "equity",
      "label": "Shares",
      "value": 1530.5,
      "share_pct": 79.1
     },
     {
      "asset_class": "bond",
      "label": "Bonds",
      "value": 310.0,
      "share_pct": 16.0
     },
     {
      "asset_class": "commodity",
      "label": "Commodities",
      "value": 95.0,
      "share_pct": 4.9
     }
    ],
    "top_holdings": [
     {
      "instrument_id": "IE00B3XXRP09",
      "name": "Vanguard S&P 500",
      "quantity": 10,
      "value": 900.0,
      "asset_class": "equity",
      "region": "US"
     },
     {
      "instrument_id": "US0378331005",
      "name": "Apple",
      "quantity": 2.5,
      "value": 480.5,
      "asset_class": "equity",
      "region": "US"
     },
     {
      "instrument_id": "GB00B0V3WR38",
      "name": "UK Gilts ETF",
      "quantity": 30,
      "value": 310.0,
      "asset_class": "bond",
      "region": "UK"
     },
     {
      "instrument_id": "IE00B4L5Y983",
      "name": "iShares World",
      "quantity": 4,
      "value": 150.0,
      "asset_class": "equity",
      "region": "Global"
     },
     {
      "instrument_id": "SGLN",
      "name": "Physical Gold",
      "quantity": 3,
      "value": 95.0,
      "asset_class": "commodity"
     }
    ]
   }
  }
 ]
}
"""#
        case .monzoAndT212: #"""
{
 "connections": [
  {
   "id": "monzo",
   "title": "Monzo",
   "connected": true,
   "data_status": "live",
   "last_synced": "2026-10-17",
   "provides": "Transactions since 21 Jul 2026 (151)"
  },
  {
   "id": "trading212",
   "title": "Trading 212",
   "connected": true,
   "data_status": "live",
   "last_synced": "2026-10-17",
   "provides": "8 holdings"
  },
  {
   "id": "statement",
   "title": "Statement",
   "connected": false
  },
  {
   "id": "manual",
   "title": "Your numbers",
   "connected": false
  },
  {
   "id": "sample",
   "title": "Sample student",
   "connected": false
  }
 ],
 "sections": [
  {
   "id": "habits",
   "title": "Your habits",
   "available": true,
   "sources": [
    "monzo"
   ],
   "habits": {
    "components": {
     "savings_rate": 72,
     "months_of_cover": 40,
     "spend_stability": 81,
     "discretionary_share": 63,
     "subscription_creep": 90,
     "debt_pressure": 100
    },
    "overall": 74
   }
  },
  {
   "id": "spending",
   "title": "Your spending",
   "available": true,
   "sources": [
    "monzo"
   ],
   "spending": {
    "month": "2026-09",
    "partial": false,
    "months_used": 2,
    "monthly_in": 1250.0,
    "monthly_out": 586.3,
    "top_categories": [
     {
      "category": "groceries",
      "label": "Groceries",
      "emoji": "🛒",
      "amount": 182.4,
      "share": 0.31,
      "transactions": 19
     },
     {
      "category": "eating_out",
      "label": "Eating out",
      "emoji": "🍽️",
      "amount": 96.8,
      "share": 0.16,
      "transactions": 11
     },
     {
      "category": "transport",
      "label": "Transport",
      "emoji": "🚌",
      "amount": 64.2,
      "share": 0.11,
      "transactions": 14
     }
    ],
    "subscriptions_monthly": 37.98,
    "subscriptions_count": 2
   }
  },
  {
   "id": "net_worth",
   "title": "Net worth",
   "available": true,
   "sources": [
    "monzo",
    "trading212"
   ],
   "net_worth": {
    "net_worth": 3052.5,
    "cash": 912.5,
    "investments": 2140.0,
    "other": 0,
    "parts": [
     {
      "label": "Monzo current account",
      "amount": 912.5
     },
     {
      "label": "Trading 212 Stocks & Shares",
      "amount": 2140.0
     }
    ]
   }
  },
  {
   "id": "investments",
   "title": "Investments",
   "available": true,
   "sources": [
    "trading212"
   ],
   "investments": {
    "total_value": 2140.0,
    "invested_value": 1935.5,
    "holdings_count": 8,
    "mix": [
     {
      "asset_class": "equity",
      "label": "Shares",
      "value": 1530.5,
      "share_pct": 79.1
     },
     {
      "asset_class": "bond",
      "label": "Bonds",
      "value": 310.0,
      "share_pct": 16.0
     },
     {
      "asset_class": "commodity",
      "label": "Commodities",
      "value": 95.0,
      "share_pct": 4.9
     }
    ],
    "top_holdings": [
     {
      "instrument_id": "IE00B3XXRP09",
      "name": "Vanguard S&P 500",
      "quantity": 10,
      "value": 900.0,
      "asset_class": "equity",
      "region": "US"
     },
     {
      "instrument_id": "US0378331005",
      "name": "Apple",
      "quantity": 2.5,
      "value": 480.5,
      "asset_class": "equity",
      "region": "US"
     },
     {
      "instrument_id": "GB00B0V3WR38",
      "name": "UK Gilts ETF",
      "quantity": 30,
      "value": 310.0,
      "asset_class": "bond",
      "region": "UK"
     },
     {
      "instrument_id": "IE00B4L5Y983",
      "name": "iShares World",
      "quantity": 4,
      "value": 150.0,
      "asset_class": "equity",
      "region": "Global"
     },
     {
      "instrument_id": "SGLN",
      "name": "Physical Gold",
      "quantity": 3,
      "value": 95.0,
      "asset_class": "commodity"
     }
    ]
   }
  }
 ]
}
"""#
        case .sampleStudent: #"""
{
 "connections": [
  {
   "id": "monzo",
   "title": "Monzo",
   "connected": false
  },
  {
   "id": "trading212",
   "title": "Trading 212",
   "connected": false
  },
  {
   "id": "statement",
   "title": "Statement",
   "connected": false
  },
  {
   "id": "manual",
   "title": "Your numbers",
   "connected": false
  },
  {
   "id": "sample",
   "title": "Sample student",
   "connected": true,
   "data_status": "mock",
   "label": "Sample data",
   "last_synced": "2026-10-17",
   "provides": "Eilidh Fraser, 312 transactions since 1 Jul 2026",
   "sample_id": "scholarship"
  }
 ],
 "sections": [
  {
   "id": "habits",
   "title": "Your habits",
   "available": true,
   "sources": [
    "sample"
   ],
   "habits": {
    "components": {
     "savings_rate": 72,
     "months_of_cover": 40,
     "spend_stability": 81,
     "discretionary_share": 63,
     "subscription_creep": 90,
     "debt_pressure": 100
    },
    "overall": 74
   }
  },
  {
   "id": "spending",
   "title": "Your spending",
   "available": true,
   "sources": [
    "sample"
   ],
   "spending": {
    "month": "2026-09",
    "partial": false,
    "months_used": 2,
    "monthly_in": 1250.0,
    "monthly_out": 586.3,
    "top_categories": [
     {
      "category": "groceries",
      "label": "Groceries",
      "emoji": "🛒",
      "amount": 182.4,
      "share": 0.31,
      "transactions": 19
     },
     {
      "category": "eating_out",
      "label": "Eating out",
      "emoji": "🍽️",
      "amount": 96.8,
      "share": 0.16,
      "transactions": 11
     },
     {
      "category": "transport",
      "label": "Transport",
      "emoji": "🚌",
      "amount": 64.2,
      "share": 0.11,
      "transactions": 14
     }
    ],
    "subscriptions_monthly": 37.98,
    "subscriptions_count": 2
   }
  },
  {
   "id": "net_worth",
   "title": "Net worth",
   "available": true,
   "sources": [
    "sample"
   ],
   "net_worth": {
    "net_worth": 1260.4,
    "cash": 1260.4,
    "investments": 0,
    "other": 0,
    "parts": [
     {
      "label": "Current account",
      "amount": 1260.4
     }
    ]
   }
  },
  {
   "id": "investments",
   "title": "Investments",
   "available": false,
   "sources": [],
   "missing_hint": "Connect Trading 212 to see your investments."
  }
 ]
}
"""#
        }
    }
}
