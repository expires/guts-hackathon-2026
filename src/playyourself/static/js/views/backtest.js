import { api, guard } from "../api.js";
import { draw, alpha } from "../charts.js";
import { $, el, fillTable, gbp, pct } from "../util.js";
import { toast } from "../toast.js";
import { bindExplain } from "./explain.js";

export const PRESETS = [
  { name: "100% global equity", weights: { global_equity: 1 } },
  { name: "80/20 equity/gilts", weights: { global_equity: 0.8, gilts: 0.2 } },
  { name: "60/40 equity/gilts", weights: { global_equity: 0.6, gilts: 0.4 } },
  { name: "UK only", weights: { uk_equity: 1 } },
];
let loaded = false;
let last = null;

export async function load() {
  if (loaded) return;
  const env = await api("/periods");
  $("bt-period").replaceChildren(...Object.entries(env.data.periods).map(([k, [a, b]]) => el("option", { value: k, textContent: k.replace(/_/g, " ") + " (" + a + " to " + b + ")" })));
  $("bt-presets").replaceChildren(
    ...PRESETS.map((p, i) =>
      el("label", { className: "chip" }, Object.assign(el("input", { type: "checkbox", value: String(i) }), { checked: i < 3 }), el("span", { textContent: p.name }))
    )
  );
  loaded = true;
}

$("bt-run").addEventListener("click", guard(async () => {
  const chosen = [...$("bt-presets").querySelectorAll("input:checked")].map((i) => PRESETS[+i.value]);
  const hint = $("bt-hint");
  if (chosen.length < 1 || chosen.length > 3) {
    hint.hidden = false;
    toast("Pick between 1 and 3 strategies.", true);
    return;
  }
  hint.hidden = true;
  const period = $("bt-period").value, technique = $("bt-tech").value, rebalance = $("bt-reb").value;
  const btn = $("bt-run");
  btn.disabled = true;
  btn.classList.add("busy");
  try {
    const env = await api("/backtest", { method: "POST", body: { strategies: chosen.map((p) => ({ name: p.name, weights: p.weights, period, technique, rebalance })), include_local: true } });
    const res = env.data.results;
    last = res;
    $("bt-out").hidden = false;
    draw("c-bt", $("c-bt"), (t) => ({
      type: "line",
      data: {
        labels: res[0].months,
        datasets: res.map((r, i) => ({ label: r.name, data: r.index, borderColor: t.series[i], backgroundColor: alpha(t.series[i], 0.12), pointRadius: 0, pointHoverRadius: 4, borderWidth: 2.5, tension: 0.35 })),
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: { legend: { position: "bottom" }, tooltip: { callbacks: { label: (c) => " " + c.dataset.label + ": " + c.parsed.y.toFixed(1) } } },
        scales: { x: { ticks: { maxTicksLimit: 7 } }, y: { title: { display: true, text: "Index (start = 100)", color: t.muted } } },
      },
    }));
    const cols = ["Strategy", "CAGR", "Volatility", "Max drawdown", "Months to recover", "Worst 12m", "Final value (local)"];
    fillTable($("bt-table"), cols, res.map((r) => {
      const m = r.metrics;
      return [r.name, pct(m.cagr), pct(m.volatility_annual), pct(m.max_drawdown), String(m.months_to_recover ?? "not yet"), pct(m.worst_12m), r.local ? gbp(r.local.final_value_pence) : "hidden"];
    }));
    $("bt-out").scrollIntoView({ behavior: "smooth", block: "nearest" });
  } finally {
    btn.disabled = false;
    btn.classList.remove("busy");
  }
}));

bindExplain($("explain-bt"), "Explain this backtest", () => {
  if (!last) return null;
  const result = {};
  last.forEach((r) => {
    const m = r.metrics;
    result[r.name + " cagr pct"] = +(m.cagr * 100).toFixed(1);
    result[r.name + " max drawdown pct"] = +(m.max_drawdown * 100).toFixed(1);
    result[r.name + " volatility pct"] = +(m.volatility_annual * 100).toFixed(1);
  });
  return { kind: "backtest", result };
});
