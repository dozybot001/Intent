async function showTeam(slug, pane = "members", { history = "none" } = {}) {
  closeOverlays();
  const arriving = state.page !== "team" || state._team?.slug !== slug;
  if (arriving || state._team?.pane !== pane) forgetShownSecrets();
  if (arriving) {
    state._team = { slug, pane, data: null, error: "" };
    setPage("team");
  }
  state._team.pane = pane;
  writeRoute(history);
  renderTeamPage();
  settlePage(el.siteContent, arriving);
  if (arriving) await loadTeam();
}

async function loadTeam() {
  const team = state._team;
  if (!team) return;
  const request = beginViewRequest("site");
  team.error = "";
  try {
    const data = await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(team.slug)}`));
    if (!ownsViewRequest("site", request) || state._team !== team) return;
    team.data = data;
    team.edit = null;
  } catch (error) {
    if (!ownsViewRequest("site", request) || state._team !== team) return;
    team.error = error.status === 404 ? t("This team does not exist, or you are not in it.") : error.message;
  }
  // Settings is for admins; anyone else who lands there reads the members instead.
  if (team.pane === "settings" && team.data && team.data.role !== "admin") {
    team.pane = "members";
    writeRoute("replace");
  }
  renderTeamPage();
  updateDocumentTitle();
}

function teamNav(team) {
  const admin = team.data?.role === "admin";
  return [
    { label: t("Members"), icon: "users", href: teamPath(team.slug), current: team.pane === "members" },
    { label: t("Projects"), icon: "folder", href: teamPath(team.slug, "projects"), current: team.pane === "projects" },
    ...(admin ? [{ label: t("Settings"), icon: "settings", href: teamPath(team.slug, "settings"), current: team.pane === "settings" }] : []),
  ];
}

function renderTeamPage() {
  const team = state._team;
  if (state.page !== "team" || !team) return;
  if (team.error) {
    el.siteContent.innerHTML = `<div class="home-page">${pageHeader({ title: team.slug })}${sitePageError(team.error)}</div>`;
    return;
  }
  el.siteContent.innerHTML = settingsLayout({
    title: team.data?.team.name || team.slug,
    label: t("Team"),
    items: teamNav(team),
    pane: team.data ? { members: teamMembersPane, projects: teamProjectsPane, settings: teamSettingsPane }[team.pane](team.data) : viewLoadingHtml(),
  });
}

function roleOptions() {
  return TEAM_ROLES.map((role) => ({ value: role, label: roleLabel(role) }));
}

function memberRow(member, admin) {
  const name = `${esc(member.name)}${member.you ? ` <span class="chip">${esc(t("You"))}</span>` : ""}`;
  return settingsRow({
    before: monogram(member.name),
    title: name,
    meta: metaParts([member.email, t("Joined {date}", { date: calendarDate(member.joined_at) })]),
    control: admin
      ? `${selectField({ id: `member-role-${member.id}`, value: member.role, options: roleOptions(), label: t("Role of {name}", { name: member.name }), className: "role-select", attrs: ` data-member-role="${esc(member.id)}"` })}
         <button class="button button-danger button-small" type="button" data-remove-member="${esc(member.id)}">${iconLabel("userMinus", t("Remove"))}</button>`
      : `<span class="settings-role">${esc(roleLabel(member.role))}</span>`,
  });
}

function inviteRow(invite) {
  return settingsRow({
    title: esc(t("{role} invite", { role: roleLabel(invite.role) })),
    meta: metaParts([invite.invited_by ? t("Created by {name}", { name: invite.invited_by }) : "", t("Expires {date}", { date: calendarDate(invite.expires_at) })]),
    control: `<button class="button button-danger button-small" type="button" data-revoke-invite="${esc(invite.id)}">${iconLabel("revoke", t("Revoke"))}</button>`,
  });
}

function teamMembersPane(data) {
  const admin = data.role === "admin";
  const fresh = state._newInvite;
  return `
    ${settingsBlock("members", t("Members"), settingsList(data.members.map((member) => memberRow(member, admin)).join("")))}
    ${admin ? settingsBlock("invite", t("Invite people"), `
      <form class="settings-form invite-form" data-invite-form novalidate>
        <div class="settings-field">
          <label class="field-label" for="invite-role-select">${esc(t("Role"))}</label>
          ${selectField({ id: "invite-role-select", name: "invite-role", value: state._inviteRole || "member", options: roleOptions() })}
        </div>
        <button class="button button-primary" type="submit">${iconLabel("link", t("Create invite link"))}</button>
        <p class="field-error" role="alert" hidden></p>
      </form>
      ${fresh ? secretBox(fresh.url, "data-copy-invite", t("Copy it now; it won't be shown again.")) : ""}`,
      esc(t("A link works once and expires after 7 days. Anyone who opens it and signs in joins with the role you choose."))) : ""}
    ${admin && data.invites.length ? settingsBlock("pending-invites", t("Pending invites"), settingsList(data.invites.map(inviteRow).join(""))) : ""}
    <div class="settings-block">${settingsList(settingsRow({
      title: esc(t("Leave team")),
      meta: esc(t("You lose access to the team's projects until someone invites you again.")),
      control: `<button class="button button-danger" type="button" data-leave-team>${iconLabel("logout", t("Leave team"))}</button>`,
    }))}</div>`;
}

function teamProjectRow(project) {
  return `
    <a class="settings-row settings-row-link" href="${esc(projectPath(project.id))}" data-route>
      <div class="settings-row-copy">
        <strong>${esc(project.name)}</strong>
        <p class="settings-meta">${metaParts([project.last_synced_at ? t("Synced {time}", { time: relativeDate(project.last_synced_at) }) : t("Not synced")])}</p>
      </div>
      <div class="settings-row-control">${visibilityBadge(project.visibility)}${icon("chevron")}</div>
    </a>`;
}

function teamProjectsPane(data) {
  return settingsBlock("projects", t("Projects"), data.projects.length
    ? settingsList(data.projects.map(teamProjectRow).join(""))
    : `<p class="inline-empty">${esc(t("This team has no projects yet."))}</p>`);
}

function teamSettingsPane(data) {
  const edit = state._team.edit || { name: data.team.name, slug: data.team.slug };
  const count = data.projects.length;
  return `
    ${settingsBlock("team", t("General"), `
      <form class="settings-form team-form" data-team-settings-form novalidate>
        ${teamFields("edit-team", edit.name, edit.slug)}
        <button class="button button-secondary" type="submit">${iconLabel("check", t("Save"))}</button>
        <p class="field-error" id="edit-team-error" role="alert" hidden></p>
        <p class="field-note">${esc(t("Clones follow a new team URL on their next push or pull."))}</p>
      </form>`)}
    ${settingsBlock("team-danger", t("Danger zone"), settingsList(settingsRow({
      title: esc(t("Delete this team")),
      meta: esc(count ? plural(count, "Removes the team and its {count} project.", "Removes the team and its {count} projects.") : t("Removes the team. It has no projects.")),
      control: `<button class="button button-danger" type="button" data-delete-team>${iconLabel("trash", t("Delete team"))}</button>`,
    })))}`;
}

async function saveTeam(form) {
  const team = state._team;
  const button = form.querySelector("[type=submit]");
  const values = checkTeamForm(form);
  if (!team?.data || !button || button.disabled || !values) return;
  setButtonBusy(button, true, "Saving…", "Save");
  try {
    const result = await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(team.data.team.id)}`), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(values) });
    team.data = { ...team.data, team: result.team };
    team.slug = result.team.slug;
    team.edit = null;
    state._teams = null;
    writeRoute("replace");
    renderTeamPage();
    updateDocumentTitle();
    el.siteContent.querySelector?.("#edit-team-name")?.focus();
    setStatus(t("Team saved."));
    await refreshProjectList();
  } catch (error) {
    setFieldError(form, teamErrorMessage(error, values.slug), form.elements["team-slug"]);
    setButtonBusy(button, false, "Saving…", "Save");
  }
}

function confirmDeleteTeam(trigger = null) {
  const data = state._team?.data;
  if (!data) return;
  const count = data.projects.length;
  openConfirm({
    title: () => t("Delete {name}?", { name: data.team.name }),
    body: () => count
      ? plural(count, "This removes the team and its {count} project from this hub, with their history. Local .intent data is not touched. This cannot be undone.", "This removes the team and its {count} projects from this hub, with their history. Local .intent data is not touched. This cannot be undone.")
      : t("This removes the team from this hub. This cannot be undone."),
    label: () => tHtml("Type {name} to confirm.", { name: `<strong class="confirm-name">${esc(data.team.slug)}</strong>` }),
    expect: data.team.slug,
    action: "Delete team",
    icon: "trash",
    busy: "Deleting…",
    run: (typed) => deleteTeam(data.team, typed),
    returnFocus: trigger,
  });
}

async function leaveTeamPage(message) {
  state._teams = null;
  setStatus(message);
  await refreshProjectList();
  await openDefault();
}

async function deleteTeam(team, confirm) {
  await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(team.id)}/delete`), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ confirm }) });
  await leaveTeamPage(t("Deleted {name}.", { name: team.name }));
}

function confirmLeaveTeam(trigger = null) {
  const data = state._team?.data;
  const me = data?.members.find((member) => member.you);
  if (!me) return;
  openConfirm({
    title: () => t("Leave {name}?", { name: data.team.name }),
    body: () => t("You lose access to the team's projects until someone invites you again."),
    action: "Leave team",
    icon: "logout",
    busy: "Leaving…",
    run: async () => {
      await removeMember(data.team, me.id);
      await leaveTeamPage(t("You left {name}.", { name: data.team.name }));
    },
    message: serverMessage,
    returnFocus: trigger,
  });
}

function removeMember(team, memberId) {
  return fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(team.id)}/members/${encodeURIComponent(memberId)}/remove`), { method: "POST", headers: JSON_HEADERS, body: "{}" });
}

function confirmRemoveMember(memberId, trigger = null) {
  const data = state._team?.data;
  const member = data?.members.find((entry) => entry.id === memberId);
  if (!member) return;
  if (member.you) {
    confirmLeaveTeam(trigger);
    return;
  }
  openConfirm({
    title: () => t("Remove {name}?", { name: member.name }),
    body: () => t("{name} loses access to the team's projects.", { name: member.name }),
    action: "Remove member",
    icon: "userMinus",
    busy: "Removing…",
    run: async () => {
      await removeMember(data.team, member.id);
      await loadTeam();
      setStatus(t("Removed {name}.", { name: member.name }));
    },
    message: serverMessage,
    returnFocus: trigger,
  });
}

async function changeMemberRole(select) {
  const data = state._team?.data;
  const member = data?.members.find((entry) => entry.id === select.dataset.memberRole);
  if (!member || select.value === member.role) return;
  const role = select.value;
  const { trigger } = selectParts(select.closest("[data-select]"));
  trigger.disabled = true;
  try {
    await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(data.team.id)}/members/${encodeURIComponent(member.id)}/role`), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ role }) });
    member.role = role;
    setStatus(t("{name} is now {role}.", { name: member.name, role: roleLabel(role) }));
    // Losing the admin role takes the management controls away.
    if (member.you && role !== "admin") {
      await loadTeam();
      el.siteContent.focus?.({ preventScroll: true });
    }
  } catch (error) {
    setSelectValue(select, member.role);
    setStatus(serverMessage(error), true);
  } finally {
    trigger.disabled = false;
  }
}

async function createInvite(form) {
  const data = state._team?.data;
  const button = form.querySelector("[type=submit]");
  if (!data || !button || button.disabled) return;
  const role = form.elements["invite-role"].value;
  setFieldError(form, "");
  setButtonBusy(button, true, "Creating link…", "Create invite link");
  try {
    const result = await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(data.team.id)}/invites`), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ role }) });
    state._inviteRole = role;
    // The link exists only in this response; the hub keeps its hash.
    state._newInvite = { id: result.invite.id, url: `${window.location.origin}${result.path}` };
    data.invites = [{ ...result.invite, invited_by: state.account?.display_name || "" }, ...data.invites];
    renderTeamPage();
    setStatus(t("Invite link created. Copy it now; it won't be shown again."));
    el.siteContent.querySelector("[data-copy-invite]")?.focus();
  } catch (error) {
    setFieldError(form, serverMessage(error));
    setButtonBusy(button, false, "Creating link…", "Create invite link");
  }
}

async function revokeInvite(inviteId, button) {
  const data = state._team?.data;
  if (!data || button.disabled) return;
  button.disabled = true;
  try {
    await fetchJson(apiUrl(`/api/v1/teams/${encodeURIComponent(data.team.id)}/invites/${encodeURIComponent(inviteId)}/revoke`), { method: "POST", headers: JSON_HEADERS, body: "{}" });
    data.invites = data.invites.filter((invite) => invite.id !== inviteId);
    if (state._newInvite?.id === inviteId) state._newInvite = null;
    renderTeamPage();
    el.siteContent.focus?.({ preventScroll: true });
    setStatus(t("Invite revoked."));
  } catch (error) {
    button.disabled = false;
    setStatus(serverMessage(error), true);
  }
}
