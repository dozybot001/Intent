/* Account and Settings: who you are, and how you use IntHub. Each pane has its own URL. */

function accountNav(pane) {
  return [
    { label: t("Profile"), icon: "user", href: ACCOUNT_PATHS.profile, current: pane === "profile" },
    { label: t("Danger zone"), icon: "blocker", href: ACCOUNT_PATHS.danger, current: pane === "danger" },
  ];
}

function settingsNav(pane) {
  return [
    { label: t("Access tokens"), icon: "key", href: SETTINGS_PATHS.tokens, current: pane === "tokens" },
    { label: t("Teams"), icon: "users", href: SETTINGS_PATHS.teams, current: pane === "teams" },
    { label: t("Usage"), icon: "gauge", href: SETTINGS_PATHS.usage, current: pane === "usage" },
  ];
}

function dialogTitle() {
  return t(state._dialog === "account" ? "Account" : "Settings");
}

// The dialog keeps its size whichever pane shows, opens over the current page, and adds one history entry however
// many panes it passes through, so Back closes it. A dialog restored by a link or Back leaves its entry in place.
function openSettingsDialog(page, pane, { history = "auto" } = {}) {
  closeHeaderMenus();
  toggleProjectPicker(false);
  closeDrawer({ history: "none" });
  const wasOpen = Boolean(state._dialog);
  if (state._dialog !== page || state._pane !== pane) {
    forgetShownSecrets();
    state._dialog = page;
    state._pane = pane;
    state._tokenDraft = { name: "itt", days: DEFAULT_TOKEN_DAYS };
    state._teamDraft = { name: "", slug: "", edited: false };
    renderSettingsDialog();
    loadPane();
  }
  if (!el.settingsDialog.open) el.settingsDialog.showModal();
  revealNavItem(el.settingsDialogBody)?.focus?.({ preventScroll: true });
  updateDocumentTitle();
  const routed = writeRoute(history === "auto" ? (wasOpen ? "replace" : "push") : history, "dialog");
  if (!wasOpen) state._dialogPushed = routed === "pushed";
}

function closeSettingsDialog({ history = "auto" } = {}) {
  if (!state._dialog) return;
  closeSelect();
  const trigger = state._dialog === "settings" ? el.settingsLink : el.accountMenuTrigger;
  beginViewRequest("dialog");
  forgetShownSecrets();
  state._dialog = null;
  state._pane = "";
  state._tokens = null;
  state._tokensError = "";
  state._usage = null;
  if (el.settingsDialog.open) el.settingsDialog.close();
  el.settingsDialogBody.innerHTML = "";
  updateDocumentTitle();
  trigger.focus?.();
  if (history === "auto") {
    if (state._dialogPushed && window.history.state?.inthub === "dialog" && window.history.back) window.history.back();
    else writeRoute("replace");
  }
  state._dialogPushed = false;
}

async function loadPane() {
  if (state._pane === "tokens") await loadAccountTokens();
  else if (state._pane === "teams") await loadTeams();
  else if (state._pane === "usage") await loadUsage();
}

function renderSettingsDialog() {
  const pane = state._pane;
  const account = state._dialog === "account";
  if (!state._dialog) return;
  const title = dialogTitle();
  el.settingsDialogTitle.textContent = title;
  el.settingsDialogBody.innerHTML = settingsLayout({
    label: title,
    items: account ? accountNav(pane) : settingsNav(pane),
    pane: { profile: profilePane, danger: accountDangerPane, tokens: tokensPane, teams: teamsPane, usage: usagePane }[pane](),
  });
}

function profilePane() {
  const account = state.account || {};
  const name = account.display_name || account.login || "";
  return `
    ${settingsBlock("profile", t("Profile"), settingsList(settingsRow({
      before: monogram(name),
      title: esc(name),
      meta: metaParts([account.email || (account.login && account.login !== name ? `@${account.login}` : "")]),
      control: `<a class="settings-link" href="${TENON_ACCOUNT_URL}">${esc(t("Edit in Tenon"))}${icon("external")}</a>`,
    })))}
    ${settingsBlock("identity", t("Link your Snaps"), profileIdentityHtml(account))}`;
}

function accountDangerPane() {
  return settingsBlock("account-danger", t("Danger zone"), settingsList(settingsRow({
    title: esc(t("Delete account")),
    meta: esc(t("Removes the account with its personal projects and access tokens. Teams you administer pass to the next member; a team with nobody else is deleted with its projects. You confirm it in Tenon's account center.")),
    control: `<button id="delete-account-btn" class="button button-danger" type="button" data-delete-account>${iconLabel("trash", t("Delete account"))}</button>`,
  })));
}

// The link between Git and this account is the author email, as on GitHub.
function profileIdentityHtml(account) {
  if (!account.email) return `<p class="settings-lead">${esc(t("Sign in again to link Snaps to this account."))}</p>`;
  const email = /^[\w.+@-]+$/.test(account.email) ? account.email : shellArg(account.email);
  return `
    <p class="settings-lead">${tHtml("Snaps link to this account when their author email is {email}. Set Git to the same address:", { email: `<span class="profile-email">${esc(account.email)}</span>` })}</p>
    ${commandSnippet([`git config --global user.email ${email}`])}`;
}

function tokensPane() {
  return settingsBlock("tokens", t("Access tokens"), `${tokenFormHtml()}<div class="settings-slot" id="token-list" tabindex="-1">${tokenListHtml()}</div>`,
    esc(t("The Intent CLI signs in with an access token to push this account's projects. Revoke a token when a machine no longer needs it.")));
}

function tokenFormHtml() {
  const draft = state._tokenDraft || { name: "itt", days: DEFAULT_TOKEN_DAYS };
  const days = TOKEN_LIFETIMES.includes(Number(draft.days)) ? Number(draft.days) : DEFAULT_TOKEN_DAYS;
  return `
    <form class="settings-form token-form" data-token-form novalidate>
      <div class="settings-field token-name-field">
        <label class="field-label" for="token-name">${esc(t("Name"))}</label>
        <input class="text-field" id="token-name" name="token-name" type="text" value="${esc(draft.name ?? "itt")}" maxlength="100" autocomplete="off" autocapitalize="off" spellcheck="false" aria-describedby="token-form-error">
      </div>
      <div class="settings-field">
        <label class="field-label" for="token-lifetime">${esc(t("Expires in"))}</label>
        ${selectField({ id: "token-lifetime", name: "token-days", value: days, options: TOKEN_LIFETIMES.map((value) => ({ value, label: plural(value, "{count} day", "{count} days") })) })}
      </div>
      <button class="button button-primary" type="submit">${iconLabel("key", t("Generate token"))}</button>
      <p class="field-error" id="token-form-error" role="alert" hidden></p>
    </form>`;
}

// Active tokens only: revoked and expired ones no longer let the CLI in.
function activeTokens() {
  const now = Date.now();
  return (state._tokens || []).filter((token) => !token.revoked_at && !(token.expires_at && new Date(token.expires_at).getTime() <= now));
}

function tokenRowHtml(token) {
  const fresh = state._newToken?.id === token.id ? state._newToken : null;
  return settingsRow({
    title: esc(token.name || "CLI"),
    meta: metaParts([
      t("Created {date}", { date: calendarDate(token.created_at) }),
      token.last_used_at ? t("Last used {time}", { time: relativeDate(token.last_used_at) }) : t("Never used"),
      token.expires_at ? t("Expires {date}", { date: calendarDate(token.expires_at) }) : "",
    ]),
    control: `<button class="button button-danger button-small" type="button" data-revoke-token="${esc(token.id)}">${iconLabel("revoke", t("Revoke"))}</button>`,
  }) + (fresh ? secretBox(fresh.token, "data-copy-new-token", t("Copy it now; it won't be shown again.")) : "");
}

function tokenListHtml() {
  if (state._tokensError) {
    return `<div class="inline-empty settings-retry"><p>${esc(state._tokensError)}</p><button type="button" class="secondary-btn" data-retry-tokens>${iconLabel("refresh", t("Retry"))}</button></div>`;
  }
  if (!state._tokens) return viewLoadingHtml();
  const tokens = activeTokens();
  if (!tokens.length) return `<p class="inline-empty">${esc(t("No active tokens. Generate one for each machine or Agent that runs the Intent CLI."))}</p>`;
  return settingsList(tokens.map(tokenRowHtml).join(""));
}

function renderTokenList() {
  const list = el.settingsDialogBody.querySelector?.("#token-list");
  if (list) list.innerHTML = tokenListHtml();
  else renderSettingsDialog();
}

async function loadAccountTokens() {
  const request = beginViewRequest("dialog");
  state._tokensError = "";
  try {
    const result = await fetchJson(apiUrl("/api/v1/auth/tokens"));
    if (!ownsViewRequest("dialog", request) || state._dialog !== "settings") return;
    state._tokens = result.tokens || [];
  } catch (error) {
    if (!ownsViewRequest("dialog", request) || state._dialog !== "settings") return;
    state._tokensError = error.message;
  }
  renderTokenList();
}

async function generateAccessToken({ name, days }) {
  const label = String(name ?? "").trim();
  if (!label) throw new ApiRequestError(t("Enter a token name."), 0, "INVALID_INPUT");
  const lifetime = TOKEN_LIFETIMES.includes(Number(days)) ? Number(days) : DEFAULT_TOKEN_DAYS;
  const issued = await fetchJson(apiUrl("/api/v1/auth/tokens"), {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify({ name: label, ttl_seconds: lifetime * 86400 }),
  });
  if (state._dialog !== "settings") return issued;
  // The secret lives only here, for this visit to the pane; the list shows it once, under its row.
  state._newToken = { id: issued.id, token: issued.token };
  state._tokens = [
    { id: issued.id, name: issued.name, created_at: issued.created_at, expires_at: issued.expires_at, last_used_at: null, revoked_at: null },
    ...(state._tokens || []).filter((token) => token.id !== issued.id),
  ];
  renderTokenList();
  return issued;
}

async function submitTokenForm(form) {
  const button = form.querySelector("[type=submit]");
  if (!button || button.disabled) return;
  setFieldError(form, "");
  setButtonBusy(button, true, "Generating…", "Generate token");
  try {
    await generateAccessToken({ name: form.elements["token-name"].value, days: form.elements["token-days"].value });
    // The next token starts from the default name again; the lifetime choice stays.
    form.elements["token-name"].value = "itt";
    state._tokenDraft = { ...(state._tokenDraft || {}), name: "itt" };
    setStatus(t("Token created. Copy it now; it won't be shown again."));
    el.settingsDialogBody.querySelector("[data-copy-new-token]")?.focus();
  } catch (error) {
    setFieldError(form, error.code === "INVALID_INPUT" && error.detail ? error.detail : error.message);
  } finally {
    setButtonBusy(button, false, "Generating…", "Generate token");
  }
}

function confirmRevokeToken(id, trigger = null) {
  const token = (state._tokens || []).find((entry) => entry.id === id);
  if (!token) return;
  openConfirm({
    title: () => t("Revoke {name}?", { name: token.name || "CLI" }),
    body: () => t("Every CLI that uses this token stops being able to push at once. This cannot be undone."),
    action: "Revoke token",
    icon: "revoke",
    busy: "Revoking…",
    run: () => revokeAccessToken(id),
    returnFocus: trigger,
  });
}

async function revokeAccessToken(id) {
  try {
    await fetchJson(apiUrl(`/api/v1/auth/tokens/${encodeURIComponent(id)}/revoke`), { method: "POST", headers: JSON_HEADERS, body: "{}" });
  } catch (error) {
    // Already revoked (404) is the state we asked for.
    if (error.status !== 404) throw error;
  }
  state._tokens = (state._tokens || []).filter((token) => token.id !== id);
  if (state._newToken?.id === id) state._newToken = null;
  renderTokenList();
  setStatus(t("Token revoked."));
}

async function startAccountDeletion(button) {
  if (button.disabled) return;
  setButtonBusy(button, true, "Opening account management…", "Delete account");
  try {
    const result = await fetchJson(apiUrl("/api/auth/tenon/delete/start"), { method: "POST", headers: JSON_HEADERS, body: "{}" });
    window.location.assign(productDeletionDestination(result));
  } catch (error) {
    setStatus(error.message, true);
    setButtonBusy(button, false, "Opening account management…", "Delete account");
  }
}

function formatBytes(bytes) {
  const units = ["B", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit && value < 10 ? value.toFixed(1) : Math.round(value)} ${units[unit]}`;
}

function usageRow(owner) {
  return settingsRow({
    title: esc(owner.name || t("Personal")),
    meta: metaParts([
      t("{used} of {limit} projects", { used: owner.projects, limit: owner.projects_limit }),
      t("{used} of {limit} history storage", { used: formatBytes(owner.storage_bytes), limit: formatBytes(owner.storage_limit) }),
    ]),
  });
}

function usageListHtml() {
  if (state._usageError) return `<div class="inline-empty settings-retry"><p>${esc(state._usageError)}</p><button type="button" class="secondary-btn" data-retry-site>${iconLabel("refresh", t("Retry"))}</button></div>`;
  return state._usage ? settingsList(state._usage.map(usageRow).join("")) : viewLoadingHtml();
}

function usagePane() {
  return settingsBlock("usage", t("Usage"), `<div class="settings-slot" id="usage-list">${usageListHtml()}</div>`,
    esc(t("Your account and each team have their own allowance. Deleting a project frees its storage.")));
}

async function loadUsage() {
  const request = beginViewRequest("dialog");
  state._usageError = "";
  try {
    const result = await fetchJson(apiUrl("/api/v1/usage"));
    if (!ownsViewRequest("dialog", request)) return;
    state._usage = result.owners;
  } catch (error) {
    if (!ownsViewRequest("dialog", request)) return;
    state._usageError = error.message;
  }
  const list = el.settingsDialogBody.querySelector?.("#usage-list");
  if (list) list.innerHTML = usageListHtml();
  else renderSettingsDialog();
}
