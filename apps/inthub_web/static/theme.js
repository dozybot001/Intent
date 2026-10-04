/* Apply before painting. This preference contains no account or project data. */
window.IntHubTheme = (() => {
  const modes = ["system", "light", "dark"];
  const media = window.matchMedia("(prefers-color-scheme: dark)");
  let preference = "system";
  try {
    const saved = localStorage.getItem("inthub.theme");
    if (modes.includes(saved)) preference = saved;
  } catch {}
  const icons = {
    system: '<rect x="3" y="4" width="14" height="10" rx="2"/><path d="M7 17h6M10 14v3"/>',
    light: '<circle cx="10" cy="10" r="3.5"/><path d="M10 1.5v2M10 16.5v2M1.5 10h2M16.5 10h2M4 4l1.5 1.5M14.5 14.5 16 16M4 16l1.5-1.5M14.5 5.5 16 4"/>',
    dark: '<path d="M16.8 11.5A7 7 0 0 1 8.5 3.2a7 7 0 1 0 8.3 8.3Z"/>',
  };
  function refreshControls() {
    const key = `Theme: ${preference[0].toUpperCase()}${preference.slice(1)}`;
    for (const button of document.querySelectorAll("[data-theme-switch]")) {
      const label = window.IntHubI18n?.t(key) || key;
      button.setAttribute("aria-label", label);
      button.dataset.preference = preference;
      button.innerHTML = `<svg viewBox="0 0 20 20" aria-hidden="true">${icons[preference]}</svg>`;
    }
    for (const button of document.querySelectorAll("[data-theme-setting]")) {
      const selected = button.dataset.themeSetting === preference;
      button.setAttribute("aria-pressed", String(selected));
      button.classList.toggle("is-selected", selected);
    }
    for (const mark of document.querySelectorAll('img.brand-mark')) {
      mark.setAttribute("src", `/inthub-mark.svg?rev=3${document.documentElement.dataset.theme === "dark" ? "#dark" : ""}`);
    }
  }
  function apply() {
    const theme = preference === "system" ? (media.matches ? "dark" : "light") : preference;
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute("content", theme === "dark" ? "#171717" : "#F6F6F6");
    refreshControls();
  }
  function setPreference(next) {
    if (!modes.includes(next)) return;
    preference = next;
    try { localStorage.setItem("inthub.theme", preference); } catch {}
    apply();
  }
  apply();
  media.addEventListener("change", () => { if (preference === "system") apply(); });
  document.addEventListener("DOMContentLoaded", () => {
    refreshControls();
    document.addEventListener("click", (event) => {
      const setting = event.target.closest("[data-theme-setting]");
      if (setting) setPreference(setting.dataset.themeSetting);
      else if (event.target.closest("[data-theme-switch]")) setPreference(modes[(modes.indexOf(preference) + 1) % modes.length]);
    });
  });
  window.addEventListener("inthub:language", refreshControls);
  return { setPreference, get preference() { return preference; } };
})();
