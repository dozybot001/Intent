/* ---- Authentication ---- */

const LOGIN_LABELS = { github: "Continue with GitHub", apple: "Continue with Apple", email: "Continue with email" };
const LAST_LOGIN_METHOD = "inthub.last-method";

function setTenonLoginLoading(active = "") {
  for (const link of el.tenonLogin.querySelectorAll("[data-login-method]")) {
    const method = link.dataset.loginMethod, loading = method === active;
    link.classList.toggle("is-loading", loading);
    link.setAttribute("aria-busy", String(loading));
    if (active) link.setAttribute("aria-disabled", "true");
    else link.removeAttribute("aria-disabled");
    link.querySelector("[data-login-label]").textContent = t(loading ? "Opening sign-in…" : LOGIN_LABELS[method]);
  }
}

function showAuthGate(message = "", { keepPage = false } = {}) {
  closeHeaderMenus();
  closeDrawer({ history: "none" });
  if (el.searchDialog.open) el.searchDialog.close();
  if (el.confirmDialog.open) el.confirmDialog.close();
  closeSettingsDialog({ history: "none" });
  if (!keepPage) {
    if (state.page !== "project") setPage("project");
    for (const view of ["projects", "project", "detail", "sheet", "search"]) beginViewRequest(view);
    el.detailContent.innerHTML = "";
    el.searchResults.innerHTML = "";
    el.searchInput.value = "";
    el.accountLabel.textContent = "";
    state._searchResults = null;
    state._detailCache = new Map();
    state.visitor = false;
    el.signInButton.classList.add("is-hidden");
  }
  el.shell.inert = true;
  state._authMessage = window.IntHubI18n.keyFor(message);
  state.authenticated = false;
  el.shell.classList.add("is-locked");
  el.authGate.classList.remove("is-hidden");
  el.authDismiss.classList.toggle("is-hidden", !keepPage);
  // Someone reading a public project already knows what this is.
  el.authPitch.classList.toggle("is-hidden", keepPage);
  el.authStart.innerHTML = commandSnippet([INSTALL_COMMAND, "itt init"]);
  el.accountControl.classList.add("is-hidden");
  el.authError.textContent = message;
  el.authError.classList.toggle("is-hidden", !message);
  el.tenonLogin.classList.remove("is-hidden");
  const returnTo = `${window.location.pathname}${window.location.search}`;
  let lastMethod = null;
  try { lastMethod = window.localStorage.getItem(LAST_LOGIN_METHOD); } catch { /* The marker is only a convenience. */ }
  for (const link of el.tenonLogin.querySelectorAll("[data-login-method]")) {
    link.href = `/auth/redirect?method=${link.dataset.loginMethod}&return_to=${encodeURIComponent(returnTo)}`;
    link.querySelector(".last-used").classList.toggle("is-hidden", link.dataset.loginMethod !== lastMethod);
  }
  setTenonLoginLoading();
  window.setTimeout(() => el.tenonLogin.querySelector("[data-login-method]").focus(), 0);
}

function hideAuthGate() {
  el.shell.inert = false;
  state.authenticated = !state.visitor;
  el.shell.classList.remove("is-locked");
  el.authGate.classList.add("is-hidden");
  el.authDismiss.classList.add("is-hidden");
  el.accountControl.classList.toggle("is-hidden", !state.config?.authRequired || state.visitor);
  el.signInButton.classList.toggle("is-hidden", !state.visitor);
  el.logoutBtn.classList.remove("is-hidden");
  el.accountMenuTrigger.disabled = false;
  const account = state.account;
  // The name, then what tells two people with that name apart.
  el.accountLabel.textContent = account ? account.display_name || `@${account.login}` : "";
  el.accountMode.textContent = account ? account.email || (account.display_name && account.login ? `@${account.login}` : "") : "";
  el.authError.textContent = "";
  el.authError.classList.add("is-hidden");
}

// A visitor who opened the gate can go back to the project they were reading.
function dismissAuthGate() {
  hideAuthGate();
  el.signInButton.focus();
}

// Reading state.account === null afterwards means nobody is signed in: for a visitor that is not an error.
async function loadCurrentAccount() {
  if (!state.config?.authRequired) return;
  try {
    state.account = (await fetchJson(apiUrl("/api/v1/auth/me"), { gate: false })).account;
  } catch (error) {
    if (error.status !== 401) throw error;
    state.account = null;
  }
}

function callbackErrorMessage() {
  const params = new URLSearchParams(window.location.search);
  const code = params.get("auth_error");
  if (!code) return "";
  params.delete("auth_error");
  const query = params.toString();
  window.history.replaceState(
    {},
    "",
    `${window.location.pathname}${query ? `?${query}` : ""}`,
  );
  const messages = {
    tenon_denied: t("Tenon sign-in was cancelled."),
    invalid_state: t("That sign-in attempt expired. Please try again."),
    tenon_failed: t("Tenon sign-in could not be completed. Please try again."),
    suspended: t("This account is suspended. Contact support@tenonai.cn."),
  };
  return messages[code] || t("Sign-in could not be completed.");
}
