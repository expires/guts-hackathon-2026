// DOM + formatting helpers shared by all views.

export const $ = (id) => document.getElementById(id);

// el("div", { className: "x", "aria-label": "y" }, child, "text")
export function el(tag, props, ...kids) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === undefined || v === null) continue;
    if (k.startsWith("aria-") || k.startsWith("data-") || k === "role") e.setAttribute(k, v);
    else e[k] = v;
  }
  for (const k of kids.flat()) if (k !== null && k !== undefined && k !== false) e.append(k);
  return e;
}

const NS = "http://www.w3.org/2000/svg";
export function svg(markup, cls) {
  const t = document.createElementNS(NS, "svg");
  t.setAttribute("viewBox", "0 0 24 24");
  t.setAttribute("aria-hidden", "true");
  t.setAttribute("fill", "none");
  t.setAttribute("stroke", "currentColor");
  t.setAttribute("stroke-width", "1.8");
  t.setAttribute("stroke-linecap", "round");
  t.setAttribute("stroke-linejoin", "round");
  if (cls) t.setAttribute("class", cls);
  t.innerHTML = markup;
  return t;
}

export const gbp2 = (p) =>
  (p < 0 ? "-" : "") + "£" + (Math.abs(p) / 100).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const gbp = (p) => "£" + (p / 100).toLocaleString("en-GB", { maximumFractionDigits: 0 });
export const pct = (x) => (x * 100).toFixed(1) + "%";
export const label = (c) => String(c).replace(/_/g, " ");
export const sentence = (c) => {
  const s = label(c);
  return s.charAt(0).toUpperCase() + s.slice(1);
};

// Build a <table> body from rows; numeric columns from `numFrom` are right-aligned.
export function fillTable(table, cols, rows, numFrom = 1) {
  const head = el("tr", {}, ...cols.map((c, i) => el("th", { scope: "col", className: i >= numFrom ? "num" : "", textContent: c })));
  const body = rows.map((r) =>
    el("tr", {}, ...r.map((c, i) => {
      const cell = typeof c === "object" && c !== null ? c : { text: c };
      return el("td", { className: ((i >= numFrom ? "num " : "") + (cell.cls || "")).trim(), textContent: cell.text });
    }))
  );
  if (!body.length) body.push(el("tr", {}, el("td", { colSpan: cols.length, className: "empty", textContent: "Nothing to show for this period." })));
  table.replaceChildren(el("thead", {}, head), el("tbody", {}, ...body));
}

// Mark a panel as loading while fn runs: skeleton shimmer on first load, soft dim on refresh.
export async function withLoading(panel, fn) {
  const first = !panel.dataset.ready;
  const skeletons = [];
  if (first) {
    for (const card of panel.querySelectorAll(".card:not([hidden])")) {
      const sk = el("div", { className: "sk", "aria-hidden": "true" }, el("i"), el("i"));
      card.append(sk);
      skeletons.push(sk);
    }
  }
  panel.classList.add(first ? "is-loading" : "is-refreshing");
  panel.setAttribute("aria-busy", "true");
  try {
    await fn();
    panel.dataset.ready = "1";
  } finally {
    skeletons.forEach((s) => s.remove());
    panel.classList.remove("is-loading", "is-refreshing");
    panel.removeAttribute("aria-busy");
  }
}
