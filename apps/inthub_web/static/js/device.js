/* Device: approving `itt auth login`. The code is typed, never carried in a link, so nobody can send one to approve. */

function showDevice() {
  closeOverlays();
  setPage("device");
  state._device = { step: "code", code: "", name: "", days: 0 };
  writeRoute("none");
  renderDevicePage();
  settlePage(el.siteContent, true);
  el.siteContent.querySelector?.("#device-code")?.focus();
}

function renderDevicePage() {
  const device = state._device;
  if (state.page !== "device" || !device) return;
  const home = `<a class="button button-secondary" href="/" data-route>${iconLabel("arrow", t("Go to IntHub"))}</a>`;
  const card = {
    code: () => `
      <h1>${esc(t("Connect a device"))}</h1>
      <p>${esc(t("Enter the code shown in your terminal."))}</p>
      <form class="device-form" data-device-form novalidate>
        <input class="text-field device-code" id="device-code" name="device-code" type="text" value="${esc(device.code)}" maxlength="9" placeholder="XXXX-XXXX" autocomplete="off" autocapitalize="characters" spellcheck="false" aria-label="${esc(t("Device code"))}" aria-describedby="device-error">
        <p class="field-error" id="device-error" role="alert" hidden></p>
        <button class="button button-primary" type="submit">${iconLabel("arrow", t("Continue"))}</button>
      </form>`,
    confirm: () => `
      <h1>${esc(t("Authorize {name}?", { name: device.name }))}</h1>
      <p>${esc(t("It will be able to read and push your projects for {count} days. Only continue if you ran itt auth login yourself.", { count: device.days }))}</p>
      <div class="invite-actions">
        <button class="button button-secondary" type="button" data-device-deny>${iconLabel("close", t("Cancel"))}</button>
        <button class="button button-primary" type="button" data-device-approve>${iconLabel("check", t("Authorize"))}</button>
      </div>
      <p class="field-error" role="alert" hidden></p>`,
    approved: () => `
      <h1>${esc(t("Device connected"))}</h1>
      <p>${esc(t("Return to the terminal. Its token is listed under Settings, where you can revoke it."))}</p>
      <div class="invite-actions">${home}</div>`,
    denied: () => `
      <h1>${esc(t("Not authorized"))}</h1>
      <p>${esc(t("No access was granted."))}</p>
      <div class="invite-actions">${home}</div>`,
  }[device.step]();
  el.siteContent.innerHTML = `<div class="invite-page"><section class="invite-card">${card}</section></div>`;
}

function formatDeviceCode(value) {
  const letters = value.toUpperCase().replace(/[^A-Z]/g, "").slice(0, 8);
  return letters.length > 4 ? `${letters.slice(0, 4)}-${letters.slice(4)}` : letters;
}

function deviceErrorMessage(error) {
  return error.code === "DEVICE_CODE_INVALID" ? t("This code is not valid or has expired. Run itt auth login again.") : serverMessage(error);
}

async function lookupDevice(form) {
  const device = state._device;
  const button = form.querySelector("[type=submit]");
  const code = form.elements["device-code"].value;
  if (!device || !button || button.disabled) return;
  if (code.length !== 9) {
    setFieldError(form, t("Enter the 8-letter code."));
    return;
  }
  setButtonBusy(button, true, "Checking…", "Continue");
  try {
    const result = await fetchJson(apiUrl("/api/v1/auth/device/lookup"), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ code }) });
    if (state._device !== device) return;
    Object.assign(device, { step: "confirm", code, name: result.name, days: result.token_days });
    renderDevicePage();
  } catch (error) {
    setFieldError(form, deviceErrorMessage(error));
    setButtonBusy(button, false, "Checking…", "Continue");
  }
}

async function decideDevice(button, approve) {
  const device = state._device;
  if (!device || button.disabled) return;
  const message = el.siteContent.querySelector(".invite-card .field-error");
  setButtonBusy(button, true, approve ? "Authorizing…" : "Cancelling…", approve ? "Authorize" : "Cancel");
  try {
    await fetchJson(apiUrl("/api/v1/auth/device/decide"), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ code: device.code, approve }) });
    if (state._device !== device) return;
    device.step = approve ? "approved" : "denied";
    renderDevicePage();
  } catch (error) {
    setButtonBusy(button, false, approve ? "Authorizing…" : "Cancelling…", approve ? "Authorize" : "Cancel");
    if (message) { message.textContent = deviceErrorMessage(error); message.hidden = false; }
  }
}
