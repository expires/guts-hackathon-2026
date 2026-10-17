import { api, guard } from "../api.js";
import { draw, destroyPrefix } from "../charts.js";
import { $, el, sentence, withLoading } from "../util.js";

function pie(entry, i) {
  const keys = Object.keys(entry.pie);
  const canvas = el("canvas", { "aria-label": "Allocation: " + keys.map((k) => k + " " + entry.pie[k] + "%").join(", "), role: "img" });
  draw("pie-" + i, canvas, (t) => ({
    type: "doughnut",
    data: { labels: keys.map(sentence), datasets: [{ data: keys.map((k) => entry.pie[k]), backgroundColor: t.series, borderColor: t.surface, borderWidth: 2 }] },
    options: { cutout: "62%", animation: false, events: [], plugins: { legend: { display: false }, tooltip: { enabled: false } } },
  }));
  return el("div", { className: "mini-pie" }, canvas);
}

export async function load() {
  await withLoading($("tab-friends"), async () => {
    const [lb, card] = await Promise.all([api("/friends/leaderboard"), api("/friends/me/card")]);
    destroyPrefix("pie-");
    $("lb").replaceChildren(
      ...lb.data.map((e, i) =>
        el("li", { className: "rank-row" + (e.is_me ? " me" : "") },
          el("span", { className: "rank-n", textContent: String(e.rank) }),
          el("div", { className: "rank-who" },
            el("span", { className: "rank-name", textContent: e.display_name + (e.is_me && !/^you$/i.test(e.display_name) ? " (you)" : "") }),
            el("span", { className: "muted small", textContent: "Score " + (e.overall_score ?? "n/a") + " · 80/20 index " + e.twr_index_final }),
            e.pie ? el("span", { className: "muted small", textContent: Object.keys(e.pie).map((k) => sentence(k) + " " + e.pie[k] + "%").join(" · ") }) : el("span", { className: "muted small", textContent: "Allocation private" })),
          e.pie ? pie(e, i) : null,
          el("div", { className: "rank-score" }, el("span", { className: "num", textContent: e.rebased_score ?? "n/a" }), el("span", { className: "muted small", textContent: "rebased" })))
      )
    );
    $("share-pie").checked = !!card.data.pie;
    $("card-json").textContent = JSON.stringify(card.data, null, 2);
  });
}

$("share-pie").addEventListener("change", guard(async (ev) => {
  const box = ev.target;
  box.disabled = true;
  try {
    await api("/friends/share", { method: "PUT", body: { share_pie: box.checked } });
    await load();
  } catch (e) {
    box.checked = !box.checked; // keep the switch truthful when the request failed
    throw e;
  } finally {
    box.disabled = false;
  }
}));
