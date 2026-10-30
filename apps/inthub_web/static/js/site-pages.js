// A secret the server returns once: a new access token, an invite link.
function secretBox(value, copyAttribute, note) {
  return `
    <div class="secret-box">
      <code class="secret-value">${esc(value)}</code>
      <button class="button button-secondary button-small" type="button" ${copyAttribute}>${iconLabel("copy", t("Copy"))}</button>
      <p class="secret-note">${esc(note)}</p>
    </div>`;
}

function setFieldError(form, message, field = form?.querySelector?.(".text-field")) {
  const error = form?.querySelector?.(".field-error");
  if (!error) return;
  error.textContent = message;
  error.hidden = !message;
  for (const input of form.querySelectorAll?.(".text-field") || []) input.removeAttribute("aria-invalid");
  if (message) field?.setAttribute("aria-invalid", "true");
}

function serverMessage(error) {
  return t(error.detail || error.message);
}

function sitePageError(message) {
  return `<div class="empty-state"><p>${esc(message)}</p><button type="button" class="secondary-btn" data-retry-site>${iconLabel("refresh", t("Retry"))}</button></div>`;
}

// Secrets stay for one visit to their pane; moving away drops them.
function forgetShownSecrets() {
  state._newToken = null;
  state._newInvite = null;
}

function setPage(page) {
  if (state.page !== page) forgetShownSecrets();
  const site = page !== "project";
  state.page = page;
  el.shell.classList.toggle("is-site", site);
  el.detailContent.classList.toggle("is-hidden", site);
  el.siteContent.classList.toggle("is-hidden", !site);
  el.skipLink?.setAttribute("href", site ? "#site-content" : "#detail-content");
  if (!site) {
    // Focus inside the page about to be emptied moves to the project view.
    if (el.siteContent.contains?.(document.activeElement)) el.detailContent.focus?.({ preventScroll: true });
    beginViewRequest("site");
    state._team = null;
    state._invite = null;
    state._device = null;
    // Teams change on these pages: the project's Settings tab asks again.
    state._teams = null;
    state._teamsError = "";
    state._projectTeam = null;
    el.siteContent.innerHTML = "";
  }
  renderProjectSelector();
}

function leaveSitePage() {
  if (state.page === "project") return;
  setPage("project");
  if (state.activeTab === "settings") renderProjectBody();
}

function closeOverlays() {
  closeHeaderMenus();
  toggleProjectPicker(false);
  closeDrawer({ history: "none" });
  closeSettingsDialog({ history: "none" });
}

// On a phone the nav is one scrolling row: bring the current item into it.
function revealNavItem(root) {
  const nav = root.querySelector?.(".settings-nav");
  const item = nav?.querySelector?.('[aria-current="page"]');
  if (item && nav.scrollWidth > nav.clientWidth) nav.scrollLeft = Math.max(0, item.offsetLeft - nav.offsetLeft - (nav.clientWidth - item.offsetWidth) / 2);
  return item;
}

// Keep the reader's place: focus a page on arrival, and the nav item when moving between panes.
function settlePage(root, arriving) {
  const item = revealNavItem(root);
  window.scrollTo?.({ top: 0 });
  // The first paint leaves focus where the browser put it.
  if (state._ready) (!arriving && item ? item : root).focus?.({ preventScroll: true });
}

function renderSitePage() {
  if (state._dialog) renderSettingsDialog();
  if (state.page === "home") renderHomePage();
  else if (state.page === "team") renderTeamPage();
  else if (state.page === "invite") renderInvitePage();
  else if (state.page === "device") renderDevicePage();
  updateDocumentTitle();
}

async function reloadSitePage() {
  if (state._dialog) await loadPane();
  else if (state.page === "home") await loadHome();
  else if (state.page === "team") await loadTeam();
  else if (state.page === "invite") await loadInvite();
}
