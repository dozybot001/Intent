// A newer action owns its view. Late responses may finish, but cannot replace it.
function beginViewRequest(view) {
  state._requestVersions ||= {};
  if (view === "detail" || view === "sheet") setViewBusy(view, false);
  return state._requestVersions[view] = (state._requestVersions[view] || 0) + 1;
}

function ownsViewRequest(view, request) {
  return state._requestVersions?.[view] === request;
}

function setViewBusy(view, busy) {
  const target = view === "sheet" ? el.drawerContent : el.detailPane;
  target.setAttribute("aria-busy", String(busy));
}

function viewLoadingHtml() {
  return `<div class="view-loading" role="status"><span class="view-loading-spinner" aria-hidden="true"></span><p data-view-loading-copy>${esc(t("Loading…"))}</p></div>`;
}

function pageSkeletonHtml() {
  return `<div class="page-skeleton" role="status" aria-label="${esc(t("Loading continuation brief"))}"><i></i><i></i><i></i></div>`;
}

function localizeViewLoadingCopy() {
  for (const node of document.querySelectorAll("[data-view-loading-copy]")) node.textContent = t("Loading…");
}

class ApiRequestError extends Error {
  constructor(message, status, code, detail = "") {
    super(message);
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

// gate: false lets a caller read a 401 as an answer instead of showing the sign-in gate.
async function fetchJson(url, { gate = true, ...options } = {}) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  let r;
  let p;
  try {
    r = await fetch(url, { credentials: "same-origin", ...options, signal: controller.signal });
    p = await r.json();
  } catch (error) {
    throw new ApiRequestError(t("Could not load data. Try again."), r?.status || 0, error.name === "AbortError" ? "REQUEST_TIMEOUT" : "INVALID_RESPONSE");
  } finally {
    clearTimeout(timeout);
  }
  if (!r.ok || p.ok === false) {
    const error = new ApiRequestError(
      t(r.status === 401 ? "Sign in again to continue." : r.status === 403 ? "Permission denied." : r.status === 404 ? "Object no longer exists." : "Could not load data. Try again."),
      r.status,
      p?.error?.code,
      p?.error?.message || "",
    );
    error.details = p?.error?.details;
    if (r.status === 401 && gate && state.config?.authRequired) showAuthGate();
    throw error;
  }
  return p.result;
}

async function copyText(text, message) {
  try {
    await navigator.clipboard.writeText(text);
    setStatus(message);
    return true;
  } catch {
    setStatus(t("Copy failed. Select and copy the text manually."), true);
    return false;
  }
}
