from pathlib import Path

from apps.inthub_web import product_version


STATIC_DIR = Path(__file__).resolve().parents[1] / "apps" / "inthub_web" / "static"


def test_about_version_reads_build_or_installed_metadata(monkeypatch):
    monkeypatch.setenv("INTHUB_VERSION", "6.0.1+g1234567")
    assert product_version() == "6.0.1+g1234567"
    monkeypatch.delenv("INTHUB_VERSION")
    monkeypatch.setattr("apps.inthub_web.version", lambda _: "6.0.1.dev36")
    assert product_version() == "6.0.1.dev36"


def test_about_does_not_invent_a_version_for_uninstalled_source(monkeypatch):
    from importlib.metadata import PackageNotFoundError

    monkeypatch.delenv("INTHUB_VERSION", raising=False)

    def missing(_):
        raise PackageNotFoundError

    monkeypatch.setattr("apps.inthub_web.version", missing)
    assert product_version() == "Unavailable (unpackaged source)"


def test_web_shell_exposes_continuation_first_navigation():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")

    assert 'data-active-tab="overview"' in html
    assert 'data-tab="overview"' in html
    assert 'data-tab="search"' in html
    assert 'id="search-trigger"' in html
    assert "Continuation queue" in html
    assert "private archive" not in html


def test_web_client_loads_handoff_and_surfaces_checkpoint_contract():
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")

    assert "/handoff" in javascript
    assert "function parseCheckpoint" in javascript
    assert 'checkpointCell("boundary", "Boundary"' in javascript
    assert 'checkpointCell("next", "Next"' in javascript
    assert 'checkpointCell("blocker", "Blocker"' in javascript
    assert "event.metaKey || event.ctrlKey" in javascript


def test_web_shell_uses_soft_cards_without_console_style_color_rails():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert "tenon-product-1" in html
    assert "--shadow-card:" in stylesheet
    assert ".checkpoint-blocker.is-clear" in stylesheet
    assert 'clearBlocker ? " is-clear"' in javascript
    assert "box-shadow: inset 3px 0 0" not in stylesheet
    assert "box-shadow: inset 0 -2px 0" not in stylesheet
    assert "background: rgba(25, 28, 24, 0.97)" not in stylesheet


def test_continuation_brief_does_not_repeat_snap_context_footer():
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert "brief-context" not in javascript
    assert "brief-context" not in stylesheet
    assert "Checkpoint constraint:" not in javascript
    assert '<strong>Constraints:</strong>' in javascript


def test_web_shell_uses_continuity_logo_and_local_default_avatar():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert html.count('class="brand-mark"') == 3
    assert "brand-glyph" not in html
    assert "brand-glyph" not in stylesheet
    assert '<span id="account-avatar" class="account-avatar"' in html
    assert "function accountInitials" in javascript
    assert "function accountAvatarTone" in javascript
    assert "account?.avatar_url" not in javascript
    assert '.account-avatar[data-tone="1"]' in stylesheet


def test_timeline_uses_concise_snap_titles_and_structured_event_rows():
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert "function conciseSnapTitle" in javascript
    assert "function renderTimeline" in javascript
    assert 'class="timeline-entry${status.className}"' in javascript
    assert 'class="timeline-day"' in javascript
    assert 'class="detail-title detail-title-snap"' in javascript
    assert '<h2 class="detail-title">${esc(snap.what)}</h2>' not in javascript
    assert "extractCheckpointParts(snap?.what)" in javascript
    assert "extractCheckpointParts(snap?.why)" in javascript
    assert ".timeline-events::before" in stylesheet
    assert ".detail-title-snap" in stylesheet


def test_intents_are_grouped_by_lifecycle_with_collapsed_history():
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'other.filter((intent) => intent.status === "suspend")' in javascript
    assert 'other.filter((intent) => intent.status === "done")' in javascript
    assert 'other.filter((intent) => intent.status === "cancelled")' in javascript
    assert 'class="object-archive intent-archive"' in javascript
    assert "Active objectives" in javascript
    assert "Resolved history" in javascript
    assert ".intent-entry" in stylesheet
    assert ".object-archive" in stylesheet


def test_decisions_surface_current_constraints_scope_and_deprecated_history():
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert "function decisionScope" in javascript
    assert "function decisionConstraint" in javascript
    assert "Active constraints" in javascript
    assert "No Intent scope recorded" in javascript
    assert "Deprecated history" in javascript
    assert "Current cross-Intent constraint" in javascript
    assert ".decision-constraint" in stylesheet
    assert ".decision-detail-scope" in stylesheet


def test_login_page_matches_the_continuity_workspace_and_keeps_one_auth_path():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'class="auth-trajectory"' in html
    assert 'class="auth-preview"' in html
    assert "Resume with the" in html
    assert "Continuation brief" in html
    assert html.count('id="tenon-login"') == 1
    assert "No repository permissions" in html
    assert "Your account is managed by Tenon" in javascript
    assert ".auth-assurances" in stylesheet
    assert ".auth-preview-flow::before" in stylesheet
    assert "var(--graphite-950);" not in stylesheet[stylesheet.index(".auth-gate {"):stylesheet.index(".auth-stage {")]


def test_tenon_login_has_immediate_loading_feedback_and_recovers_from_history():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'class="tenon-login-spinner"' in html
    assert 'aria-live="polite"' in html
    assert "function setTenonLoginLoading" in javascript
    assert 'setAttribute("aria-busy", String(loading))' in javascript
    assert '"Connecting to Tenon\\u2026"' in javascript
    assert 'window.addEventListener("pageshow"' in javascript
    assert 'event.preventDefault()' in javascript
    assert ".tenon-login.is-loading" in stylesheet
    assert "animation: spin 700ms linear infinite" in stylesheet


def test_showcase_mode_reuses_the_product_shell_without_private_account_actions():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'id="account-mode"' in html
    assert 'data-brand-link' in html
    assert '"/showcase/config.json"' in javascript
    assert "/api/v1/public-profiles/" in javascript
    assert 'el.tokenBtn.classList.toggle("is-hidden", publicMode)' in javascript
    assert 'el.logoutBtn.classList.toggle("is-hidden", publicMode)' in javascript
    assert 'el.projectPickerEyebrow.textContent = "Public collection"' in javascript
    assert ".shell.is-public-view .account-control" in stylesheet
    assert ".account-mode" in stylesheet


def test_product_brand_and_about_follow_tenon_standard():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    mark = (STATIC_DIR / "tenon-mark.svg").read_text(encoding="utf-8")

    assert html.count('class="product-publisher-mark"') == 3
    assert html.count('data-about-open') == 2
    assert 'rel="icon" type="image/svg+xml" href="/tenon-mark.svg"' in html
    assert 'id="about-dialog" aria-labelledby="about-title"' in html
    assert 'id="about-close"' in html
    assert 'id="about-version"' in html
    assert '榫卯 Tenon AI' in html
    assert 'href="https://tenon.asia/"' in html
    assert 'aria-label="IntHub, by Tenon, home"' in html
    assert (html.index('class="brand about-brand"')
            < html.index('id="about-version"')
            < html.index('class="about-description"')
            < html.index('class="about-publisher"'))
    assert 'width: max(14px, 0.58em)' in stylesheet
    assert 'gap: max(4px, 0.18em)' in stylesheet
    assert 'margin-top: -0.04em' in stylesheet
    assert 'state.config?.productVersion || "Unavailable"' in javascript
    assert 'el.aboutDialog.showModal()' in javascript
    assert 'el.aboutDialog.close()' in javascript
    assert 'if (el.aboutDialog.open || el.tokenDialog.open) return' in javascript
    assert 'fill="#f06b32"' in mark
    assert 'M13 16H51V28H38V48H26V28H13Z' in mark
