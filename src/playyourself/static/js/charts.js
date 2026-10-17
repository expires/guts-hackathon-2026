// Chart.js theming from CSS tokens. Charts are registered as builders so they can be
// rebuilt when the colour scheme changes.
import { reducedMotion } from "./spring.js";

const registry = new Map(); // key -> { canvas, build, chart }

export function theme() {
  const cs = getComputedStyle(document.documentElement);
  const v = (n) => cs.getPropertyValue(n).trim();
  return {
    text: v("--text"),
    muted: v("--muted"),
    grid: v("--grid"),
    surface: v("--surface"),
    line: v("--line"),
    accent: v("--accent"),
    series: [1, 2, 3, 4, 5, 6, 7, 8].map((i) => v("--s" + i)),
    font: v("--font") || "system-ui, sans-serif",
  };
}

export function alpha(color, a) {
  return `color-mix(in srgb, ${color} ${Math.round(a * 100)}%, transparent)`;
}

// Common options: faint horizontal grid only, no axis lines, card-like tooltip.
export function baseOptions(t) {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: reducedMotion() ? false : { duration: 500, easing: "easeOutCubic" },
    font: { family: t.font },
    layout: { padding: { top: 4 } },
    plugins: {
      legend: { labels: { color: t.muted, usePointStyle: true, pointStyle: "circle", boxWidth: 8, boxHeight: 8, padding: 14, font: { family: t.font, size: 12 } } },
      tooltip: {
        backgroundColor: t.surface, titleColor: t.text, bodyColor: t.text, borderColor: t.line, borderWidth: 1,
        cornerRadius: 12, padding: 12, boxPadding: 5, usePointStyle: true,
        titleFont: { family: t.font, weight: "600" }, bodyFont: { family: t.font },
      },
    },
    scales: {
      x: { grid: { display: false }, border: { display: false }, ticks: { color: t.muted, maxRotation: 0, autoSkipPadding: 12, font: { family: t.font, size: 11 } } },
      y: { grid: { color: t.grid }, border: { display: false }, ticks: { color: t.muted, maxTicksLimit: 5, padding: 8, font: { family: t.font, size: 11 } } },
    },
  };
}

// Deep merge of plain objects (arrays and primitives are replaced).
export function merge(a, b) {
  const out = { ...a };
  for (const [k, v] of Object.entries(b || {})) {
    out[k] = v && typeof v === "object" && !Array.isArray(v) && a?.[k] && typeof a[k] === "object" ? merge(a[k], v) : v;
  }
  return out;
}

// Draws a doughnut centre label from options.plugins.centre = { title, sub }.
const centrePlugin = {
  id: "centre",
  afterDraw(chart, _args, opts) {
    if (!opts || !opts.title) return;
    const { ctx, chartArea: a } = chart;
    const t = theme();
    const cx = (a.left + a.right) / 2;
    const cy = (a.top + a.bottom) / 2;
    ctx.save();
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillStyle = t.text;
    ctx.font = `700 ${Math.round((a.right - a.left) * 0.15)}px ${t.font}`;
    ctx.fillText(opts.title, cx, cy - (opts.sub ? 9 : 0));
    if (opts.sub) {
      ctx.fillStyle = t.muted;
      ctx.font = `500 12px ${t.font}`;
      ctx.fillText(opts.sub, cx, cy + 14);
    }
    ctx.restore();
  },
};

// build(theme, baseOptions) returns a Chart.js config; options get merged over the base.
export function draw(key, canvas, build) {
  destroy(key);
  const entry = { canvas, build, chart: null };
  registry.set(key, entry);
  mount(entry);
}

function mount(entry) {
  const t = theme();
  const cfg = entry.build(t);
  const base = baseOptions(t);
  if (cfg.type === "doughnut" || cfg.type === "pie") delete base.scales;
  cfg.options = merge(base, cfg.options);
  cfg.plugins = [centrePlugin, ...(cfg.plugins || [])];
  entry.chart = new Chart(entry.canvas, cfg);
}

export function destroy(key) {
  const e = registry.get(key);
  if (e?.chart) e.chart.destroy();
  registry.delete(key);
}

export function destroyPrefix(prefix) {
  for (const k of [...registry.keys()]) if (k.startsWith(prefix)) destroy(k);
}

// Re-theme every live chart when the OS colour scheme flips.
matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
  requestAnimationFrame(() => {
    for (const e of registry.values()) {
      if (!e.canvas.isConnected) continue;
      e.chart.destroy();
      mount(e);
    }
  });
});

export const money = (v) => "£" + Number(v).toLocaleString("en-GB", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export const moneyTick = (v) => "£" + Number(v).toLocaleString("en-GB", { maximumFractionDigits: 0 });
