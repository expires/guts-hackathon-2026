import { api } from "../api.js";
import { openSheet } from "../sheet.js";
import { toast } from "../toast.js";
import { $, el, withLoading } from "../util.js";

const ERROR_TEXT = {
  auth: "Key rejected",
  rate_limited: "Rate limited by provider, try again shortly",
  timeout: "The provider did not respond in time",
  unavailable: "The provider is unavailable right now",
  bad_data: "The provider sent an unexpected response",
  not_configured: "Monzo sign-in is not configured on this server (MONZO_CLIENT_ID is missing)",
  invalid_state: "Sign-in expired or was not started here, please try again",
  denied: "Sign-in was cancelled",
};
export const plainError = (code) => ERROR_TEXT[String(code || "").replace(/^source_/, "")] || "Something went wrong (" + code + ")";
const nice = (name) => (name === "trading212" ? "Trading212" : "Monzo");

export function renderConnection(name, c) {
  const badge = $("mode-" + name);
  badge.replaceChildren(el("span", { className: "dot" }), c.mode === "live" ? "Live" : "Demo data");
  badge.className = "pill " + (c.mode === "live" ? "ok live" : "");
  let t = c.mode === "live" ? "Showing live data" : "Showing demo data";
  if (c.connected) t += ". Credentials " + c.hint + (c.remembered ? " (remembered on this device)" : " (this session only)");
  if (c.health && !c.health.ok) t += ". Last check failed" + (c.health.error_code ? ": " + plainError(c.health.error_code) : "");
  $("state-" + name).textContent = t + ".";
  if (name === "monzo") renderHistory(c);
  $("disc-" + name).hidden = !c.connected;
  if (name === "monzo") {
    const a = $("monzo-oauth");
    a.setAttribute("aria-disabled", String(!c.oauth_available));
    a.title = c.oauth_available ? "" : "Set MONZO_CLIENT_ID (and MONZO_CLIENT_SECRET) on the server to enable this";
    a.href = c.oauth_available ? "/v1/connect/monzo/start?remember=" + $("monzo-remember").checked : "#connections";
    $("monzo-oauth-note").hidden = c.oauth_available;
  }
}

function renderHistory(c) {
  const host = $("state-monzo");
  let note = document.getElementById("history-monzo");
  if (!note) {
    note = el("p", { id: "history-monzo", className: "muted small" });
    host.after(note);
  }
  const h = c.history;
  note.hidden = !c.connected || !h;
  if (note.hidden) return;
  note.className = h.synced ? "muted small" : "form-error";
  if (h.synced) {
    stopRetry();
    note.textContent = "History imported from " + h.oldest + " (" + h.count + " transactions).";
    return;
  }
  // "auth" almost always means access isn't approved in the Monzo app yet (Monzo returns 403
  // for data until then), not the 90-day rule. Retry quietly while they approve.
  if (h.last_error === "auth") {
    note.replaceChildren(
      "Approve the request in your Monzo app. Your history will import automatically once you do. ",
      el("button", { type: "button", className: "link", textContent: "Import now", onclick: () => syncHistory(true) }),
    );
    startRetry();
  } else {
    note.textContent =
      "Couldn't import full history. Monzo only shares the last 90 days after the first 5 minutes — disconnect and reconnect to try again.";
  }
}

// Retry the import every 5s for up to 5 minutes (Monzo's full-history window after sign-in).
const RETRY_MS = 5000;
const RETRY_FOR_MS = 5 * 60 * 1000;
let retryTimer = null;
let retryUntil = 0;

function startRetry() {
  if (retryTimer) return;
  retryUntil = Date.now() + RETRY_FOR_MS;
  retryTimer = setInterval(() => (Date.now() > retryUntil ? stopRetry() : syncHistory(false)), RETRY_MS);
}

function stopRetry() {
  clearInterval(retryTimer);
  retryTimer = null;
}

async function syncHistory(manual) {
  try {
    const env = await api("/connect/monzo/sync", { method: "POST", body: {} });
    renderConnection("monzo", env.data);
    if (env.data.history?.synced) toast("Monzo history imported.");
    else if (manual) toast("Monzo still refused access. Check the approval in your Monzo app.", true);
  } catch (e) {
    if (manual) toast(plainError(e.code), true);
  }
}

export async function load() {
  await withLoading($("tab-connections"), async () => {
    const env = await api("/connect/status");
    for (const [name, c] of Object.entries(env.data.sources)) renderConnection(name, c);
  });
}

// ---- form pieces with inline validation ----
function field({ id, text, required, hint }) {
  const input = el("input", { id, type: "password", autocomplete: "off", spellcheck: false, required: false });
  const err = el("p", { className: "field-error", id: id + "-err", hidden: true });
  input.setAttribute("aria-describedby", id + "-err");
  const validate = () => {
    const bad = required && !input.value.trim();
    err.hidden = !bad;
    err.textContent = bad ? "Enter your " + text.toLowerCase().replace(/ \(optional\)$/, "") + " to continue." : "";
    input.setAttribute("aria-invalid", String(bad));
    return !bad;
  };
  input.addEventListener("blur", () => {
    if (input.value || input.dataset.touched) validate();
  });
  input.addEventListener("input", () => {
    input.dataset.touched = "1";
    if (input.getAttribute("aria-invalid") === "true") validate();
  });
  return { input, validate, node: el("div", { className: "field" }, el("label", { htmlFor: id, textContent: text }), input, hint ? el("p", { className: "muted small", textContent: hint }) : null, err) };
}

function switchRow(id, text, checked) {
  const input = el("input", { id, type: "checkbox", className: "switch", role: "switch", checked });
  return { input, node: el("label", { className: "switch-row", htmlFor: id }, el("span", { textContent: text }), input) };
}

function openConnectForm({ name, title, fields, remember, path, buildBody, intro }) {
  const submit = el("button", { className: "btn block", type: "submit", textContent: "Connect" });
  const formError = el("p", { className: "form-error", role: "alert", hidden: true });
  const form = el("form", { autocomplete: "off", noValidate: true, className: "stack-form" },
    intro ? el("p", { className: "muted", textContent: intro }) : null,
    ...fields.map((f) => f.node),
    remember.node,
    el("p", { className: "muted small", textContent: "Remembered credentials are stored in a local file readable only by your user." }),
    formError,
    submit);
  const sheet = openSheet({ title, body: form });
  form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    formError.hidden = true;
    const results = fields.map((f) => f.validate());
    if (results.includes(false)) {
      fields[results.indexOf(false)].input.focus();
      return;
    }
    submit.disabled = true;
    submit.classList.add("busy");
    submit.textContent = name === "monzo" ? "Importing your transaction history…" : "Connecting";
    try {
      const env = await api(path, { method: "POST", body: buildBody() });
      sheet.close();
      renderConnection(name, env.data);
      toast("Connected. Showing live data for " + nice(name) + ".");
    } catch (e) {
      const msg = e.code ? plainError(e.code) : e.message;
      formError.textContent = msg;
      formError.hidden = false;
      toast(msg, true);
    } finally {
      submit.disabled = false;
      submit.classList.remove("busy");
      submit.textContent = "Connect";
    }
  });
}

$("monzo-paste").addEventListener("click", () => {
  const token = field({ id: "monzo-token", text: "Access token", required: true });
  const remember = switchRow("monzo-remember-form", "Remember on this device", $("monzo-remember").checked);
  remember.input.addEventListener("change", () => ($("monzo-remember").checked = remember.input.checked));
  openConnectForm({
    name: "monzo", title: "Connect Monzo", fields: [token], remember, path: "/connect/monzo/token",
    intro: "Paste a token from the Monzo developer playground. It is only used to read your data.",
    buildBody: () => ({ access_token: token.input.value, remember: remember.input.checked }),
  });
});

$("t212-open").addEventListener("click", () => {
  const key = field({ id: "t212-key", text: "API key", required: true });
  const secret = field({ id: "t212-secret", text: "API secret", required: true });
  const remember = switchRow("t212-remember", "Remember on this device", true);
  openConnectForm({
    name: "trading212", title: "Connect Trading212", fields: [key, secret], remember, path: "/connect/trading212",
    intro: "Generate an API key in the Trading212 app (it comes as a key and a secret) and paste both here. Works for Invest and Stocks ISA accounts.",
    buildBody: () => {
      return { api_key: key.input.value, api_secret: secret.input.value, remember: remember.input.checked };
    },
  });
});

for (const name of ["monzo", "trading212"]) {
  $("disc-" + name).addEventListener("click", async () => {
    try {
      const env = await api("/connect/" + name, { method: "DELETE" });
      renderConnection(name, env.data);
      toast("Disconnected. " + nice(name) + " is back to demo data.");
    } catch (e) {
      toast(e.code ? plainError(e.code) : e.message, true);
    }
  });
}
$("monzo-oauth").addEventListener("click", (ev) => {
  if ($("monzo-oauth").getAttribute("aria-disabled") === "true") {
    ev.preventDefault();
    toast(plainError("not_configured"), true);
  }
});
$("monzo-remember").addEventListener("change", () => {
  const a = $("monzo-oauth");
  if (a.getAttribute("aria-disabled") !== "true") a.href = "/v1/connect/monzo/start?remember=" + $("monzo-remember").checked;
});

