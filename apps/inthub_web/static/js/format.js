/* ---- Helpers ---- */

function productDeletionDestination(result) {
  let target;
  try {
    target = new URL(result?.url || "");
  } catch {
    throw new Error(t("Tenon returned an invalid deletion destination."));
  }
  if (target.origin !== "https://account.tenon.asia" || target.pathname !== "/account/delete/"
      || target.username || target.password || target.hash
      || [...target.searchParams].length !== 1 || !/^[A-Za-z0-9_-]{43}$/.test(target.searchParams.get("request") || "")
      || !Number.isFinite(result?.expiresAt) || result.expiresAt <= Date.now()) {
    throw new Error(t("Tenon returned an invalid deletion destination."));
  }
  return target.href;
}

function esc(v) {
  return String(v ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

function fmtDate(v) {
  if (!v) return "—";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  const pad = (part) => String(part).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function relativeDate(v) {
  if (!v) return t("Never synced");
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return String(v);
  // Clock skew can put fresh server times slightly in the future.
  const seconds = Math.min(0, Math.round((d.getTime() - Date.now()) / 1000));
  const abs = Math.abs(seconds);
  const formatter = new Intl.RelativeTimeFormat(window.IntHubI18n.language, { numeric: "auto" });
  if (abs < 60) return t("just now");
  if (abs < 3600) return formatter.format(Math.round(seconds / 60), "minute");
  if (abs < 86400) return formatter.format(Math.round(seconds / 3600), "hour");
  if (abs < 2592000) return formatter.format(Math.round(seconds / 86400), "day");
  return fmtDate(v);
}

function shortDay(v) {
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return "—";
  const today = new Date();
  if (d.toDateString() === today.toDateString()) {
    return new Intl.DateTimeFormat(window.IntHubI18n.language, { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(d);
  }
  // Earlier years use the compact numeric form so the date column never overflows.
  return new Intl.DateTimeFormat(window.IntHubI18n.language, d.getFullYear() === today.getFullYear()
    ? { month: "short", day: "numeric" }
    : { year: "2-digit", month: "numeric", day: "numeric" }).format(d);
}

function plural(count, one, other, values = {}) {
  return t(count === 1 ? one : other, { count, ...values });
}

function shortRevision(v) {
  return v ? v.slice(0, 8) : "—";
}

function truncate(v, n = 140) {
  if (!v || v.length <= n) return v || "";
  return v.slice(0, n).trimEnd() + "…";
}

function formatText(v) {
  if (!v) return "";
  return String(v)
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => `<p>${esc(line)}</p>`)
    .join("");
}

function highlight(text, query) {
  const source = String(text ?? "");
  const needle = String(query || "").trim().toLowerCase();
  const lower = source.toLowerCase();
  if (!needle || lower.length !== source.length) return esc(source);
  let out = "";
  let index = 0;
  for (let hit = lower.indexOf(needle); hit >= 0; hit = lower.indexOf(needle, index)) {
    out += `${esc(source.slice(index, hit))}<mark>${esc(source.slice(hit, hit + needle.length))}</mark>`;
    index = hit + needle.length;
  }
  return out + esc(source.slice(index));
}

function intentStatusLabel(status) {
  return {
    active: t("In progress"),
    suspend: t("On hold"),
    done: t("Completed"),
    cancelled: t("Cancelled"),
    deprecated: t("Deprecated"),
  }[status] || status || t("Unknown");
}

function decisionStatusLabel(status) {
  return { active: t("In effect"), deprecated: t("Deprecated") }[status] || status || t("Unknown");
}

function statusBadge(status, kind = "intent") {
  const label = kind === "decision" ? decisionStatusLabel(status) : intentStatusLabel(status);
  return `<span class="status-pill status-${esc(status || "unknown")}"><span class="status-dot" aria-hidden="true"></span>${esc(label)}</span>`;
}

function stateBadge(status) {
  return `<span class="status-pill state-${esc(status.key)}"><span class="status-dot" aria-hidden="true"></span>${esc(status.label)}</span>`;
}

function rowStatusIcon(status) {
  return `<span class="row-icon status-${esc(status || "unknown")}" aria-hidden="true"><span class="status-dot"></span></span>`;
}

function originName(origin) {
  return ORIGIN_NAMES[origin] || origin || "";
}

function authorName(object) {
  return object?.author?.name || object?.author?.email || "";
}

// "Ana Lee · Claude Code": who recorded it and with which agent. Without an author, only the agent.
function byline(object) {
  return [authorName(object), originName(object?.origin)].filter(Boolean).join(" · ");
}

function verifiedBadge(object) {
  if (!object?.verified) return "";
  return `<span class="status-pill status-verified" data-tip="${esc(t("Pushed by the account that owns this email."))}"><span class="status-dot" aria-hidden="true"></span>${esc(t("Verified"))}</span>`;
}

// One quiet line in a list row or timeline entry; nothing when the object names nobody.
function rowByline(object) {
  const line = byline(object);
  const badge = verifiedBadge(object);
  return line || badge ? `<span class="row-byline">${line ? `<span>${esc(line)}</span>` : ""}${badge}</span>` : "";
}

// Sheets name the author in full, and can explain "Verified".
function identityMeta(object) {
  const line = byline(object);
  const email = object?.author?.name ? object.author.email : "";
  return [
    line ? `<span class="chip">${esc(line)}</span>` : "",
    email ? `<span class="detail-email">${esc(email)}</span>` : "",
    object?.verified ? `<span class="detail-verified">${verifiedBadge(object)}${helpButton("verified")}</span>` : "",
  ].join("");
}

function idChip(id) {
  return `<span class="chip chip-id">${esc(id)}</span>`;
}

function remoteId(wksId, objId) {
  return `${wksId}__${objId}`;
}

function projectIdFromRemoteId(rId) {
  return String(rId || "").split("__", 1)[0] || "";
}

// Requests stay same-origin (CSP connect-src 'self'); apiBaseUrl is only for CLI snippets.
function apiUrl(path) {
  return path;
}

function configUrl() {
  return "/config.json";
}
