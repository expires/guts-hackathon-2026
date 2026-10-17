// Bottom sheet: scrim + draggable surface anchored to the bottom.
// Drag is tracked 1:1 (grab offset respected), released with momentum projection,
// and the release velocity is handed to the spring. Enter and exit share one path.
import { $, el, svg } from "./util.js";
import { Spring, project, rubberband, reducedMotion } from "./spring.js";

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea, [tabindex]:not([tabindex="-1"])';

let current = null; // the open sheet, if any

export function openSheet({ title, body, onClose }) {
  if (current) current.close(true);

  const root = $("sheet-root");
  const sheet = $("sheet");
  const scrim = $("scrim");
  const bodyEl = $("sheet-body");
  const handle = $("sheet-handle");
  $("sheet-title").textContent = title;
  bodyEl.replaceChildren(body);
  bodyEl.scrollTop = 0;

  const opener = document.activeElement;
  const app = $("app");
  const reduce = reducedMotion();
  let height = 0;
  let closed = false;
  let dragging = false;

  // y = distance the sheet is pushed down (0 = fully open, height = fully hidden).
  const render = (y) => {
    const progress = height ? 1 - Math.min(Math.max(y, 0), height) / height : 1;
    scrim.style.opacity = String(progress);
    if (reduce && !dragging) {
      sheet.style.opacity = String(progress);
      sheet.style.transform = "";
    } else {
      sheet.style.transform = `translateY(${y}px)`;
    }
  };
  const spring = new Spring(0, { dampingRatio: 1, response: 0.35, precision: 0.05, onUpdate: render });

  function finish() {
    if (closed) return;
    closed = true;
    root.hidden = true;
    sheet.style.transform = sheet.style.opacity = scrim.style.opacity = "";
    app.removeAttribute("inert");
    document.removeEventListener("keydown", onKey, true);
    handle.removeEventListener("pointerdown", onDown);
    $("sheet-close").onclick = scrim.onclick = null;
    if (current === api) current = null;
    if (opener && opener.isConnected) opener.focus({ preventScroll: true });
    onClose?.();
  }

  function close(immediate = false) {
    if (closed) return;
    if (immediate) {
      spring.stop();
      finish();
      return;
    }
    height = sheet.offsetHeight; // content may have grown since opening
    spring.onRest = finish;
    spring.to(height, { dampingRatio: 1, response: 0.35 });
  }

  // ---- drag to dismiss ----
  let grabOffset = 0; // pointer Y minus the sheet's current translate, so the sheet never jumps
  let history = [];
  function onDown(e) {
    if (e.button > 0 || reduce || e.target.closest("button")) return;
    dragging = true;
    height = sheet.offsetHeight;
    spring.stop();
    spring.onRest = () => {};
    handle.setPointerCapture(e.pointerId);
    grabOffset = e.clientY - spring.value;
    history = [{ t: e.timeStamp, y: spring.value }];
    handle.addEventListener("pointermove", onMove);
    handle.addEventListener("pointerup", onUp);
    handle.addEventListener("pointercancel", onUp);
  }
  function onMove(e) {
    let y = e.clientY - grabOffset;
    if (y < 0) y = -rubberband(-y, window.innerHeight); // resist dragging above the top
    spring.x = y; // 1:1, bypassing the spring
    render(y);
    history.push({ t: e.timeStamp, y });
    while (history.length > 2 && e.timeStamp - history[0].t > 100) history.shift();
  }
  function onUp(e) {
    handle.removeEventListener("pointermove", onMove);
    handle.removeEventListener("pointerup", onUp);
    handle.removeEventListener("pointercancel", onUp);
    dragging = false;
    const a = history[0];
    const b = history[history.length - 1];
    const dt = (b.t - a.t) / 1000;
    const velocity = dt > 0.001 ? (b.y - a.y) / dt : 0; // px/s
    const y = spring.x;
    const dismiss = e.type !== "pointercancel" && y + project(velocity) > height / 2;
    if (dismiss) spring.onRest = finish;
    spring.to(dismiss ? height : 0, { velocity, dampingRatio: 0.8, response: 0.3 });
  }

  // ---- keyboard: Escape closes, Tab is trapped inside the sheet ----
  function onKey(e) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      close();
    } else if (e.key === "Tab") {
      const items = [...sheet.querySelectorAll(FOCUSABLE)].filter((n) => n.offsetParent !== null);
      if (!items.length) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (e.shiftKey && (document.activeElement === first || !sheet.contains(document.activeElement))) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    }
  }

  const api = {
    close,
    setBody(node) {
      bodyEl.replaceChildren(node);
    },
    setTitle(t) {
      $("sheet-title").textContent = t;
    },
  };
  current = api;

  // ---- present ----
  root.hidden = false;
  app.setAttribute("inert", "");
  height = sheet.offsetHeight;
  spring.set(height);
  spring.to(0);
  document.addEventListener("keydown", onKey, true);
  handle.addEventListener("pointerdown", onDown);
  $("sheet-close").onclick = scrim.onclick = () => close();
  (sheet.querySelector("input, select, textarea") || $("sheet-close")).focus({ preventScroll: true });
  return api;
}

// Static markup the sheet needs; created once.
export function buildSheetShell() {
  const root = el("div", { id: "sheet-root", className: "sheet-root", hidden: true },
    el("div", { id: "scrim", className: "scrim" }),
    el("div", { id: "sheet", className: "sheet", role: "dialog", "aria-modal": "true", "aria-labelledby": "sheet-title" },
      el("div", { id: "sheet-handle", className: "sheet-handle" },
        el("div", { className: "grabber" }),
        el("div", { className: "sheet-head" },
          el("h2", { id: "sheet-title" }),
          el("button", { id: "sheet-close", className: "icon-btn", type: "button", "aria-label": "Close" },
            svg('<path d="M6 6l12 12M18 6L6 18"/>')))),
      el("div", { id: "sheet-body", className: "sheet-body" })));
  document.body.append(root);
}
