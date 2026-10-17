// GENERATED from contracts/openapi.yaml `components.examples` (connections, investments, habits, ISA).
// Do not hand-edit. Regenerate when the contract examples change.

extension PreviewJSON {
    static let connections = #"""
{
  "providers": [
    {
      "provider": "monzo",
      "connected": true,
      "data_status": "live",
      "hint": "…a1b2",
      "oauth_available": true,
      "history": {
        "synced": true,
        "oldest": "2024-10-18",
        "count": 1342
      }
    },
    {
      "provider": "trading212",
      "connected": false,
      "data_status": "mock",
      "oauth_available": false
    }
  ]
}
"""#

    static let providerConnection = #"""
{
  "provider": "monzo",
  "connected": true,
  "data_status": "live",
  "hint": "…a1b2",
  "oauth_available": true,
  "history": {
    "synced": true,
    "oldest": "2024-10-18",
    "count": 1342
  }
}
"""#

    static let historyStatus = #"""
{
  "synced": false,
  "count": 0,
  "last_error": "auth"
}
"""#

    static let investments = #"""
{
  "meta": {
    "data_status": "live",
    "source": "monzo+trading212",
    "as_of": "2026-10-17"
  },
  "holdings": [
    {
      "instrument_id": "VUSAl_EQ",
      "name": "Vanguard S&P 500",
      "quantity": 10.0,
      "value": 900.0,
      "asset_class": "equity",
      "region": "US"
    },
    {
      "instrument_id": "VGOV_EQ",
      "name": "Vanguard UK Gilts",
      "quantity": 20.0,
      "value": 380.5,
      "asset_class": "bond",
      "region": "UK"
    }
  ],
  "total_value": 1280.5,
  "cash": 42.0,
  "allocation": {
    "bond": 29.71,
    "equity": 70.29
  }
}
"""#

    static let habitFactors = #"""
{
  "version": "hf-1",
  "window": {
    "months": 6,
    "end": "2026-09-30"
  },
  "factors": [
    {
      "id": "savings_rate",
      "label": "Money you keep",
      "explainer": "The share of what you earn that you do not spend.",
      "raw": 0.18,
      "score": 70
    }
  ],
  "overall": 70
}
"""#

    static let isaPeriods = #"""
{
  "periods": [
    {
      "id": "gfc_2008",
      "label": "The 2008 financial crisis",
      "start": "2007-10",
      "end": "2012-12"
    }
  ],
  "assets": [
    "global_equity",
    "uk_equity",
    "gilts",
    "cash"
  ],
  "label": "Synthetic illustrative returns",
  "data_status": "mock"
}
"""#

    static let isaBacktestResponse = #"""
{
  "results": [
    {
      "period": "gfc_2008",
      "label": "the 2008 financial crisis",
      "months": [
        "2007-09",
        "2007-10",
        "2007-11"
      ],
      "index": [
        100.0,
        101.2,
        99.5
      ],
      "metrics": {
        "cagr": 0.042,
        "volatility": 0.13,
        "max_drawdown": 0.31,
        "months_to_recover": 38,
        "worst_12m": -0.27
      },
      "contributed": 3600.0,
      "final_value": 4310.4,
      "money_weighted_return": 0.051,
      "data_status": "mock",
      "data_label": "Synthetic illustrative returns"
    }
  ],
  "monthly_contribution": 150.0,
  "contribution_source": "request",
  "label": "Synthetic illustrative returns",
  "data_status": "mock"
}
"""#

    static let isaScenarios = #"""
{
  "paths": [
    {
      "start_month": "2009-03",
      "index": [
        100.0,
        101.5,
        103.2
      ]
    }
  ],
  "fan": {
    "p10": [
      100.0,
      98.0,
      97.1
    ],
    "p50": [
      100.0,
      101.5,
      103.2
    ],
    "p90": [
      100.0,
      104.0,
      107.9
    ]
  },
  "horizon_months": 2,
  "label": "Modelled scenarios from similar past periods. Not a forecast. Not financial advice.",
  "data_status": "mock",
  "data_label": "Synthetic illustrative returns"
}
"""#

}
