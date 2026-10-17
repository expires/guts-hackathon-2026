import { api } from "../api.js";
import { Spring, reducedMotion } from "../spring.js";
import { $, el, sentence, withLoading } from "../util.js";
import { bindExplain } from "./explain.js";

let last = null;
const R = 52;
const C = 2 * Math.PI * R;

// Animate 0 -> 1 with a critically damped spring and hand each frame to `apply`.
function reveal(apply) {
  if (reducedMotion()) return apply(1);
  apply(0);
  new Spring(0, { response: 0.6, precision: 0.001, onUpdate: apply }).to(1);
}

function ring(score) {
  const ns = "http://www.w3.org/2000/svg";
  const s = document.createElementNS(ns, "svg");
  s.setAttribute("viewBox", "0 0 128 128");
  s.setAttribute("class", "ring");
  s.setAttribute("role", "img");
  s.setAttribute("aria-label", score === null ? "Overall score not available" : "Overall habit score " + score + " out of 100");
  s.innerHTML =
    `<circle class="ring-track" cx="64" cy="64" r="${R}" fill="none" stroke-width="12"/>` +
    `<circle class="ring-fill" cx="64" cy="64" r="${R}" fill="none" stroke-width="12" stroke-linecap="round" transform="rotate(-90 64 64)" stroke-dasharray="${C}" stroke-dashoffset="${C}"/>` +
    `<text x="64" y="66" class="ring-num" text-anchor="middle" dominant-baseline="middle">${score === null ? "n/a" : score}</text>` +
    `<text x="64" y="90" class="ring-sub" text-anchor="middle">out of 100</text>`;
  const fill = s.querySelector(".ring-fill");
  reveal((p) => fill.setAttribute("stroke-dashoffset", String(C * (1 - ((score ?? 0) / 100) * p))));
  return s;
}

export async function load() {
  await withLoading($("tab-habits"), async () => {
    const env = await api("/habit-vector");
    const hv = env.data;
    last = hv;
    $("ring-host").replaceChildren(ring(hv.overall_score));
    const rows = Object.entries(hv.factors).map(([name, f]) => {
      const fill = el("div", { className: "fill" });
      reveal((p) => (fill.style.transform = `scaleX(${((f.score ?? 0) / 100) * p})`));
      return el("li", { className: "factor" },
        el("div", { className: "factor-head" }, el("span", { className: "factor-name", textContent: sentence(name) }), el("span", { className: "num strong", textContent: f.score === null ? "n/a" : f.score + " / 100" })),
        el("div", { className: "track", role: "meter", "aria-valuemin": "0", "aria-valuemax": "100", "aria-valuenow": String(f.score ?? 0), "aria-label": sentence(name) }, fill),
        f.reason ? el("p", { className: "muted small", textContent: f.reason }) : null);
    });
    $("factor-bars").replaceChildren(...rows);
  });
}

bindExplain($("explain-habits"), "Explain your habit score", () => {
  if (!last) return null;
  const scores = {};
  Object.entries(last.factors).forEach(([k, f]) => {
    if (f.score !== null) scores[k] = f.score;
  });
  return { kind: "habit_vector", result: { scores, overall_score: last.overall_score } };
});
