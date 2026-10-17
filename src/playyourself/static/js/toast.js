// Toasts: status, completion and error feedback. Spring in, spring out.
import { $, el } from "./util.js";
import { Spring, reducedMotion } from "./spring.js";

export function toast(msg, bad = false) {
  const host = $("toasts");
  const t = el("div", { className: "toast" + (bad ? " bad" : ""), role: bad ? "alert" : "status" }, el("span", { className: "dot" }), el("span", { textContent: msg }));
  host.append(t);
  const rm = reducedMotion();
  const p = new Spring(1, {
    response: 0.35,
    precision: 0.002,
    onUpdate: (v) => {
      t.style.opacity = String(1 - Math.min(Math.max(v, 0), 1));
      t.style.transform = rm ? "" : `translateY(${-14 * v}px)`;
    },
  });
  p.set(1);
  p.to(0);
  const leave = () => {
    clearTimeout(timer);
    p.onRest = () => t.remove();
    p.to(1, { response: 0.3 });
  };
  const timer = setTimeout(leave, bad ? 7000 : 4500);
  t.addEventListener("click", leave);
  while (host.children.length > 3) host.firstChild.remove();
}
