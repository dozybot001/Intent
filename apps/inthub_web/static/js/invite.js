/* Invite: /invite?token=… */

async function showInvite(token, { history = "none" } = {}) {
  closeOverlays();
  setPage("invite");
  state._invite = { token, preview: null, error: "" };
  writeRoute(history);
  renderInvitePage();
  settlePage(el.siteContent, true);
  await loadInvite();
}

async function loadInvite() {
  const invite = state._invite;
  if (!invite) return;
  const request = beginViewRequest("site");
  invite.error = "";
  try {
    if (!invite.token) throw new ApiRequestError("", 410, "INVITE_INVALID");
    const preview = await fetchJson(apiUrl(`/api/v1/invites/preview?${new URLSearchParams({ token: invite.token })}`));
    if (!ownsViewRequest("site", request) || state._invite !== invite) return;
    invite.preview = preview;
  } catch (error) {
    if (!ownsViewRequest("site", request) || state._invite !== invite) return;
    invite.error = error.code === "INVITE_INVALID" ? t("This invite link is no longer valid.") : error.message;
    invite.invalid = error.code === "INVITE_INVALID";
  }
  renderInvitePage();
}

function renderInvitePage() {
  const invite = state._invite;
  if (state.page !== "invite" || !invite) return;
  const preview = invite.preview;
  const home = `<a class="button button-secondary" href="/" data-route>${iconLabel("close", t("Not now"))}</a>`;
  const card = invite.error
    ? `<h1>${esc(t("Team invite"))}</h1><p>${esc(invite.error)}</p>
       <div class="invite-actions">${invite.invalid ? `<a class="button button-secondary" href="/" data-route>${iconLabel("arrow", t("Go to IntHub"))}</a>` : `<button type="button" class="button button-secondary" data-retry-site>${iconLabel("refresh", t("Retry"))}</button>`}</div>`
    : !preview
      ? viewLoadingHtml()
      : preview.already_member
        ? `<h1>${esc(preview.team.name)}</h1><p>${esc(t("You are already in this team."))}</p>
           <div class="invite-actions"><a class="button button-primary" href="${esc(teamPath(preview.team.slug))}" data-route>${iconLabel("arrow", t("Open team"))}</a></div>`
        : `<h1>${esc(preview.team.name)}</h1>
           <p>${esc(preview.invited_by
             ? t("{name} invited you to join {team} as {role}.", { name: preview.invited_by, team: preview.team.name, role: roleLabel(preview.role) })
             : t("You are invited to join {team} as {role}.", { team: preview.team.name, role: roleLabel(preview.role) }))}</p>
           <div class="invite-actions">${home}<button class="button button-primary" type="button" data-accept-invite>${iconLabel("check", t("Accept"))}</button></div>
           <p class="field-error" role="alert" hidden></p>`;
  el.siteContent.innerHTML = `<div class="invite-page"><section class="invite-card">${card}</section></div>`;
}

async function acceptInvite(button) {
  const invite = state._invite;
  if (!invite || button.disabled) return;
  setButtonBusy(button, true, "Joining…", "Accept");
  try {
    const result = await fetchJson(apiUrl("/api/v1/invites/accept"), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ token: invite.token }) });
    // The token has done its job; it does not stay in the address bar or the history.
    window.history.replaceState({ inthub: "page" }, "", teamPath(result.team.slug));
    state._teams = null;
    await showTeam(result.team.slug, "members", { history: "none" });
    if (result.joined) setStatus(t("You joined {name}.", { name: result.team.name }));
    await refreshProjectList();
  } catch (error) {
    if (error.code === "INVITE_INVALID") {
      invite.preview = null;
      invite.invalid = true;
      invite.error = t("This invite link is no longer valid.");
      renderInvitePage();
      return;
    }
    setButtonBusy(button, false, "Joining…", "Accept");
    const message = el.siteContent.querySelector(".invite-card .field-error");
    if (message) { message.textContent = serverMessage(error); message.hidden = false; }
  }
}
