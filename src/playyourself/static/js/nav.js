// Segmented control / tab bar with a spring-driven sliding selection indicator.
// The indicator is two springs (x, width) so a click mid-flight re-targets from the live
// position and velocity instead of jumping.
import { Spring } from "./spring.js";

export class Segmented {
  constructor(root, onSelect) {
    this.root = root;
    this.onSelect = onSelect;
    this.buttons = [...root.querySelectorAll("[role=tab]")];
    this.indicator = root.querySelector(".seg-indicator");
    this.base = 1;
    this.selected = null;
    this.xs = new Spring(0, { response: 0.38, dampingRatio: 1, onUpdate: () => this.paint() });
    this.ws = new Spring(1, { response: 0.38, dampingRatio: 1, onUpdate: () => this.paint() });

    for (const b of this.buttons) {
      b.addEventListener("click", () => this.onSelect(b.dataset.tab));
      b.addEventListener("keydown", (e) => {
        const i = this.buttons.indexOf(b);
        const next = { ArrowRight: i + 1, ArrowLeft: i - 1, Home: 0, End: this.buttons.length - 1 }[e.key];
        if (next === undefined) return;
        e.preventDefault();
        const nb = this.buttons[(next + this.buttons.length) % this.buttons.length];
        nb.focus();
        this.onSelect(nb.dataset.tab);
      });
    }
    new ResizeObserver(() => this.layout(false)).observe(root);
  }

  paint() {
    this.indicator.style.transform = `translateX(${this.xs.value}px) scaleX(${this.ws.value / this.base})`;
  }

  select(id, animate = true) {
    this.selected = id;
    for (const b of this.buttons) {
      const on = b.dataset.tab === id;
      b.setAttribute("aria-selected", String(on));
      b.tabIndex = on ? 0 : -1;
    }
    this.layout(animate);
  }

  layout(animate) {
    const btn = this.buttons.find((b) => b.dataset.tab === this.selected);
    if (!btn || !btn.offsetWidth) return; // hidden at this breakpoint
    this.base = Math.max(...this.buttons.map((b) => b.offsetWidth));
    this.indicator.style.width = this.base + "px";
    this.indicator.style.opacity = "1";
    if (animate && this.moved) {
      this.xs.to(btn.offsetLeft);
      this.ws.to(btn.offsetWidth);
    } else {
      this.xs.set(btn.offsetLeft);
      this.ws.set(btn.offsetWidth);
      this.moved = true;
    }
  }
}
