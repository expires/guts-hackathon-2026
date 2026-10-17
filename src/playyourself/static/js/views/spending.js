import { api, guard } from "../api.js";
import { draw, money, moneyTick } from "../charts.js";
import { $, el, fillTable, gbp2, label, pct, sentence, withLoading } from "../util.js";
import { bindExplain } from "./explain.js";

let last = null;

export async function load() {
  await withLoading($("tab-spending"), async () => {
    const env = await api("/spending?months=" + +$("sp-months").value);
    const d = env.data;
    last = d;
    $("sp-insights").replaceChildren(...(d.insights.length ? d.insights : ["Not enough data yet."]).map((t) => el("li", {}, el("span", { className: "bullet" }), el("span", { textContent: t }))));

    const tip = { callbacks: { label: (c) => " " + c.dataset.label + ": " + money(c.parsed.y) } };
    draw("c-sp-month", $("c-sp-month"), (t) => ({
      type: "bar",
      data: {
        labels: d.monthly.map((m) => m.month),
        datasets: [
          { label: "Income", data: d.monthly.map((m) => m.income_pence / 100), backgroundColor: t.series[1], borderRadius: 6, borderSkipped: false },
          { label: "Spend", data: d.monthly.map((m) => m.spend_pence / 100), backgroundColor: t.series[0], borderRadius: 6, borderSkipped: false },
        ],
      },
      options: { plugins: { tooltip: tip }, scales: { y: { ticks: { callback: moneyTick } } } },
    }));

    const m = d.category_by_month;
    draw("c-sp-stack", $("c-sp-stack"), (t) => ({
      type: "bar",
      data: {
        labels: m.months,
        datasets: m.categories.map((c, i) => ({ label: sentence(c), data: m.values[c].map((v) => v / 100), backgroundColor: t.series[i % t.series.length], borderRadius: 3, borderSkipped: false })),
      },
      options: {
        plugins: { legend: { position: "bottom" }, tooltip: tip },
        scales: { x: { stacked: true }, y: { stacked: true, ticks: { callback: moneyTick } } },
      },
    }));

    fillTable($("sp-cats"), ["Category", "Total", "Share", "Monthly avg", "vs previous"], d.by_category.map((c) => {
      const ch = c.change_vs_prev_period;
      const cell = ch === null ? { text: "n/a" } : { text: (ch > 0 ? "+" : "") + (ch * 100).toFixed(0) + "%", cls: ch > 0 ? "up" : ch < 0 ? "down" : "" };
      return [sentence(c.category), gbp2(c.total_pence), pct(c.share), gbp2(c.monthly_avg_pence), cell];
    }));
    fillTable($("sp-merch"), ["Merchant", "Total", "Count", "Category"], d.top_merchants.map((x) => [x.merchant, gbp2(x.total_pence), String(x.count), label(x.category)]), 1);

    const s = d.subscriptions;
    $("sp-subtotal").textContent = s.items.length ? gbp2(s.total_monthly_pence) + " per month, " + gbp2(s.annualised_pence) + " per year" : "No recurring monthly payments detected.";
    fillTable($("sp-subs"), ["Merchant", "Monthly", "First seen", "Months active"], s.items.map((i) => [i.merchant, gbp2(i.monthly_pence), i.first_seen, String(i.months_active)]));
    fillTable($("sp-unusual"), ["Date", "Merchant", "Category", "Amount", "Category median"], d.unusual.map((u) => [u.date, u.merchant, label(u.category), gbp2(u.amount_pence), gbp2(u.category_median_pence)]), 3);

    const p = d.patterns;
    $("sp-pattern").textContent =
      (p.weekend_share_of_discretionary === null
        ? "No discretionary spending. "
        : "Discretionary: " + pct(p.weekday_share_of_discretionary) + " weekdays, " + pct(p.weekend_share_of_discretionary) + " weekends. ") +
      "Average daily spend " + gbp2(p.average_daily_spend_pence) + ".";
    draw("c-sp-week", $("c-sp-week"), (t) => ({
      type: "bar",
      data: { labels: ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"], datasets: [{ data: p.spend_by_weekday_pence.map((v) => v / 100), backgroundColor: t.accent, borderRadius: 6, borderSkipped: false }] },
      options: { plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => " " + money(c.parsed.y) } } }, scales: { y: { ticks: { callback: moneyTick } } } },
    }));
  });
}

$("sp-months").addEventListener("change", guard(load));
bindExplain($("explain-sp"), "Explain your spending", () => {
  if (!last) return null;
  return {
    kind: "spending",
    result: {
      insights: last.insights.slice(0, 6),
      top_categories: last.by_category.slice(0, 3).map((c) => ({ category: c.category, share_pct: +(c.share * 100).toFixed(1) })),
    },
  };
});
