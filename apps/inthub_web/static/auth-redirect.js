(() => {
  const i18n = window.IntHubI18n;
  i18n.bindStatic(document.body);
  const spinner = document.getElementById("transition-spinner");
  const error = document.getElementById("transition-error");
  const retry = document.getElementById("transition-retry");
  const back = document.getElementById("transition-return");
  const title = document.getElementById("transition-title");
  const candidate = new URLSearchParams(location.search).get("return_to") || "/";
  const returnTo = candidate.startsWith("/") && !candidate.startsWith("//") && !/[\\\x00-\x1f\x7f]/.test(candidate)
    && !candidate.startsWith("/auth/redirect") ? candidate : "/";
  back.href = returnTo;
  let controller = null;
  let errorKey = "";
  function render() {
    title.textContent = i18n.t(errorKey ? "Sign-in could not be completed." : "Connecting to Tenon…");
    error.textContent = i18n.t(errorKey);
  }
  async function prepare() {
    if (controller) return;
    controller = new AbortController();
    const request = controller;
    const timeout = setTimeout(() => request.abort(), 15000);
    errorKey = "";
    spinner.classList.remove("is-hidden");
    error.classList.add("is-hidden");
    retry.classList.add("is-hidden");
    retry.disabled = true;
    render();
    try {
      const response = await fetch("/api/v1/auth/tenon/prepare", {
        method: "POST", credentials: "same-origin", signal: request.signal,
        headers: {"Content-Type": "application/json"}, body: JSON.stringify({return_to: returnTo}),
      });
      const body = await response.json();
      if (!response.ok || body.ok !== true) throw new Error("prepare failed");
      const url = new URL(body.result.authorizationUrl);
      if (url.origin !== "https://account.tenon.asia" || url.pathname !== "/api/auth/oauth2/authorize"
          || url.username || url.password || url.hash) throw new Error("invalid destination");
      location.replace(url.href);
    } catch (failure) {
      errorKey = failure.name === "AbortError" ? "Login request timed out. Try again." : "Could not prepare Tenon sign-in. Try again.";
      spinner.classList.add("is-hidden");
      error.classList.remove("is-hidden");
      retry.classList.remove("is-hidden");
      retry.disabled = false;
      render();
    } finally {
      clearTimeout(timeout);
      controller = null;
    }
  }
  retry.addEventListener("click", prepare);
  document.querySelector("[data-language-switch]").addEventListener("click", () => i18n.setLanguage(i18n.language === "en" ? "zh-CN" : "en"));
  window.addEventListener("inthub:language", render);
  window.addEventListener("pagehide", () => controller?.abort());
  // Let the complete local waiting screen paint before contacting the backend.
  requestAnimationFrame(() => requestAnimationFrame(prepare));
})();
