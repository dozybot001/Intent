/* One dialog for confirmations. */

function openConfirm(spec) {
  state._confirm = spec;
  state._confirmBusy = false;
  el.confirmInput.value = "";
  el.confirmField.hidden = spec.expect === undefined;
  el.confirmError.textContent = "";
  el.confirmError.hidden = true;
  el.confirmOk.disabled = spec.expect !== undefined;
  el.confirmOk.classList.toggle("button-danger", spec.tone !== "neutral");
  el.confirmOk.classList.toggle("button-primary", spec.tone === "neutral");
  el.confirmCancel.disabled = false;
  localizeConfirm();
  el.confirmDialog.showModal();
  (spec.expect === undefined ? el.confirmCancel : el.confirmInput).focus();
}

function localizeConfirm() {
  const spec = state._confirm;
  if (!spec) return;
  el.confirmTitle.textContent = spec.title();
  el.confirmBody.textContent = spec.body();
  el.confirmLabel.innerHTML = spec.label ? spec.label() : "";
  el.confirmOk.innerHTML = iconLabel(spec.icon, t(state._confirmBusy ? spec.busy : spec.action));
}

async function runConfirm() {
  const spec = state._confirm;
  if (!spec || state._confirmBusy || el.confirmOk.disabled) return;
  const typed = el.confirmInput.value;
  if (spec.expect !== undefined && typed !== spec.expect) return;
  state._confirmBusy = true;
  setButtonBusy(el.confirmOk, true, spec.busy, spec.action);
  el.confirmCancel.disabled = true;
  el.confirmError.hidden = true;
  try {
    await spec.run(typed);
    state._confirmBusy = false;
    if (el.confirmDialog.open) el.confirmDialog.close();
  } catch (error) {
    state._confirmBusy = false;
    el.confirmError.textContent = error.code === "CONFIRMATION_MISMATCH" ? t("Type the name exactly as shown.") : (spec.message || ((reason) => reason.message))(error);
    el.confirmError.hidden = false;
  } finally {
    state._confirmBusy = false;
    setButtonBusy(el.confirmOk, false, spec.busy, spec.action);
    el.confirmCancel.disabled = false;
    if (spec.expect !== undefined) el.confirmOk.disabled = el.confirmInput.value !== spec.expect;
  }
}
