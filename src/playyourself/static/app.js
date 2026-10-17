// Entry point: builds navigation, routes between sections and wires up the shell.
import { $, el, svg } from "./js/util.js";
import { guard, showError } from "./js/api.js";
import { Spring, reducedMotion } from "./js/spring.js";
import { Segmented } from "./js/nav.js";
import { buildSheetShell } from "./js/sheet.js";
import { toast } from "./js/toast.js";
import * as dashboard from "./js/views/dashboard.js";
import * as habits from "./js/views/habits.js";
import * as spending from "./js/views/spending.js";
import * as backtest from "./js/views/backtest.js";
import * as scenarios from "./js/views/scenarios.js";
import * as friends from "./js/views/friends.js";
import * as connections from "./js/views/connections.js";

const ICONS = {
  dashboard: '<rect x="3.5" y="3.5" width="7" height="7" rx="2"/><rect x="13.5" y="3.5" width="7" height="7" rx="2"/><rect x="3.5" y="13.5" width="7" height="7" rx="2"/><rect x="13.5" y="13.5" width="7" height="7" rx="2"/>',
  habits: '<circle cx="12" cy="12" r="8.5"/><path d="M8.5 12.3l2.4 2.4 4.6-5"/>',
  spending: '<rect x="3" y="5.5" width="18" height="13" rx="3"/><path d="M3 10h18M7 15h3"/>',
  backtest: '<path d="M3.5 6v12h17"/><path d="M7 14l3.5-4 3 2.5L19 7"/>',
  scenarios: '<path d="M4 12h5c3 0 3-6 6-6h5M9 12c3 0 3 6 6 6h5M9 12h11"/>',
  friends: '<circle cx="9" cy="8.5" r="3.2"/><path d="M3.5 19c.5-3.2 2.7-5 5.5-5s5 1.8 5.5 5"/><path d="M16 5.6a3 3 0 010 5.8M17.5 14.3c1.7.6 2.8 2.2 3 4.7"/>',
  connections: '<rect x="3" y="6" width="18" height="13" rx="3"/><path d="M3 10h18"/><circle cx="16.5" cy="14.5" r="1.2"/>',
};
const TABS = [
  { id: "dashboard", label: "Overview", view: dashboard },
  { id: "habits", label: "Habits", view: habits },
  { id: "spending", label: "Spending", view: spending },
  { id: "backtest", label: "Backtest", view: backtest },
  { id: "scenarios", label: "Scenarios", view: scenarios },
  { id: "friends", label: "Friends", view: friends },
  { id: "connections", label: "Accounts", view: connections },
];

function buildNav(host, withIcons) {
  host.replaceChildren(
    el("span", { className: "seg-indicator", "aria-hidden": "true" }),
    ...TABS.map((t) =>
      el("button", { className: "seg-btn", type: "button", role: "tab", id: (withIcons ? "bar-" : "seg-") + t.id, "aria-controls": "tab-" + t.id, "data-tab": t.id },
        withIcons ? svg(ICONS[t.id]) : null,
        el("span", { textContent: t.label }))
    )
  );
}
buildNav($("segmented"), false);
buildNav($("tabbar"), true);
buildSheetShell();

let current = null;
const panels = Object.fromEntries(TABS.map((t) => [t.id, $("tab-" + t.id)]));

// Slide the incoming panel from the side it lives on; cross-fade only under reduced motion.
function enter(panel, dir) {
  const reduce = reducedMotion();
  panel.hidden = false;
  panel._spring?.stop();
  const s = new Spring(1, {
    response: reduce ? 0.2 : 0.4,
    dampingRatio: 1,
    precision: 0.002,
    onUpdate: (p) => {
      panel.style.opacity = String(1 - Math.min(Math.max(p, 0), 1));
      panel.style.transform = reduce ? "" : `translate3d(${dir * 36 * p}px,0,0)`;
    },
    onRest: () => {
      panel.style.opacity = panel.style.transform = panel.style.willChange = "";
    },
  });
  panel._spring = s;
  panel.style.willChange = "transform, opacity";
  s.set(1);
  s.to(0);
}

function showTab(name) {
  if (name === current) return;
  const from = TABS.findIndex((t) => t.id === current);
  const to = TABS.findIndex((t) => t.id === name);
  if (current) {
    panels[current]._spring?.stop();
    panels[current].style.opacity = panels[current].style.transform = "";
    panels[current].hidden = true;
  }
  current = name;
  history.replaceState(null, "", `#${name}`);
  segmented.select(name);
  tabbar.select(name);
  window.scrollTo(0, 0);
  enter(panels[name], from < 0 ? 0 : Math.sign(to - from));
  guard(TABS[to].view.load)();
}
const segmented = new Segmented($("segmented"), showTab);
const tabbar = new Segmented($("tabbar"), showTab);

// Scroll-edge effect: the header gains a soft blurred fade only once content slides under it.
const header = document.querySelector(".app-header");
const onScroll = () => header.classList.toggle("scrolled", window.scrollY > 4);
addEventListener("scroll", onScroll, { passive: true });
onScroll();

$("error-close").addEventListener("click", () => showError(""));

// Deep links: /#<tab> opens that tab. Also handles the OAuth redirect
// (/#connections?monzo=connected|error&code=...).
function handleHash() {
  const [tab, query] = location.hash.slice(1).split("?");
  if (!TABS.some((t) => t.id === tab)) return false;
  showTab(tab);
  const q = new URLSearchParams(query || "");
  if (q.get("monzo") === "connected") toast("Monzo connected. Showing live data.");
  else if (q.get("monzo") === "error") toast(connections.plainError(q.get("code")), true);
  return true;
}
addEventListener("hashchange", handleHash);
if (!handleHash()) showTab("dashboard");
