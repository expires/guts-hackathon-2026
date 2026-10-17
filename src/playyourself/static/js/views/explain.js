// "Explain" opens a sheet, asks /v1/explain, and shows the answer (or a plain error).
import { api } from "../api.js";
import { openSheet } from "../sheet.js";
import { toast } from "../toast.js";
import { el } from "../util.js";

export function bindExplain(button, title, build) {
  button.addEventListener("click", async () => {
    const payload = build();
    if (!payload) {
      toast("Nothing to explain yet. Load some results first.", true);
      return;
    }
    const sheet = openSheet({
      title,
      body: el("div", { className: "skeleton-lines", "aria-label": "Loading explanation", role: "status" }, el("i"), el("i"), el("i", { className: "short" })),
    });
    try {
      const env = await api("/explain", { method: "POST", body: payload });
      sheet.setBody(
        el("div", { className: "explain" },
          el("p", { className: "explain-text", textContent: env.data.text }),
          el("p", { className: "explain-src" }, el("span", { className: "pill", textContent: "Source: " + env.data.source })),
          el("p", { className: "muted small", textContent: "Modelled from your results. Not financial advice." }))
      );
    } catch (e) {
      sheet.setBody(el("p", { className: "form-error", role: "alert", textContent: e.message }));
      toast(e.message, true);
    }
  });
}
