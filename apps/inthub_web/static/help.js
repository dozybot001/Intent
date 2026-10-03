(() => {
  const copy = {
    auth: "No repository access is requested. Tenon manages identity; IntHub keeps its own short-lived session.",
    token: "A token grants CLI access to your own projects. It is shown once; keep it secret and revoke it when no longer needed.",
    search: "Search matches goals, checkpoints and decisions within the selected project. Cmd/Ctrl+K opens search.",
    decisions: "Rules that remain binding across linked objectives.",
    setup: "Run these commands where your .intent/ data lives.",
  };
  const panel = document.getElementById("help-popover");
  let trigger = null;
  let pinned = false;
  let timer;
  function close() {
    if (trigger) {
      trigger.setAttribute("aria-expanded", "false");
      trigger.removeAttribute("aria-describedby");
    }
    if (panel.matches(":popover-open")) panel.hidePopover();
    panel.hidden = true;
    trigger = null;
    pinned = false;
  }
  function position() {
    if (!trigger || !trigger.isConnected) return close();
    const rect = trigger.getBoundingClientRect();
    const viewport = window.visualViewport;
    const width = viewport?.width || innerWidth;
    const height = viewport?.height || innerHeight;
    const left = viewport?.offsetLeft || 0;
    const top = viewport?.offsetTop || 0;
    panel.style.width = `${Math.min(260, width - 32)}px`;
    const below = top + height - rect.bottom - 24;
    const above = rect.top - top - 24;
    const useAbove = below < 150 && above > below;
    panel.style.maxHeight = `${Math.max(48, useAbove ? above : below)}px`;
    panel.style.left = `${Math.min(Math.max(left + 16, rect.left), left + width - panel.offsetWidth - 16)}px`;
    panel.style.top = `${useAbove ? rect.top - panel.offsetHeight - 8 : rect.bottom + 8}px`;
  }
  function open(button, pin = false) {
    clearTimeout(timer);
    if (pin && trigger === button && pinned) return close();
    if (trigger !== button) close();
    trigger = button;
    pinned = pin || pinned;
    panel.textContent = window.IntHubI18n.t(copy[button.dataset.help] || button.dataset.helpCopy || "");
    (button.closest("dialog") || document.body).appendChild(panel);
    panel.hidden = false;
    if (!panel.matches(":popover-open")) panel.showPopover();
    button.setAttribute("aria-describedby", "help-popover");
    button.setAttribute("aria-expanded", "true");
    position();
  }
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-help], [data-help-copy]");
    if (button) open(button, true);
    else if (!panel.contains(event.target)) close();
  });
  document.addEventListener("pointerover", (event) => {
    if (event.pointerType === "touch") return;
    const button = event.target.closest("[data-help], [data-help-copy]");
    if (button && (!pinned || trigger === button)) open(button);
    if (panel.contains(event.target)) clearTimeout(timer);
  });
  document.addEventListener("pointerout", (event) => {
    if (!pinned && (event.target.closest("[data-help], [data-help-copy]") || panel.contains(event.target))) timer = setTimeout(close, 180);
  });
  document.addEventListener("focusin", (event) => {
    const button = event.target.closest("[data-help], [data-help-copy]");
    if (button) open(button);
  });
  document.addEventListener("focusout", () => { if (!pinned) timer = setTimeout(close, 180); });
  document.addEventListener("keydown", (event) => { if (event.key === "Escape" && trigger) { close(); event.preventDefault(); event.stopImmediatePropagation(); } }, true);
  document.addEventListener("scroll", position, true);
  window.addEventListener("resize", position);
  window.visualViewport?.addEventListener("resize", position);
  window.addEventListener("inthub:language", () => { if (trigger) open(trigger); });
  for (const dialog of document.querySelectorAll("dialog")) dialog.addEventListener("close", close);
})();
