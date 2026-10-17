import { api } from "../api.js";
import { draw, money, moneyTick } from "../charts.js";
import { $, el, gbp, fillTable, sentence, withLoading, label } from "../util.js";

function sourcePill(s) {
  const cls = s.ok ? "ok" : s.stale ? "warn" : "bad";
  let text = sentence(s.name) + " · " + (s.mode === "live" ? "Live" : "Demo");
  if (!s.ok) text += s.stale ? " · stale, showing last good data" : " · failed" + (s.error_code ? " (" + s.error_code + ")" : "");
  if (s.dropped) text += " · " + s.dropped + " bad records dropped";
  return el("span", { className: "pill " + cls + (s.mode === "live" ? " live" : ""), title: s.as_of ? "As of " + s.as_of : "" }, el("span", { className: "dot" }), text);
}

export async function load() {
  await withLoading($("tab-dashboard"), async () => {
    const env = await api("/dashboard");
    const d = env.data;

    const pills = Object.values(env.meta.sources).map(sourcePill);
    if (env.meta.stale) pills.unshift(el("span", { className: "pill warn" }, el("span", { className: "dot" }), "Warning: some data is stale"));
    $("sources").replaceChildren(...pills);

    $("hero-value").textContent = gbp(d.net_worth_pence);
    const spend = d.monthly_spend;
    const latest = spend[spend.length - 1];
    const avg = spend.length ? spend.reduce((a, m) => a + m.total_pence, 0) / spend.length : 0;
    const tiles = [
      ["Liquid cash", gbp(d.liquid_cash_pence), "Current accounts"],
      ["ISA value", gbp(d.isa_value_pence), "Invested"],
      ["Spent in " + (latest ? latest.month : "latest month"), latest ? gbp(latest.total_pence) : "n/a", "Month to date"],
      ["Average monthly spend", gbp(avg), "Last " + spend.length + " months"],
    ];
    $("kpis").replaceChildren(
      ...tiles.map(([l, v, s]) => el("div", { className: "card kpi" }, el("div", { className: "kpi-l", textContent: l }), el("div", { className: "kpi-v", textContent: v }), el("div", { className: "kpi-s", textContent: s })))
    );

    // Allocation doughnut with a centre label and an HTML legend.
    const keys = Object.keys(d.allocation_pct);
    const top = keys.reduce((a, k) => (d.allocation_pct[k] > d.allocation_pct[a] ? k : a), keys[0]);
    draw("c-alloc", $("c-alloc"), (t) => ({
      type: "doughnut",
      data: { labels: keys.map(sentence), datasets: [{ data: keys.map((k) => d.allocation_pct[k]), backgroundColor: t.series, borderColor: t.surface, borderWidth: 3, hoverOffset: 4 }] },
      options: {
        cutout: "70%",
        plugins: { legend: { display: false }, centre: { title: d.allocation_pct[top] + "%", sub: sentence(top) }, tooltip: { callbacks: { label: (c) => " " + c.label + ": " + c.parsed + "%" } } },
      },
    }));
    $("alloc-legend").replaceChildren(
      ...keys.map((k, i) =>
        el("li", {}, el("span", { className: "swatch", style: "background: var(--s" + (i + 1) + ")" }), el("span", { className: "grow", textContent: sentence(k) }), el("span", { className: "num strong", textContent: d.allocation_pct[k] + "%" }))
      )
    );

    const totals = {};
    spend.forEach((m) => Object.entries(m.by_category).forEach(([k, v]) => (totals[k] = (totals[k] || 0) + v)));
    const cats = Object.keys(totals).sort((a, b) => totals[b] - totals[a]);
    draw("c-spend", $("c-spend"), (t) => ({
      type: "bar",
      data: { labels: cats.map(sentence), datasets: [{ data: cats.map((c) => totals[c] / 100), backgroundColor: t.accent, borderRadius: 6, borderSkipped: false, barThickness: 16 }] },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => " " + money(c.parsed.x) } } },
        scales: { x: { grid: { color: t.grid }, ticks: { callback: moneyTick } }, y: { grid: { display: false }, ticks: { autoSkip: false } } },
      },
    }));

    fillTable(
      $("txs"),
      ["Date", "Merchant", "Category", "Amount"],
      d.recent_transactions.map((t) => [t.ts.slice(0, 10), t.merchant, label(t.category), { text: (t.amount_pence < 0 ? "-" : "+") + "£" + (Math.abs(t.amount_pence) / 100).toFixed(2), cls: t.amount_pence > 0 ? "pos" : "" }]),
      3
    );
  });
}
