// Fetch wrapper for the /v1 envelope API plus the persistent error banner.
import { $ } from "./util.js";

export function showError(msg) {
  const b = $("error");
  b.querySelector(".banner-text").textContent = msg || "";
  b.hidden = !msg;
}

export async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: {} };
  if (opts.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }
  let res;
  try {
    res = await fetch("/v1" + path, init);
  } catch {
    throw new Error("Cannot reach the API. Is the server running?");
  }
  let env;
  try {
    env = await res.json();
  } catch {
    throw new Error("Unexpected response from the server (HTTP " + res.status + ")");
  }
  if (env.error) {
    const err = new Error(env.error.message + " [" + env.error.code + "]");
    err.code = env.error.code;
    throw err;
  }
  showError("");
  return env;
}

// Wrap a handler so failures surface in the banner instead of vanishing.
export function guard(fn) {
  return async (...a) => {
    try {
      await fn(...a);
    } catch (e) {
      showError(e.message);
    }
  };
}
