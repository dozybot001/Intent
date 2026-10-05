from pathlib import Path
from html.parser import HTMLParser
import re
import shutil
import subprocess

import pytest

from apps.inthub_web import product_version


STATIC_DIR = Path(__file__).resolve().parents[1] / "apps" / "inthub_web" / "static"


class _MarkupTags(HTMLParser):
    """Collect element attributes and ancestry without rendering the page."""

    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.stack = []
        self.feed(html)

    def handle_starttag(self, tag, attributes):
        attributes = dict(attributes)
        self.tags.append((tag, attributes, tuple(identifier for _, identifier in self.stack)))
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}:
            self.stack.append((tag, attributes.get("id")))

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == tag:
                del self.stack[index:]
                break

    def within(self, identifier):
        return [(tag, attributes) for tag, attributes, ancestors in self.tags if identifier in ancestors]


def test_header_groups_preferences_and_account_actions_in_separate_menus():
    html = (STATIC_DIR / "index.html").read_text()
    header = html.split('<header class="app-header">', 1)[1].split('</header>', 1)[0]
    markup = _MarkupTags(header)
    assert 'id="settings-menu-trigger"' in header
    assert 'id="account-menu-trigger"' in header
    assert 'data-theme-switch' not in header and 'data-language-switch' not in header
    settings = markup.within("settings-menu")
    assert any("data-theme-setting" in attributes for _, attributes in settings)
    assert any("data-language-select" in attributes for _, attributes in settings)
    assert any(attributes.get("id") == "refresh-btn" for _, attributes in settings)
    assert any("data-about-open" in attributes for _, attributes in settings)
    account = markup.within("account-actions")
    assert {"account-label", "token-btn", "logout-btn"}.issubset({attributes.get("id") for _, attributes in account})
    assert not any("data-theme-setting" in attributes or "data-language-select" in attributes for _, attributes in account)
    assert header.index('id="account-menu-trigger"') < header.index('id="settings-menu-trigger"')
    assert 'id="auth-settings-menu"' in html


def test_product_resource_links_have_fixed_official_targets_and_safe_new_tabs():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    markup = _MarkupTags(html)
    targets = {
        "skill": "https://www.skills.sh/dozybot001/intent/intent-cli",
        "repository": "https://github.com/dozybot001/Intent",
    }
    links = [(tag, attributes) for tag, attributes, _ in markup.tags if "data-product-link" in attributes]
    assert links
    for tag, attributes in links:
        assert tag == "a"
        assert attributes["href"] == targets[attributes["data-product-link"]]
        assert attributes.get("target") == "_blank"
        assert {"noopener", "noreferrer"}.issubset(attributes.get("rel", "").split())
        assert "onclick" not in attributes
    header = html.split('<header class="app-header">', 1)[1].split('</header>', 1)[0]
    auth_tags = [(tag, attributes, ancestors) for tag, attributes, ancestors in markup.tags if "auth-gate" in ancestors]
    for scope in (_MarkupTags(header).tags, auth_tags):
        assert {attributes["data-product-link"] for _, attributes, _ in scope if "data-product-link" in attributes} == set(targets)


def test_resource_menus_share_accessible_header_menu_control_flow():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    markup = _MarkupTags(html)
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    triggers = [(tag, attributes) for tag, attributes, _ in markup.tags if "data-resources-trigger" in attributes]
    assert {attributes["id"] for _, attributes in triggers} == {"resources-menu-trigger", "auth-resources-menu-trigger"}
    for tag, attributes in triggers:
        assert tag == "button" and attributes.get("type") == "button"
        assert attributes.get("aria-expanded") == "false"
        assert attributes.get("aria-label")
        panel_id = attributes["aria-controls"]
        panels = [attributes for _, attributes, _ in markup.tags if attributes.get("id") == panel_id]
        assert len(panels) == 1
        assert "inert" in panels[0] and panels[0].get("role") == "group"
        assert {"header-menu", "resources-menu"}.issubset(panels[0].get("class", "").split())
        assert {attributes["data-product-link"] for _, attributes in markup.within(panel_id) if "data-product-link" in attributes} == {"skill", "repository"}
    menu_enumeration = javascript.split("function headerMenus()", 1)[1].split("function headerMenuControls", 1)[0]
    assert 'querySelectorAll("[data-resources-trigger]")' in menu_enumeration
    assert 'querySelectorAll("button, a[href]")' in javascript
    assert 'if (event.key === "Escape" && openMenu)' in javascript
    assert 'if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return' in javascript


def test_compact_login_header_uses_resource_menu_even_on_wide_viewports():
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    links = re.search(r"\.auth-header \.header-resources\s*\{([^}]+)", css).group(1)
    menu = re.search(r"\.auth-header \.resources-control\s*\{([^}]+)", css).group(1)
    assert "display: none" in links
    assert "display: flex" in menu


def test_project_context_and_options_use_horizontal_flexible_rows():
    css = (STATIC_DIR / "styles.css").read_text()
    for selector in (".project-picker-copy", ".project-picker-option"):
        block = re.search(re.escape(selector) + r"\s*\{([^}]+)", css).group(1)
        assert "display: flex" in block
        assert "align-items: center" in block
    trigger = re.search(r"\.project-picker-trigger\s*\{([^}]+)", css).group(1)
    assert "min-width: 0" in trigger
    label = re.search(r"\.project-picker-label\s*\{([^}]+)", css).group(1)
    assert "min-width: 0" in label and "text-overflow: ellipsis" in label
    name = re.search(r"\.project-picker-option-name\s*\{([^}]+)", css).group(1)
    assert "min-width: 0" in name
    assert "text-overflow: ellipsis" in name
    assert "white-space: nowrap" in name
    description = re.search(r"\.project-picker-option-repo\s*\{([^}]+)", css).group(1)
    assert "flex: 0 0 auto" in description
    assert "white-space: nowrap" in description


def test_index_heading_is_one_row_and_list_height_follows_its_content():
    html = (STATIC_DIR / "index.html").read_text()
    css = (STATIC_DIR / "styles.css").read_text()
    header = re.search(r"\.index-header\s*\{([^}]+)", css).group(1)
    assert "display: flex" in header and "align-items: center" in header
    sidebar = re.search(r"\.sidebar\s*\{([^}]+)", css).group(1)
    assert "grid-template-rows: auto minmax(0, 1fr)" in sidebar
    title = re.search(r"\.index-title\s*\{([^}]+)", css).group(1)
    assert "min-width: 0" in title and "margin: 0" in title
    assert "white-space: nowrap" in title and "text-overflow: ellipsis" in title
    assert "order:" not in title
    assert html.index('id="sidebar-title"') < html.index('id="sidebar-kicker"')
    for body in re.findall(r"\.sidebar-body\s*\{([^}]+)", css):
        assert "height: calc(" not in body


def test_detail_canvas_does_not_keep_fixed_desktop_width_caps():
    css = (STATIC_DIR / "styles.css").read_text()
    content = re.search(r"\.detail-content\s*\{([^}]+)", css).group(1)
    assert "width: 100%" in content
    assert "1120px" not in content and "margin: 0 auto" not in content
    for selector in (".detail-header", ".detail-header-snap", ".detail-section"):
        block = re.search(re.escape(selector) + r"\s*\{([^}]+)", css).group(1)
        assert "max-width: none" in block
    title = re.search(r"\.detail-title\s*\{([^}]+)", css).group(1)
    assert "max-width: 100%" in title
    assert "28ch" not in title
    # A fluid canvas should not turn paragraphs into unbounded reading lines.
    paragraph = re.search(r"\.detail-section p\s*\{([^}]+)", css).group(1)
    assert "max-width: 74ch" in paragraph


def test_navigation_loading_does_not_insert_spinners_into_card_layout():
    javascript = (STATIC_DIR / "app.js").read_text()
    css = (STATIC_DIR / "styles.css").read_text()
    for target in ('card', 'tabButton', 'el.projectPickerTrigger'):
        assert f'setButtonBusy({target},' not in javascript
    assert 'view-loading' in javascript and 'view-loading' in css
    assert '.is-busy::before' not in css
    assert '.action-busy' in css


def test_ui_palette_is_monochrome_without_changing_official_tenon_asset():
    css = (STATIC_DIR / 'styles.css').read_text()
    for color in re.findall(r'#([0-9a-fA-F]{3,8})(?![\w-])', css):
        assert len(color) in (3, 4, 6, 8), color
        rgb = ''.join(channel * 2 for channel in color[:3]) if len(color) < 6 else color[:6]
        assert rgb[0:2].lower() == rgb[2:4].lower() == rgb[4:6].lower(), color
    for channels in re.findall(r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', css):
        assert len(set(channels)) == 1, channels
    for channels in re.findall(r'--[\w-]+-rgb:\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)', css):
        assert len(set(channels)) == 1, channels
    assert 'fill="#f06b32"' in (STATIC_DIR / 'tenon-mark.svg').read_text()


def test_primary_theme_text_and_status_color_pairs_have_readable_contrast():
    css = (STATIC_DIR / "styles.css").read_text()
    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))
    for selector in (":root", ':root[data-theme="dark"]'):
        block = re.search(re.escape(selector) + r'\s*\{([^}]+)', css).group(1)
        tokens = dict(re.findall(r'--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;', block))
        for foreground, background in (("ink", "canvas"), ("muted", "surface"), ("muted", "surface-nav"), ("copper", "surface-strong"), ("green", "green-soft"), ("amber", "amber-soft"), ("red", "red-soft"), ("blue", "blue-soft")):
            low, high = sorted((luminance(tokens[foreground]), luminance(tokens[background])))
            assert (high + 0.05) / (low + 0.05) >= 4.5, (selector, foreground, background)


def test_theme_and_local_font_cover_all_entry_pages_without_external_loading():
    for name in ("index.html", "auth-redirect.html"):
        html = (STATIC_DIR / name).read_text()
        assert 'content="light dark"' in html
        assert 'src="/theme.js?rev=header-mono-1"' in html
        assert html.index('/theme.js?') < html.index('/styles.css?')
        assert 'data-theme-switch' in html or 'data-theme-setting' in html
        assert 'href="/InterVariable.woff2"' in html
    css = (STATIC_DIR / "styles.css").read_text()
    assert '@font-face' in css and 'font-display: swap' in css
    assert 'url("/InterVariable.woff2")' in css
    assert '[data-theme="dark"]' in css
    assert '0 12px 32px #00000066, 0 2px 6px #00000033' in css
    assert 'https://' not in css
    menu = css.split('.timeline-filter-menu {', 1)[1].split('}', 1)[0]
    assert 'position: relative' in menu and '35dvh' in menu
    assert 'SIL OPEN FONT LICENSE Version 1.1' in (STATIC_DIR / 'Inter-LICENSE.txt').read_text()


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable for frontend logic tests")
def test_bilingual_rendering_preserves_user_content_and_immediate_loading():
    subprocess.run(["node", str(Path(__file__).with_name("inthub_web_logic.cjs"))], check=True, capture_output=True, text=True)
    subprocess.run(["node", str(Path(__file__).with_name("inthub_theme_logic.cjs"))], check=True, capture_output=True, text=True)


def test_updated_standard_uses_fixed_redirect_help_and_shared_dialog_layout():
    html = (STATIC_DIR / "index.html").read_text()
    javascript = (STATIC_DIR / "app.js").read_text()
    css = (STATIC_DIR / "styles.css").read_text()
    redirect = (STATIC_DIR / "auth-redirect.js").read_text()
    help_script = (STATIC_DIR / "help.js").read_text()
    assert 'href="/auth/redirect"' in html
    assert 'class="heading-with-help"' in html
    assert 'data-help="auth"' in html and 'data-help="token"' in html
    assert 'gap: 6px' in css and 'border-radius: 12px' in css
    assert '0 12px 32px #00000016, 0 2px 6px #00000008' in css
    assert 'panel.showPopover()' in help_script and 'aria-describedby' in help_script
    assert 'rect.bottom < top + 16' in help_script
    assert 'Math.min(preferredTop, top + height - panel.offsetHeight - 16)' in help_script
    assert '--dialog-width:' in css and '--dialog-height:' in css
    assert css.count('height: var(--dialog-height)') == 2
    assert 'grid-template-rows: auto minmax(0, 1fr) auto' in css
    assert 'class="dialog-body"' in html
    assert 'data-language-select' in html and 'localizeWorkspace' in javascript
    assert '/api/v1/auth/tenon/prepare' in redirect
    assert 'url.origin !== "https://account.tenon.asia"' in redirect
    assert '15000' in redirect and 'requestAnimationFrame' in redirect
    assert 'document.write' not in javascript + redirect and 'about:blank' not in javascript + redirect
    assert 'type="checkbox"' not in html + javascript


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
    assert 'checkpointCell("boundary", t("Boundary")' in javascript
    assert 'checkpointCell("next", t("Next")' in javascript
    assert 'checkpointCell("blocker", t("Blocker")' in javascript
    assert "event.metaKey || event.ctrlKey" in javascript


def test_web_shell_uses_soft_cards_without_console_style_color_rails():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert "header-mono-1" in html
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
    assert '<strong>${esc(t("Constraints:"))}</strong>' in javascript


def test_web_shell_uses_monochrome_continuity_logo_and_explicit_account_icon():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert html.count('class="brand-mark"') == 3
    assert html.count('src="/inthub-mark.svg?rev=3"') == 3
    assert "brand-mark-rail" not in html + stylesheet
    import xml.etree.ElementTree as ET
    mark = ET.parse(STATIC_DIR / "inthub-mark.svg").getroot()
    assert mark.attrib["viewBox"] == "0 0 32 32"
    paths = mark.findall(".//{http://www.w3.org/2000/svg}path")
    assert len(paths) == 2
    uses = mark.findall("{http://www.w3.org/2000/svg}use")
    assert {entry.attrib["fill"] for entry in uses} == {"#181818", "#858585", "#F3F3F3"}
    assert mark.find("{http://www.w3.org/2000/svg}view").attrib["id"] == "dark"
    assert mark.find("{http://www.w3.org/2000/svg}style") is None
    assert "brand-glyph" not in html
    assert "brand-glyph" not in stylesheet
    account_button = html.split('id="account-menu-trigger"', 1)[1].split('</button>', 1)[0]
    assert '<svg' in account_button and 'account-avatar' not in account_button
    assert 'aria-controls="account-actions"' in account_button
    assert "account?.avatar_url" not in javascript


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

    auth = html.split('id="auth-gate"', 1)[1].split('<dialog class="about-dialog"', 1)[0]
    assert 'class="auth-introduction"' in auth
    assert '<h1 id="auth-title" class="heading-with-help">Sign in to IntHub' in auth
    assert "Continue with your project context intact." in auth
    assert 'id="auth-settings-menu-trigger"' in auth
    assert 'data-theme-setting' in auth and 'data-language-select' in auth
    assert 'data-about-open' in auth
    assert 'class="brand brand-on-auth"' in auth
    assert html.count('id="tenon-login"') == 1
    assert 'id="tenon-login" href="/auth/redirect"' in auth
    assert 'id="tenon-login-label" aria-live="polite"' in auth
    assert 'class="tenon-login-spinner"' in auth
    assert 'id="auth-error" role="alert"' in auth
    assert 'data-help="auth"' in auth
    assert '<form' not in auth and '<input' not in auth
    assert "auth-trajectory" not in auth + stylesheet
    assert "auth-preview" not in auth + stylesheet
    assert "auth-assurances" not in auth + stylesheet
    assert "No repository access is requested" in (STATIC_DIR / "help.js").read_text()
    assert '.auth-stage {' in stylesheet and 'width: min(448px, 100%)' in stylesheet
    assert 'align-items: safe center' in stylesheet
    assert 'grid-template-columns: 22px minmax(0, 1fr)' in stylesheet
    assert '.tenon-login.is-loading .tenon-login-spinner' in stylesheet
    assert 'setTenonLoginLoading(true)' in javascript
    translations = (STATIC_DIR / "i18n.js").read_text()
    assert '"Sign in to IntHub": "登录 IntHub"' in translations
    assert '"Continue with your project context intact.": "保留项目上下文，继续工作。"' in translations


def test_tenon_login_has_immediate_loading_feedback_and_recovers_from_history():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    javascript = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    stylesheet = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    assert 'class="tenon-login-spinner"' in html
    assert 'aria-live="polite"' in html
    assert "function setTenonLoginLoading" in javascript
    assert 'setAttribute("aria-busy", String(loading))' in javascript
    assert 't("Connecting to Tenon…")' in javascript
    assert 'window.addEventListener("pageshow"' in javascript
    assert 'event.preventDefault()' in javascript
    assert ".tenon-login.is-loading" in stylesheet
    assert "animation: spin 700ms linear infinite" in stylesheet


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
    assert 'state.config?.productVersion || t("Unavailable")' in javascript
    assert 'el.aboutDialog.showModal()' in javascript
    assert 'el.aboutDialog.close()' in javascript
    assert 'if (el.aboutDialog.open || el.tokenDialog.open) return' in javascript
    assert 'fill="#f06b32"' in mark
    assert 'M13 16H51V28H38V48H26V28H13Z' in mark
