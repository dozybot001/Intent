(() => {
  const copy = {
    auth: "No repository access is requested. Tenon manages identity; IntHub keeps its own 30-day session.",
    search: "Search matches goals, checkpoints and decisions within the selected project. Cmd/Ctrl+K opens search.",
    decisions: "Rules that remain binding across linked objectives.",
    setup: "Run these commands where your .intent/ data lives.",
    history: "Every revision on main, like git log: what it added or changed, who made it and when. Open one to see the objects.",
    verified: "Pushed by the account that owns this email.",
    flow: "Part of branches off its parent, and ended parts come back together at one point. Derived from branches off without coming back. Succeeds is a thick arrow into the next goal on the row. Depends on is a thin arrow from the prerequisite: amber while blocked, green once satisfied, red if it was cancelled. Conflicts with is a dashed line marked vs until one side ends. Diamonds are Decisions; hollow ones are deprecated.",
  };
  // Short hints on hover or focus take the same popover in place of the browser's own title tooltip.
  const hints = "[data-help], [data-help-copy], [data-tip]";
  const panel = document.getElementById("help-popover");
  let trigger = null;
  let pinned = false;
  let timer;
  function close() {
    if (trigger) {
      if (trigger.dataset.tip === undefined) trigger.setAttribute("aria-expanded", "false");
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
    if (rect.bottom < top + 16 || rect.top > top + height - 16) return close();
    panel.style.width = panel.classList.contains("is-tip") ? "" : `${Math.min(260, width - 32)}px`;
    const below = top + height - rect.bottom - 24;
    const above = rect.top - top - 24;
    const useAbove = below < 150 && above > below;
    panel.style.maxHeight = `${Math.min(height - 32, Math.max(48, useAbove ? above : below))}px`;
    panel.style.left = `${Math.min(Math.max(left + 16, rect.left), left + width - panel.offsetWidth - 16)}px`;
    const preferredTop = useAbove ? rect.top - panel.offsetHeight - 8 : rect.bottom + 8;
    panel.style.top = `${Math.max(top + 16, Math.min(preferredTop, top + height - panel.offsetHeight - 16))}px`;
  }
  function open(button, pin = false) {
    clearTimeout(timer);
    if (pin && trigger === button && pinned) return close();
    if (trigger !== button) close();
    const tip = button.dataset.tip;
    if (tip === "") return;
    trigger = button;
    pinned = pin || pinned;
    panel.textContent = tip ?? window.IntHubI18n.t(copy[button.dataset.help] || button.dataset.helpCopy || "");
    panel.classList.toggle("is-tip", tip !== undefined);
    (button.closest("dialog") || document.body).appendChild(panel);
    panel.hidden = false;
    if (!panel.matches(":popover-open")) panel.showPopover();
    button.setAttribute("aria-describedby", "help-popover");
    if (tip === undefined) button.setAttribute("aria-expanded", "true");
    position();
  }
  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-help], [data-help-copy]");
    if (button) open(button, true);
    else if (!panel.contains(event.target)) close();
  });
  document.addEventListener("pointerover", (event) => {
    if (event.pointerType === "touch") return;
    const button = event.target.closest(hints);
    if (button && (!pinned || trigger === button)) open(button);
    if (panel.contains(event.target)) clearTimeout(timer);
  });
  document.addEventListener("pointerout", (event) => {
    if (!pinned && (event.target.closest(hints) || panel.contains(event.target))) timer = setTimeout(close, 180);
  });
  document.addEventListener("focusin", (event) => {
    const button = event.target.closest(hints);
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
