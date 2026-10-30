/* Select: the browser's popup ignores the page's look, so this is a listbox of our own. The value lives in a
   hidden input, which forms and change listeners read like any field. Its id must differ from its name:
   a form lists both under one key, and form.elements[name].value then reads empty. */
function selectField({ id, name = "", value, options, label = "", className = "", attrs = "" }) {
  const selected = options.find((option) => String(option.value) === String(value)) || options[0];
  return `
    <div class="select${className ? ` ${className}` : ""}" data-select>
      <input type="hidden"${name ? ` name="${esc(name)}"` : ""} value="${esc(selected.value)}"${attrs}>
      <button class="text-field select-trigger" id="${esc(id)}" type="button" role="combobox" aria-haspopup="listbox" aria-expanded="false" aria-controls="${esc(id)}-options"${label ? ` aria-label="${esc(label)}"` : ""}>
        <span class="select-value">${esc(selected.label)}</span>${icon("chevronDown")}
      </button>
      <div class="select-menu" id="${esc(id)}-options" role="listbox" popover="manual"${label ? ` aria-label="${esc(label)}"` : ""}>
        ${options.map((option) => `<button class="select-option" type="button" role="option" tabindex="-1" data-value="${esc(option.value)}" aria-selected="${option === selected}">${icon("check")}<span>${esc(option.label)}</span></button>`).join("")}
      </div>
    </div>`;
}

function selectParts(root) {
  return { input: root.querySelector("input"), trigger: root.querySelector(".select-trigger"), menu: root.querySelector(".select-menu") };
}

function closeSelect({ focus = false } = {}) {
  const root = state._openSelect;
  if (!root) return;
  state._openSelect = null;
  const { trigger, menu } = selectParts(root);
  trigger.setAttribute("aria-expanded", "false");
  if (menu.matches(":popover-open")) menu.hidePopover();
  if (focus) trigger.focus();
}

// The menu sits in the top layer, so nothing clips it; it opens below the field unless the window ends first.
function openSelect(root) {
  closeSelect();
  const { trigger, menu } = selectParts(root);
  if (trigger.disabled) return;
  state._openSelect = root;
  trigger.setAttribute("aria-expanded", "true");
  menu.style.minWidth = `${trigger.offsetWidth}px`;
  menu.showPopover();
  const rect = trigger.getBoundingClientRect();
  const fits = rect.bottom + menu.offsetHeight + 12 <= window.innerHeight;
  menu.style.top = `${fits ? rect.bottom + 4 : Math.max(8, rect.top - menu.offsetHeight - 4)}px`;
  menu.style.left = `${Math.max(8, Math.min(rect.left, window.innerWidth - menu.offsetWidth - 8))}px`;
  menu.querySelector('[aria-selected="true"]').focus({ preventScroll: true });
}

function setSelectValue(input, value) {
  const { trigger, menu } = selectParts(input.closest("[data-select]"));
  input.value = value;
  for (const option of menu.querySelectorAll("[role=option]")) {
    const selected = option.dataset.value === String(value);
    option.setAttribute("aria-selected", String(selected));
    if (selected) trigger.querySelector(".select-value").textContent = option.textContent;
  }
}

function chooseOption(option) {
  const root = option.closest("[data-select]");
  const { input } = selectParts(root);
  const changed = input.value !== option.dataset.value;
  setSelectValue(input, option.dataset.value);
  closeSelect({ focus: true });
  if (!changed) return;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function selectKeydown(event) {
  const root = event.target.closest?.("[data-select]");
  if (!root) return;
  if (event.key === "Escape") {
    if (root !== state._openSelect) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    closeSelect({ focus: true });
    return;
  }
  if (root !== state._openSelect) {
    if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
    event.preventDefault();
    openSelect(root);
    return;
  }
  const options = [...root.querySelectorAll("[role=option]")];
  const current = options.indexOf(document.activeElement);
  const typed = event.key.length === 1 && !event.metaKey && !event.ctrlKey && !event.altKey && event.key !== " "
    ? [...options.slice(current + 1), ...options.slice(0, current + 1)].find((option) => option.textContent.trim().toLowerCase().startsWith(event.key.toLowerCase()))
    : null;
  const target = typed || { ArrowDown: options[(current + 1) % options.length], ArrowUp: options.at(current - 1), Home: options[0], End: options.at(-1) }[event.key];
  if (!target) return;
  event.preventDefault();
  target.focus();
}
