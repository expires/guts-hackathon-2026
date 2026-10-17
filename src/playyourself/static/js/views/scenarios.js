import { api, guard } from "../api.js";
import { draw, alpha } from "../charts.js";
import { $, el } from "../util.js";
import { PRESETS } from "./backtest.js";
import { bindExplain } from "./explain.js";

let loaded = false;
let last = null;

export async function load() {
  if (loaded) return;
  $("sc-strategy").replaceChildren(...PRESETS.map((p, i) => el("option", { value: String(i), textContent: p.name })));
  $("sc-strategy").value = "2";
  loaded = true;
}

$("sc-run").addEventListener("click", guard(async () => {
  const p = PRESETS[+$("sc-strategy").value];
  const btn = $("sc-run");
  btn.disabled = true;
  btn.classList.add("busy");
  try {
    const env = await api("/scenarios", { method: "POST", body: { strategy: { name: p.name, weights: p.weights } } });
    const s = env.data;
    last = { name: p.name, fan: s.fan, n: s.paths.length };
    $("sc-out").hidden = false;
    $("sc-label").textContent = s.label + " Based on " + s.paths.length + " similar past periods, 36 months ahead.";
    const x = s.fan.p50.map((_, i) => i);
    // Order matters: p10 (hidden line), p90 filled down to p10 (the band), then the median on top.
    draw("c-sc", $("c-sc"), (t) => ({
      type: "line",
      data: {
        labels: x,
        datasets: [
          { label: "p10", data: s.fan.p10, borderColor: alpha(t.accent, 0.35), borderWidth: 1, pointRadius: 0, tension: 0.35 },
          { label: "p90", data: s.fan.p90, borderColor: alpha(t.accent, 0.35), borderWidth: 1, pointRadius: 0, tension: 0.35, fill: "-1", backgroundColor: alpha(t.accent, 0.16) },
          { label: "p50 (median)", data: s.fan.p50, borderColor: t.accent, borderWidth: 2.75, pointRadius: 0, pointHoverRadius: 4, tension: 0.35 },
        ],
      },
      options: {
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: { itemSort: (a, b) => b.parsed.y - a.parsed.y, callbacks: { title: (i) => "Month " + i[0].label, label: (c) => " " + c.dataset.label + ": " + c.parsed.y.toFixed(1) } },
        },
        scales: { x: { ticks: { maxTicksLimit: 7 }, title: { display: true, text: "Months ahead", color: t.muted } }, y: { title: { display: true, text: "Index (start = 100)", color: t.muted } } },
      },
    }));
  } finally {
    btn.disabled = false;
    btn.classList.remove("busy");
  }
}));

bindExplain($("explain-sc"), "Explain these scenarios", () => {
  if (!last) return null;
  const f = last.fan, end = f.p50.length - 1;
  return { kind: "scenarios", result: { scenarios: [{ name: last.name, p10_final: +f.p10[end].toFixed(1), p50_final: +f.p50[end].toFixed(1), p90_final: +f.p90[end].toFixed(1), similar_periods: last.n }] } };
});
