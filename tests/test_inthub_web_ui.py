from pathlib import Path
from html.parser import HTMLParser
import json
import os
import re
import shutil
import subprocess

import pytest

from apps.inthub_api import queries
from apps.inthub_api.server import REVISION_PAGE_MAX
from apps.inthub_web import product_version
from intent_cli import identity, relations, store


ROOT = Path(__file__).resolve().parents[1]
STATIC_DIR = ROOT / "apps" / "inthub_web" / "static"
STATUS_TOKEN = re.compile(r"--(?:blue|green|amber|red)(?:-soft|-line|-dot)?$")


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

    def by_id(self, identifier):
        return next((tag, attributes) for tag, attributes, _ in self.tags if attributes.get("id") == identifier)


def _static(name):
    return (STATIC_DIR / name).read_text(encoding="utf-8")


def _block(css, selector):
    return re.search(re.escape(selector) + r"\s*\{([^}]+)", css).group(1)


def _is_neutral(color):
    channels = color[:3] if len(color) in (3, 4) else color[:6]
    rgb = "".join(channel * 2 for channel in channels) if len(channels) == 3 else channels
    return rgb[0:2].lower() == rgb[2:4].lower() == rgb[4:6].lower()


def test_header_keeps_preferences_settings_and_account_apart():
    html = _static("index.html")
    header = html.split('<header class="app-header">', 1)[1].split('</header>', 1)[0]
    markup = _MarkupTags(header)
    trigger = re.search(r'<button[^>]*id="preferences-menu-trigger"[^>]*>', header).group(0)
    assert 'aria-label="Preferences"' in trigger
    assert 'id="account-menu-trigger"' in header
    assert 'data-theme-switch' not in header and 'data-language-switch' not in header
    # Preferences have their own icon: the gear means Settings, and its link opens the dialog.
    assert header.count('<circle cx="10" cy="10" r="2.5"/>') == 1
    assert header.count('<circle cx="11" cy="6" r="2"/>') == 1
    gear = re.search(r'<a[^>]*id="settings-link"[^>]*>(.*?)</a>', header).group(0)
    assert 'href="/settings"' in gear and "data-route" in gear and 'aria-label="Settings"' in gear and 'r="2.5"' in gear
    # Visitors keep Preferences; Settings and the account control give way to a small Sign in button.
    assert header.index('id="preferences-menu-trigger"') < header.index('id="sign-in-button"') < header.index('id="account-control"')
    assert header.index('id="account-control"') < header.index('id="settings-link"') < header.index('id="account-menu-trigger"')
    assert 'id="sign-in-button" class="button button-secondary button-small is-hidden"' in header
    preferences = markup.within("preferences-menu")
    assert any("data-theme-setting" in attributes for _, attributes in preferences)
    assert any("data-language-select" in attributes for _, attributes in preferences)
    assert any(attributes.get("id") == "refresh-btn" for _, attributes in preferences)
    assert any("data-about-open" in attributes for _, attributes in preferences)
    account = markup.within("account-actions")
    ids = {attributes.get("id") for _, attributes in account}
    # The account and nothing else: who you are, your profile, Tenon and Sign out.
    assert {"account-label", "account-mode", "logout-btn"}.issubset(ids)
    assert not {"token-btn", "delete-account-btn", "settings-link"} & ids
    assert [attributes["href"] for tag, attributes in account if tag == "a" and "data-route" in attributes] == ["/account"]
    assert any(attributes.get("href") == "https://account.tenon.asia/account/" for _, attributes in account)
    assert not any("data-theme-setting" in attributes or "data-language-select" in attributes for _, attributes in account)
    assert 'id="auth-preferences-menu"' in html


def test_every_option_reads_as_an_icon_and_a_label():
    html = _static("index.html")
    javascript = _static("app.js")
    names = set(re.findall(r"^  (\w+): '", javascript.split("const ICONS = {", 1)[1].split("\n};", 1)[0], re.M))
    # Static markup names its icons from the one set.
    for name in re.findall(r'data-icon="(\w+)"', html):
        assert name in names
    for match in re.finditer(r'<(?:button|a)\b[^>]*class="(?:[^"]* )?(?:menu-action|tab|button|search-close|auth-dismiss|header-resource-link)[ "][^>]*>', html):
        # The confirm button takes its icon from what it confirms.
        assert "data-icon=" in match.group(0) or 'id="confirm-ok"' in match.group(0), match.group(0)
    for match in re.finditer(r'<button\b[^>]*data-theme-setting[^>]*>', html):
        assert "data-icon=" in match.group(0), match.group(0)
    # So do the templates: no button or nav item is text alone.
    for name in re.findall(r'(?:iconLabel\(|icon\()"(\w+)"', javascript):
        assert name in names
    assert not re.search(r'class="(?:button |secondary-btn|load-more-btn)[^`\n]*>\$\{esc\(', javascript)
    assert "<svg" in html.split('data-login-method="email"', 1)[1].split("</a>", 1)[0]
    # The label is what changes while busy, so the icon stays.
    assert "button.textContent = t(" not in javascript and "setButtonLabel(button, t(busy ? loadingCopy : idleCopy))" in javascript
    # Each confirmation says what it does, with the same icon as the button that opened it.
    assert javascript.count("openConfirm({") == len(re.findall(r'^    action: .*\n    icon: ', javascript, re.M)) == 7
    assert 'iconLabel(spec.icon, t(state._confirmBusy ? spec.busy : spec.action))' in javascript
    for item in re.findall(r'\{ label: t\("[^"]+"\),[^\n}]*\}', javascript):
        assert "icon:" in item, item


def test_focus_rings_are_for_keyboards_and_nav_items_keep_their_distance():
    css = _static("styles.css")
    javascript = _static("app.js")
    assert 'none' in _rule(css, ':root[data-input="pointer"] :focus-visible')
    assert 'document.addEventListener("pointerdown"' in javascript and 'dataset.input = "keyboard"' in javascript
    # A screenshot shortcut or a bare modifier is not keyboard navigation.
    assert '["Shift", "Meta", "Control", "Alt"].includes(event.key)' in javascript
    desktop, phone = css.split("@media (max-width: 720px)", 1)
    assert "gap: 6px" in _rule(desktop.split("@media (max-width: 1180px)", 1)[0], ".settings-nav")
    assert "gap: 6px" in phone.split(".settings-nav {", 1)[1].split("}", 1)[0]


def test_header_utilities_have_breathing_room_at_every_breakpoint():
    css = _static("styles.css")
    utilities = re.findall(r"\.header-utilities\s*\{([^}]+)", css)
    assert utilities
    assert int(re.search(r"\bgap:\s*(\d+)px", utilities[0]).group(1)) >= 12
    assert "padding-left: 16px" in utilities[0]
    for block in utilities:
        assert int(re.search(r"\bgap:\s*(\d+)px", block).group(1)) >= 8
    actions = next(block for block in re.findall(r"\.header-actions\s*\{([^}]+)", css) if "justify-content: flex-end" in block)
    assert int(re.search(r"\bgap:\s*(\d+)px", actions).group(1)) >= 16
    hover = re.search(r'\.app-header \.icon-button\[aria-current="page"\]\s*\{([^}]+)', css).group(1)
    assert "border-color: transparent" in hover
    assert "background: var(--surface-selected)" in hover


def test_product_resource_links_have_fixed_official_targets_and_safe_new_tabs():
    html = _static("index.html")
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
    html = _static("index.html")
    markup = _MarkupTags(html)
    javascript = _static("app.js")
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
    css = _static("styles.css")
    assert "display: none" in _block(css, ".auth-header .header-resources")
    assert "display: flex" in _block(css, ".auth-header .resources-control")
    # The workspace header shows inline links on wide screens and folds them into the menu below 1180px.
    assert "display: none" in _block(css, ".resources-control")
    narrow = css.split("@media (max-width: 1180px)", 1)[1].split("@media", 1)[0]
    assert ".app-header .header-resources" in narrow and ".app-header .resources-control" in narrow


def test_project_context_and_options_use_horizontal_flexible_rows():
    css = _static("styles.css")
    for selector in (".project-picker-copy", ".project-picker-option"):
        block = _block(css, selector)
        assert "display: flex" in block
        assert "align-items: center" in block
    assert "min-width: 0" in _block(css, ".project-picker-trigger")
    label = _block(css, ".project-picker-label")
    assert "min-width: 0" in label and "text-overflow: ellipsis" in label
    name = _block(css, ".project-picker-option-name")
    assert "min-width: 0" in name
    assert "text-overflow: ellipsis" in name
    assert "white-space: nowrap" in name
    description = _block(css, ".project-picker-option-repo")
    assert "flex: 0 0 auto" in description
    assert "white-space: nowrap" in description


def test_workspace_is_one_fluid_page_with_tabs_instead_of_three_fixed_panes():
    html = _static("index.html")
    css = _static("styles.css")
    markup = _MarkupTags(html)
    for retired in ('id="sidebar"', 'class="primary-nav"', 'id="back-btn"', 'id="nav-health"', "Continuation queue"):
        assert retired not in html
    tabs = [attributes["data-tab"] for _, attributes, _ in markup.tags if "data-tab" in attributes]
    assert tabs == ["overview", "intents", "flow", "snaps", "history", "decisions", "settings"]
    tab_bar = markup.by_id("tab-bar")
    assert tab_bar[0] == "nav" and tab_bar[1].get("aria-label")
    content = _block(css, ".page-content")
    assert "width: 100%" in content and "margin: 0 auto" in content
    assert "max-width: calc(var(--page-max) + 2 * var(--gutter))" in content
    assert re.search(r"--page-max:\s*1200px", css)
    # A fluid canvas should not turn paragraphs into unbounded reading lines.
    assert "max-width: 74ch" in _block(css, ".detail-section p")
    assert "max-width: 82ch" in _block(css, ".brief-why")
    # Narrow screens give the project its own row instead of compressing the brand.
    mobile = css.split("@media (max-width: 720px)", 1)[1]
    assert 'grid-template-areas: "brand actions" "project project"' in mobile
    assert "display: contents" in _block(mobile, ".header-context")


def test_navigation_loading_does_not_insert_spinners_into_card_layout():
    javascript = _static("app.js")
    css = _static("styles.css")
    for target in ('card', 'tabButton', 'el.projectPickerTrigger'):
        assert f'setButtonBusy({target},' not in javascript
    assert 'view-loading' in javascript and 'view-loading' in css
    assert '.is-busy::before' not in css
    assert '.action-busy' in css
    guard = javascript.split("function setButtonBusy", 1)[1].split("\n", 2)[1]
    for navigation in (".list-row", ".timeline-entry", ".relation-item", ".search-result", ".tab", ".project-picker-trigger"):
        assert navigation in guard


def test_hue_is_reserved_for_status_tokens_and_tenon_mark_keeps_its_color():
    css = _static("styles.css")
    declarations = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", css))
    colored_tokens = set()
    for line in css.splitlines():
        match = re.match(r"\s*(--[\w-]+):\s*([^;]+);", line)
        colors = re.findall(r"#([0-9a-fA-F]{3,8})(?![\w-])", line)
        channels = re.findall(r"rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)", line)
        if not colors and not channels:
            continue
        for color in colors:
            assert len(color) in (3, 4, 6, 8), color
        chromatic = any(not _is_neutral(color) for color in colors) or any(len(set(rgb)) != 1 for rgb in channels)
        if chromatic:
            assert match and STATUS_TOKEN.match(match.group(1)), line.strip()
            colored_tokens.add(match.group(1))
    assert colored_tokens == {f"--{hue}{suffix}" for hue in ("blue", "green", "amber", "red") for suffix in ("", "-soft", "-line", "-dot")}
    assert declarations and 'fill="#f06b32"' in _static("tenon-mark.svg")
    # Status is never conveyed by color alone: every status pill carries its label text.
    javascript = _static("app.js")
    assert '<span class="status-dot" aria-hidden="true"></span>${esc(label)}</span>' in javascript
    assert '<span class="status-dot" aria-hidden="true"></span>${esc(status.label)}</span>' in javascript


def test_primary_theme_text_and_status_color_pairs_have_readable_contrast():
    css = _static("styles.css")

    def luminance(color):
        channels = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(v * weight for v, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

    pairs = (
        ("ink", "canvas"), ("ink", "surface"), ("ink-2", "surface"), ("muted", "surface"),
        ("muted", "canvas"), ("muted", "surface-subtle"), ("primary-ink", "primary-bg"),
        ("green", "green-soft"), ("amber", "amber-soft"), ("red", "red-soft"), ("blue", "blue-soft"),
    )
    for selector in (":root", ':root[data-theme="dark"]'):
        block = re.search(re.escape(selector) + r'\s*\{([^}]+)', css).group(1)
        tokens = dict(re.findall(r'--([\w-]+):\s*(#[0-9a-fA-F]{6})\s*;', block))
        for foreground, background in pairs:
            low, high = sorted((luminance(tokens[foreground]), luminance(tokens[background])))
            assert (high + 0.05) / (low + 0.05) >= 4.5, (selector, foreground, background)


def test_theme_and_local_font_cover_all_entry_pages_without_external_loading():
    for name in ("index.html", "auth-redirect.html"):
        html = _static(name)
        assert 'content="light dark"' in html
        assert re.search(r'src="/theme\.js\?rev=[\w.-]+"', html)
        assert html.index('/theme.js?') < html.index('/styles.css?')
        assert 'data-theme-switch' in html or 'data-theme-setting' in html
        assert 'href="/InterVariable.woff2"' in html
    css = _static("styles.css")
    assert '@font-face' in css and 'font-display: swap' in css
    assert 'url("/InterVariable.woff2")' in css
    assert '[data-theme="dark"]' in css
    assert '0 12px 32px #00000066, 0 2px 6px #00000033' in css
    assert 'https://' not in css
    menu = _block(css, ".timeline-filter-menu")
    assert 'position: absolute' in menu and 'dvh' in menu and 'overflow-y: auto' in menu
    assert 'SIL OPEN FONT LICENSE Version 1.1' in _static('Inter-LICENSE.txt')
    assert "prefers-reduced-motion: reduce" in css


def test_static_assets_carry_one_current_cache_revision():
    for name in ("index.html", "auth-redirect.html"):
        html = _static(name)
        references = re.findall(r'(?:src|href)="/([\w.-]+\.(?:js|css))(\?rev=[\w.-]+)?"', html)
        assert references
        for asset, revision in references:
            assert revision, (name, asset)
    # One revision per release for every asset that changes together.
    index = _static("index.html")
    revisions = set(re.findall(r'/(?:app|i18n|help|styles|theme)\.(?:js|css)\?rev=([\w.-]+)"', index))
    assert len(revisions) == 1
    redirect = _static("auth-redirect.html")
    assert set(re.findall(r'/(?:i18n|styles|theme)\.(?:js|css)\?rev=([\w.-]+)"', redirect)) == revisions


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js unavailable for frontend logic tests")
def test_bilingual_rendering_preserves_user_content_and_immediate_loading():
    # The web client derives relation states itself; hand it the CLI's answers for every status pair.
    statuses = ("active", "suspend", "done", "cancelled", None)
    parity = [[kind, subject, target, relations.state(kind, {"status": subject}, {"status": target})]
              for kind in relations.RELATION_TYPES for subject in statuses for target in statuses]
    env = {**os.environ, "INTHUB_RELATION_STATES": json.dumps(parity)}
    for script in ("inthub_web_logic.cjs", "inthub_theme_logic.cjs"):
        result = subprocess.run(["node", str(Path(__file__).with_name(script))], capture_output=True, text=True, env=env)
        assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"


def test_updated_standard_uses_fixed_redirect_help_and_shared_dialog_layout():
    html = _static("index.html")
    javascript = _static("app.js")
    css = _static("styles.css")
    redirect = _static("auth-redirect.js")
    help_script = _static("help.js")
    assert 'href="/auth/redirect?method=github"' in html
    assert 'class="heading-with-help"' in html
    assert 'data-help="auth"' in html and 'data-help="search"' in html
    assert 'help: "decisions"' in javascript and 'help: "setup"' in javascript
    # Help buttons sit beside headings so they never become part of the heading's name.
    markup = _MarkupTags(html)
    for heading in ("auth-title", "search-dialog-title"):
        assert not [tag for tag, attributes in markup.within(heading) if tag == "button"], heading
    assert '${help ? `<div class="heading-with-help">${heading}${helpButton(help)}</div>` : heading}' in javascript
    assert 'gap: max(6px, 0.28em)' in _block(css, ".heading-with-help")
    popover = _block(css, ".help-popover")
    assert 'border-radius: 12px' in popover and 'box-shadow: var(--help-shadow)' in popover
    assert '0 12px 32px #00000016, 0 2px 6px #00000008' in css
    assert 'panel.showPopover()' in help_script and 'aria-describedby' in help_script
    assert 'rect.bottom < top + 16' in help_script
    assert 'Math.min(preferredTop, top + height - panel.offsetHeight - 16)' in help_script
    assert '--dialog-width:' in css and '--dialog-height:' in css
    about = _rule(css, ".about-dialog")
    assert "width: var(--dialog-width)" in about and "height: var(--dialog-height)" in about
    assert 'grid-template-rows: auto minmax(0, 1fr) auto' in _block(css, ".dialog-layout")
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


def test_web_shell_opens_on_the_continuation_brief_with_search_palette():
    html = _static("index.html")
    javascript = _static("app.js")
    markup = _MarkupTags(html)
    assert 'data-active-tab="overview"' in html
    assert 'id="search-trigger"' in html and 'aria-haspopup="dialog"' in html
    dialog = markup.by_id("search-dialog")
    assert dialog[0] == "dialog" and dialog[1].get("aria-labelledby") == "search-dialog-title"
    search_input = markup.by_id("search-input")[1]
    assert search_input.get("role") == "combobox" and search_input.get("aria-controls") == "search-results"
    assert markup.by_id("search-results")[1].get("role") == "listbox"
    assert "private archive" not in html
    assert 'aria-activedescendant' in javascript
    assert 'if (event.isComposing || event.keyCode === 229) return;' in javascript
    assert 'event.key === "/" && !typing' in javascript
    assert '(event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k"' in javascript
    assert 'requestedTab === "search" || Boolean(q)' in javascript


def test_web_client_loads_handoff_and_surfaces_checkpoint_contract():
    javascript = _static("app.js")
    assert "/handoff" in javascript
    assert "function parseCheckpoint" in javascript
    labels = javascript.split("function checkpointGrid", 1)[1].split("}", 1)[0]
    for key, label in (("verified", "Verified"), ("boundary", "Boundary"), ("next", "Next"), ("blocker", "Blocker")):
        assert f'{key}: t("{label}")' in labels
    assert 'order = ["next", "blocker", "boundary", "verified"]' in javascript
    assert "event.metaKey || event.ctrlKey" in javascript


def test_web_checkpoint_keys_match_the_stored_snap_contract():
    javascript = _static("app.js")
    keys = re.search(r"const CHECKPOINT_KEYS = \[([^\]]*)\];", javascript).group(1)
    assert tuple(re.findall(r'"(\w+)"', keys)) == store.CHECKPOINT_FIELDS
    # Display and continuation health must read one checkpoint source.
    for function in ("parseCheckpoint", "continuationHealth", "conciseSnapTitle"):
        body = javascript.split(f"function {function}(", 1)[1].split("\n}\n", 1)[0]
        assert "snapCheckpointParts(" in body
        assert "extractCheckpointParts(" not in body


def test_detail_sheet_is_a_modal_dialog_with_back_stack_and_history():
    html = _static("index.html")
    javascript = _static("app.js")
    css = _static("styles.css")
    markup = _MarkupTags(html)
    sheet = markup.by_id("drawer")[1]
    assert sheet.get("role") == "dialog" and sheet.get("aria-modal") == "true"
    assert sheet.get("aria-labelledby") == "drawer-title" and "inert" in sheet
    assert {"drawer-back", "drawer-close", "drawer-title", "drawer-content"}.issubset({attributes.get("id") for _, attributes in markup.within("drawer")})
    assert "async function sheetBack()" in javascript
    assert 'mode === "push" && wasOpen' in javascript
    assert "state._sheetPushed && window.history.state?.inthub === \"sheet\"" in javascript
    assert 'window.addEventListener("popstate", () => applyRoute(readRoute()))' in javascript
    assert 'if (event.key === "Escape") { event.preventDefault(); closeDrawer(); return; }' in javascript
    assert "width: min(700px, calc(100vw - 16px))" in _block(css, ".sheet")
    assert "transform: none" in _block(css, ".sheet.open")


def test_web_shell_uses_soft_cards_without_console_style_color_rails():
    javascript = _static("app.js")
    stylesheet = _static("styles.css")
    assert "--shadow-card:" in stylesheet
    assert ".checkpoint-blocker.is-clear" in stylesheet
    assert ".checkpoint-blocker.is-blocked" in stylesheet
    assert 'clearBlocker ? " is-clear"' in javascript
    assert "box-shadow: inset 3px 0 0" not in stylesheet
    assert "box-shadow: inset 0 -2px 0" not in stylesheet
    # Checkpoint cells share hairlines inside one card rather than nesting cards.
    grid = _block(stylesheet, ".checkpoint-grid")
    assert "gap: 1px" in grid and "background: var(--border)" in grid
    assert "border-radius" not in _block(stylesheet, ".checkpoint")


def test_continuation_brief_does_not_repeat_snap_context_footer():
    javascript = _static("app.js")
    stylesheet = _static("styles.css")
    assert "brief-context" not in javascript
    assert "brief-context" not in stylesheet
    assert "Checkpoint constraint:" not in javascript
    assert '<strong>${esc(t("Constraints:"))}</strong>' in javascript


def test_overview_offers_a_copyable_markdown_brief():
    javascript = _static("app.js")
    assert "data-copy-brief" in javascript
    assert "function briefMarkdown()" in javascript
    assert 'copyText(briefMarkdown(), t("Brief copied."))' in javascript


def test_first_run_guide_matches_the_documented_install_and_signs_in_through_the_browser():
    javascript = _static("app.js")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    install = re.search(r'const INSTALL_COMMAND = "([^"]+)";', javascript).group(1)
    assert install in readme
    guide = javascript.split("function renderSetupGuide", 1)[1].split("/* ---- Project selector", 1)[0]
    assert '"itt init"' in guide and '"itt push"' in guide
    assert "itt auth login --api-base-url" in guide and "approve it in the browser" in guide
    assert 'data-copy="${esc(text)}"' in javascript.split("function commandSnippet", 1)[1].split("function detailSection", 1)[0]
    # The Skill step matches the README and never installs for every agent: --all creates about 50 agent folders in ~.
    skill = re.search(r'const SKILL_COMMAND = "([^"]+)";', javascript).group(1)
    assert skill in readme and "--all" not in skill and "cmd: [SKILL_COMMAND]" in guide
    assert guide.index("cmd: [INSTALL_COMMAND]") < guide.index("cmd: [SKILL_COMMAND]") < guide.index('cmd: ["itt init"]')
    # On the CLI's default endpoint login needs no URL and a push alone creates the project.
    hosted = re.search(r'const HOSTED_INTHUB = "([^"]+)";', javascript).group(1)
    credentials = (ROOT / "src" / "intent_cli" / "hub" / "credentials.py").read_text(encoding="utf-8")
    assert f'OFFICIAL_INTHUB_API_BASE_URL = "{hosted}"' in credentials
    assert 'hosted ? "itt auth login"' in guide and 'optional: { desc: t("Optional: to use a different project name, link it first."), cmd: [linkCmd] }' in guide
    assert "Resume this project through Intent." in readme and "setup-resume" in guide


def _rules(css):
    """Innermost rule blocks as (selector, body), with comments and media query wrappers dropped."""
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return [(" ".join(selector.split()), body) for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def _rule(css, selector):
    bodies = [body for name, body in _rules(css) if name == selector]
    assert len(bodies) == 1, (selector, len(bodies))
    return bodies[0]


def test_snippet_copy_button_is_placed_against_the_pre():
    css = _static("styles.css")
    snippet = _static("app.js").split("function commandSnippet", 1)[1].split("function detailSection", 1)[0]
    # Markup: the button is the pre's sibling inside the wrapper it is positioned against, and copies the plain text.
    assert '<div class="snippet"><pre class="command-snippet">${shown}</pre><button class="icon-button copy-button"' in snippet
    assert 'data-copy="${esc(text)}"' in snippet and '<span class="command-word">${word}</span>' in snippet
    assert "display: inline-block" in _rule(css, ".command-word") and "max-width: 100%" in _rule(css, ".command-word")
    # The wrapper's box is the pre's box: no padding or border on it, and no margin on the pre anywhere
    # (an empty state once pushed the pre 8px down and the button straddled its top border).
    wrapper = _rule(css, ".snippet")
    assert "position: relative" in wrapper and not re.search(r"(?<![-\w])(padding|border)[\w-]*\s*:", wrapper)
    for selector, body in _rules(css):
        if ".command-snippet" in selector:
            assert all(value.strip() == "0" for value in re.findall(r"(?<![-\w])margin[\w-]*\s*:\s*([^;]+);", body)), selector
    assert "margin-top: 16px" in _rule(css, ".empty-state .snippet")
    # Centred on the first line, so a one-line snippet has the button in its middle.
    pre = _rule(css, ".command-snippet")
    assert "padding: var(--snippet-pad) 48px var(--snippet-pad) 14px" in pre and "line-height: var(--snippet-line)" in pre
    button = _rule(css, ".snippet > .copy-button")
    assert "top: calc(1px + var(--snippet-pad) + (var(--snippet-line) - 30px) / 2)" in button and "height: 30px" in button
    pad = float(re.search(r"--snippet-pad:\s*([\d.]+)px", wrapper).group(1))
    line = float(re.search(r"--snippet-line:\s*([\d.]+)px", wrapper).group(1))
    assert 1 + pad + (line - 30) / 2 + 15 == (2 * (1 + pad) + line) / 2


def test_text_columns_shrink_instead_of_pushing_text_out_of_their_box():
    css = _static("styles.css")
    # An implicit grid column grows to its widest nowrap line: Decision rows ran 110px past their card and
    # the filter menus scrolled sideways instead of ending long Intent titles in an ellipsis.
    for selector in (".row-main", ".timeline-filter-menu"):
        assert "grid-template-columns: minmax(0, 1fr)" in _rule(css, selector), selector
    # Once the title can shrink, the count or Intent ID beside it must not (it broke into "intent-" / "007").
    side = _rule(css, ".timeline-filter-option small")
    assert "flex: none" in side and "white-space: nowrap" in side


def test_filter_menus_hang_from_the_page_header_and_stay_on_the_page():
    css = _static("styles.css")
    assert any("position: relative" in body for selector, body in _rules(css) if selector == ".page-header")
    assert "position: static" in _rule(css, ".page-header .timeline-filter")
    # One rule only: no phone override pinning the menu to its trigger's left edge (it ran 233px off a 390px screen).
    menu = _rule(css, ".timeline-filter-menu")
    assert "right: 0" in menu and "width: min(380px, 100%)" in menu


def test_small_surfaces_size_to_their_content():
    css = _static("styles.css")
    # left: 50% caps a toast's shrink-to-fit width at half the viewport, so short messages wrapped on phones.
    assert "width: max-content" in _rule(css, ".status-toast")
    # With nothing listed, the search message sits under the field instead of at the foot of the phone panel.
    assert "display: none" in _rule(css, ".search-results:not(:has(*))")


def test_text_fields_share_a_soft_focus_ring_instead_of_the_hard_outline():
    css = _static("styles.css")
    html = _static("index.html")
    javascript = _static("app.js")
    field = _rule(css, ".text-field")
    assert "border: 1px solid var(--border-strong)" in field
    focus = _rule(css, ".text-field:focus, .text-field:focus-visible")
    assert "outline: none" in focus and "box-shadow: 0 0 0 3px var(--field-ring)" in focus
    # Every text field but the search palette's borderless one uses the shared style; a select's trigger does too.
    fields = re.findall(r"<(?:input|textarea)\b[^>]*>", html + javascript)
    assert len(fields) >= 5
    for tag in fields:
        if 'id="search-input"' not in tag and 'type="hidden"' not in tag:
            assert 'class="text-field' in tag, tag
    assert 'class="text-field select-trigger"' in javascript


def test_no_control_falls_back_to_the_browsers_own_look():
    javascript = _static("app.js")
    html = _static("index.html")
    css = _static("styles.css")
    # Selects are listboxes of our own, in the top layer so a dialog or a scrolling pane cannot clip them.
    assert "<select" not in html + javascript and "<option" not in html + javascript
    assert 'role="listbox" popover="manual"' in javascript and "position: fixed" in _rule(css, ".select-menu")
    assert "aria-selected" in javascript and all(key in javascript for key in ("ArrowDown", "Home:", "End:"))
    # Hints use the page's popover, not the browser's title tooltip. The form's own title attributes stay out too.
    assert not re.search(r'<[a-z][^>]*\stitle="', html + javascript)
    assert ".title =" not in javascript.replace("document.title =", "")
    assert "data-tip" in javascript and 'data-tip]' in _static("help.js")
    assert not re.search(r"\b(alert|confirm|prompt)\(", javascript.replace("window.confirm", ""))
    for kind in ("checkbox", "radio", "date", "number", "range", "file", "color"):
        assert f'type="{kind}"' not in html + javascript


def test_settings_open_in_one_fixed_size_dialog_over_the_page():
    css = _static("styles.css")
    html = _static("index.html")
    javascript = _static("app.js")
    frame = _rule(css.split("@media (max-width: 1180px)", 1)[0], ".settings-dialog")
    assert "width: min(920px, calc(100vw - 32px))" in frame and "height: min(640px, calc(100dvh - 32px))" in frame
    # The pane scrolls, never the frame: its height does not follow what it holds.
    desktop = css.split("@media (max-width: 1180px)", 1)[0]
    assert "overflow: hidden" in frame and "overflow-y: auto" in _rule(desktop, ".settings-dialog .settings-pane")
    assert "scrollbar-gutter: stable" in _rule(desktop, ".settings-dialog .settings-pane")
    phone = css.split("@media (max-width: 720px)", 1)[1].split("@media (hover: none)", 1)[0]
    assert "width: 100vw" in _block(phone, ".settings-dialog") and "height: 100dvh" in _block(phone, ".settings-dialog")
    assert 'id="settings-dialog" aria-labelledby="settings-dialog-title"' in html
    assert html.index('id="settings-dialog"') < html.index('id="confirm-dialog"'), "a confirmation stacks on top"
    # Toasts follow the top dialog: the page behind it is inert and under the backdrop.
    assert 'querySelectorAll("dialog[open]")' in javascript.split("function placeStatusLine", 1)[1]


def test_site_pages_have_their_own_routes_without_project_chrome():
    html = _static("index.html")
    css = _static("styles.css")
    javascript = _static("app.js")
    assert 'const ACCOUNT_PATHS = { profile: "/account", danger: "/account/danger" };' in javascript
    assert 'const SETTINGS_PATHS = { tokens: "/settings", teams: "/settings/teams" };' in javascript
    assert "accountContent" not in javascript and "is-account" not in javascript + css
    assert '<div class="page-content is-hidden" id="site-content" tabindex="-1"></div>' in html
    # Home, account, team and invite pages hide what belongs to a project, search included.
    hidden = _rule(css, ".shell.is-site .tab-bar, .shell.is-site .sync-indicator, .shell.is-site .command-trigger")
    assert "display: none" in hidden
    # The server answers these paths with the app, so only the client knows them; every link stays a real link.
    assert 'a[data-route]' in javascript and "event.metaKey || event.ctrlKey || event.shiftKey || event.altKey" in javascript
    # The profile is read-only and edited in Tenon; Delete account keeps its Tenon flow on this page.
    assert 'const TENON_ACCOUNT_URL = "https://account.tenon.asia/account/";' in javascript and 'href="${TENON_ACCOUNT_URL}"' in javascript
    assert "data-delete-account" in javascript and '"/api/auth/tenon/delete/start"' in javascript
    # Tokens: 30, 90 or 365 days (90 by default), active ones only, a new secret once and inline.
    assert "const TOKEN_LIFETIMES = [30, 90, 365];" in javascript and "const DEFAULT_TOKEN_DAYS = 90;" in javascript
    assert "!token.revoked_at" in javascript
    leaving = javascript.split("function setPage", 1)[1].split("\n}\n", 1)[0]
    assert "forgetShownSecrets();" in leaving and 'el.siteContent.innerHTML = "";' in leaving


def test_settings_share_one_layout_with_one_pair_of_edges():
    full = _static("styles.css")
    css = full.split("@media (max-width: 1180px)", 1)[0]
    javascript = _static("app.js")
    layout = _rule(css, ".settings-layout")
    assert "grid-template-columns: 200px minmax(0, 720px)" in layout and "justify-content: center" in layout
    # Account, a team and the project tab all go through the same helper.
    assert javascript.count("= settingsLayout({") == 3
    # Nothing inside a pane adds side padding or a narrower measure: the two edges are the pane's.
    for selector in (".settings-pane", ".settings-block-title", ".settings-lead", ".settings-list", ".settings-row", ".settings-form"):
        body = _rule(css, selector)
        assert "max-width" not in body and "padding-left" not in body and "padding-right" not in body and "border-left" not in body, selector
    assert "padding: 14px 0" in _rule(css, ".settings-row")
    assert "border-block: 1px solid var(--border)" in _rule(css, ".settings-list")
    assert "align-items: center" in _rule(css, ".settings-row")
    # No nested cards: a pane has no surface of its own.
    for selector in (".settings-pane", ".settings-list", ".settings-row"):
        assert "background" not in _rule(css, selector) and "box-shadow" not in _rule(css, selector), selector
    # The active link is a neutral fill, never a bar.
    active = _rule(css, '.settings-nav-item[aria-current="page"]')
    assert "background: var(--surface-selected)" in active and "border" not in active
    mobile = full.split("@media (max-width: 720px)", 1)[1].split("@media (hover: none)", 1)[0]
    assert "overflow-x: auto" in _block(mobile, ".settings-nav") and "grid-template-columns: minmax(0, 1fr)" in _block(mobile, ".settings-layout")
    assert ".settings-card" not in css and ".settings-page" not in css and ".profile-card" not in css and ".token-row" not in css


def test_visitors_read_public_projects_without_account_requests():
    javascript = _static("app.js")
    # The sign-in gate is the answer to a 401 everywhere but the probes that ask whether one is needed.
    assert "async function fetchJson(url, { gate = true, ...options } = {})" in javascript
    assert 'if (r.status === 401 && gate && state.config?.authRequired) showAuthGate();' in javascript
    assert 'await fetchJson(apiUrl("/api/v1/auth/me"), { gate: false })' in javascript
    assert "/overview`), { gate: false })" in javascript
    visitor = javascript.split("async function openAsVisitor", 1)[1].split("\n}\n", 1)[0]
    assert "/api/v1/projects\"" not in visitor and "loadProjects" not in visitor and "/api/v1/auth/tokens" not in visitor
    # Picking and managing need an account.
    assert "el.projectPickerTrigger.disabled = Boolean(state._projectBusy) || state.visitor;" in javascript
    assert 'return state.overview?.project?.permission === "admin";' in javascript
    assert 'if (state.activeTab === "settings" && !canManageProject())' in javascript
    assert 'data-tab="settings"' in _static("index.html") and '<button class="tab is-hidden" data-tab="settings"' in _static("index.html")


def test_project_settings_stay_neutral_and_delete_only_after_the_exact_name():
    css = _static("styles.css")
    javascript = _static("app.js")
    # No coloured cards or stripes: only the destructive button uses the danger colour.
    neutral = (".settings-nav-item", ".settings-row", ".settings-list", ".secret-box", ".monogram", ".home-row .row-meta", ".invite-card", ".confirm-dialog")
    bodies = [(name, body) for name, body in _rules(css) if name in neutral]
    assert {name for name, _ in bodies} == set(neutral)
    for name, body in bodies:
        assert not re.search(r"--(red|amber|green|blue)", body) and "border-left" not in body, name
    assert "color: var(--red)" in _rule(css, ".button-danger")
    assert "el.confirmOk.disabled = el.confirmInput.value !== state._confirm.expect;" in javascript
    assert "body: JSON.stringify({ confirm })" in javascript
    assert "const PROJECT_NAME_MAX = 120;" in javascript
    assert '`${safe || "project"}.inthub-export.json`' in javascript and "JSON.stringify(data, null, 2)" in javascript


def test_history_tab_follows_the_timeline_and_opens_revisions_in_the_sheet():
    html = _static("index.html")
    javascript = _static("app.js")
    css = _static("styles.css")
    assert html.index('data-tab="snaps"') < html.index('data-tab="history"') < html.index('data-tab="decisions"')
    assert 'revision: "revisions"' in re.search(r"const DETAIL_PATHS = \{[^}]+\}", javascript).group(0)
    size = int(re.search(r"const REVISION_PAGE_SIZE = (\d+);", javascript).group(1))
    assert size <= REVISION_PAGE_MAX
    assert 'if (type === "revision") return buildRevisionDetailHtml(payload);' in javascript
    # The row keeps its two columns on phones, where .list-row has an icon column and no third one.
    assert "grid-template-columns: minmax(0, 1fr) auto" in _rule(css, ".list-row.history-row")
    assert "/api/v1/projects/${encodeURIComponent(projectIdFromRemoteId(rId))}/revisions/${encodeURIComponent(revision)}" in javascript
    assert "t(\"{count} more not shown\"" in javascript


def test_identity_shows_as_a_quiet_line_and_verified_as_a_dot_and_text_pill():
    javascript = _static("app.js")
    css = _static("styles.css")
    help_copy = _static("help.js")
    assert "originBadge" not in javascript
    assert '<span class="status-dot" aria-hidden="true"></span>${esc(t("Verified"))}</span>' in javascript
    assert "background: var(--green-dot)" in _rule(css, ".status-verified .status-dot")
    assert 'verified: "Pushed by the account that owns this email."' in help_copy
    byline = _rule(css, ".row-byline")
    assert "color: var(--muted)" in byline and not re.search(r"--(red|amber|green|blue)", byline)
    # Every row that names an object says who recorded it.
    for name in ("snapTimelineEntry", "intentEntry", "pausedRow", "decisionConstraint", "decisionRows"):
        assert "rowByline(" in javascript.split(f"function {name}(", 1)[1].split("\n}\n", 1)[0], name
    for name in ("buildIntentDetailHtml", "buildDecisionDetailHtml", "buildSnapDetailHtml"):
        assert "identityMeta(" in javascript.split(f"function {name}(", 1)[1].split("\n}\n", 1)[0], name


def test_commit_links_use_the_clis_hosts_and_open_safely():
    javascript = _static("app.js")
    url = javascript.split("function commitUrl(", 1)[1].split("\n}\n", 1)[0]
    for host in identity.REPOSITORY_HOSTS.split("|"):
        assert f'"{host.replace(chr(92), "")}"' in url
    assert 'target="_blank" rel="noopener noreferrer"' in javascript.split("function commitLine(", 1)[1].split("\n}\n", 1)[0]


def test_web_shell_uses_monochrome_continuity_logo_and_explicit_account_icon():
    html = _static("index.html")
    javascript = _static("app.js")
    stylesheet = _static("styles.css")

    assert html.count('class="brand-mark"') == 3
    assert html.count('src="/inthub-mark.svg?rev=3"') == 4
    assert 'class="auth-mark brand-mark"' in html
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
    javascript = _static("app.js")
    stylesheet = _static("styles.css")

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
    assert 'status.key === "blocked" ? stateBadge(status) : ""' in javascript


def test_intents_are_grouped_by_lifecycle_with_collapsed_history():
    javascript = _static("app.js")
    stylesheet = _static("styles.css")

    assert 'other.filter((intent) => intent.status === "suspend")' in javascript
    assert 'other.filter((intent) => intent.status === "done")' in javascript
    assert 'other.filter((intent) => intent.status === "cancelled")' in javascript
    assert 'class="object-archive intent-archive"' in javascript
    assert "Active objectives" in javascript
    assert "Resolved history" in javascript
    assert ".list-row" in stylesheet
    assert ".object-archive" in stylesheet


def test_decisions_surface_current_constraints_scope_and_deprecated_history():
    javascript = _static("app.js")
    stylesheet = _static("styles.css")

    assert "function decisionScope" in javascript
    assert "function decisionConstraint" in javascript
    assert "Active constraints" in javascript
    assert "No Intent scope recorded" in javascript
    assert "Deprecated history" in javascript
    assert "Current cross-Intent constraint" in javascript
    assert 'statusBadge(decision.status, "decision")' in javascript
    assert ".decision-row" in stylesheet
    assert ".decision-scope" in stylesheet


def test_login_page_matches_the_continuity_workspace_and_keeps_one_auth_path():
    html = _static("index.html")
    javascript = _static("app.js")
    stylesheet = _static("styles.css")

    auth = html.split('id="auth-gate"', 1)[1].split('<dialog class="search-dialog"', 1)[0]
    assert 'class="auth-introduction"' in auth
    assert '<div class="heading-with-help"><h1 id="auth-title">Sign in to IntHub</h1>' in auth
    assert "Continue with your project context intact." in auth
    assert 'id="auth-preferences-menu-trigger"' in auth
    assert 'data-theme-setting' in auth and 'data-language-select' in auth
    assert 'data-about-open' in auth
    assert 'class="brand brand-on-auth"' in auth
    assert html.count('id="tenon-login"') == 1
    for method in ("github", "apple", "email"):
        assert f'data-login-method="{method}" href="/auth/redirect?method={method}"' in auth
    assert 'data-login-label aria-live="polite"' in auth
    assert "creates a Tenon Account" in auth
    assert 'class="tenon-login-spinner"' in auth
    assert 'id="auth-error" role="alert"' in auth
    assert 'data-help="auth"' in auth
    assert '<form' not in auth and '<input' not in auth
    assert "auth-trajectory" not in auth + stylesheet
    assert "auth-preview" not in auth + stylesheet
    assert "auth-assurances" not in auth + stylesheet
    assert "No repository access is requested" in _static("help.js")
    assert '.auth-stage {' in stylesheet and 'width: min(400px, 100%)' in _block(stylesheet, ".auth-panel")
    assert 'align-items: safe center' in stylesheet
    assert 'width: 100%' in _block(stylesheet, ".tenon-login")
    assert '.tenon-login.is-loading .tenon-login-spinner' in stylesheet
    assert 'setTenonLoginLoading(link.dataset.loginMethod)' in javascript
    translations = _static("i18n.js")
    assert '"Sign in to IntHub": "登录 IntHub"' in translations
    assert '"Continue with your project context intact.": "保留项目上下文，继续工作。"' in translations


def test_tenon_login_has_immediate_loading_feedback_and_recovers_from_history():
    html = _static("index.html")
    javascript = _static("app.js")
    stylesheet = _static("styles.css")

    assert 'class="tenon-login-spinner"' in html
    assert 'aria-live="polite"' in html
    assert "function setTenonLoginLoading" in javascript
    assert 'setAttribute("aria-busy", String(loading))' in javascript
    assert 'url.searchParams.set("tenon_method", method)' in _static("auth-redirect.js")
    assert 'window.addEventListener("pageshow"' in javascript
    assert 'event.preventDefault()' in javascript
    assert ".tenon-login.is-loading" in stylesheet
    assert "animation: spin 700ms linear infinite" in stylesheet


def test_product_brand_and_about_follow_tenon_standard():
    html = _static("index.html")
    javascript = _static("app.js")
    stylesheet = _static("styles.css")
    mark = _static("tenon-mark.svg")

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
    assert 'if (el.aboutDialog.open || el.searchDialog.open || el.confirmDialog.open || el.settingsDialog.open) return' in javascript
    assert 'fill="#f06b32"' in mark
    assert 'M13 16H51V28H38V48H26V28H13Z' in mark


def test_flow_relations_mirror_the_cli_rules():
    javascript = _static("app.js")
    types = re.search(r"const RELATION_TYPES = \[([^\]]*)\];", javascript).group(1)
    assert tuple(re.findall(r'"(\w+)"', types)) == relations.RELATION_TYPES
    parents = re.search(r"const PARENT_RELATIONS = new Set\(\[([^\]]*)\]\);", javascript).group(1)
    assert set(re.findall(r'"(\w+)"', parents)) == relations.PARENT_TYPES
    attention = re.search(r"const ATTENTION_STATES = new Set\(\[([^\]]*)\]\);", javascript).group(1)
    assert set(re.findall(r'"(\w+)"', attention)) == relations.ATTENTION_STATES
    ended = re.search(r"const ENDED_STATUSES = new Set\(\[([^\]]*)\]\);", javascript).group(1)
    assert set(re.findall(r'"(\w+)"', ended)) == relations.ENDED
    # Withdrawn entries carry removed_at and never count, exactly like active_entries().
    assert '!("removed_at" in entry)' in javascript.split("function activeRelationEntries", 1)[1].split("\n}\n", 1)[0]
    # A relation state is never shown by colour alone.
    assert '<span class="status-dot" aria-hidden="true"></span>${esc(relationStateLabel(key, row))}</span>' in javascript


def test_flow_tab_is_a_keyboard_reachable_inline_svg_without_inline_styles():
    html = _static("index.html")
    javascript = _static("app.js")
    css = _static("styles.css")
    translations = _static("i18n.js")
    assert re.search(r'const TABS = \["overview", "intents", "flow", "snaps", "history", "decisions", "settings"\];', javascript)
    assert '"Flow": "流转"' in translations and '"Project": "项目"' in translations
    assert 'case "flow":' in javascript and "function flowLayout(" in javascript and "function renderFlowSvg(" in javascript
    # CSP style-src 'self': no style attributes in markup strings; SVG presentation attributes only.
    assert not re.search(r"""\sstyle=["'`$]""", javascript + html)
    assert "cdn" not in javascript.lower() and "<script" not in javascript
    node = javascript.split("function flowNodeSvg", 1)[1].split("\n}\n", 1)[0]
    assert 'role="button" tabindex="0" data-detail-type="intent"' in node and "aria-label=" in node
    for name in ("flowPinsSvg", "flowChipSvg"):
        decision = javascript.split(f"function {name}", 1)[1].split("\n}\n", 1)[0]
        assert 'role="button" tabindex="0" data-detail-type="decision"' in decision and "aria-label=" in decision
    assert 'event.key !== "Enter" && event.key !== " "' in javascript
    assert 'svg [role=button][data-detail-type][data-remote-id]' in javascript
    # The graph scrolls inside its own frame so the page never scrolls sideways.
    canvas = _block(css, ".flow-canvas")
    assert "overflow-x: auto" in canvas and "max-width: 100%" in canvas
    assert ".flow-node:focus-visible .flow-node-ring" in css
    assert 'data-help="flow"' not in html and 'help: "flow"' in javascript and "flow:" in _static("help.js")
    for command in ("--part-of ID", "relate ID --depends-on OTHER", "cancel ID --into OTHER", "--from ID"):
        assert command in javascript.split("function renderFlowTab", 1)[1].split("\n}\n", 1)[0]


def test_timeline_pages_from_the_snaps_endpoint_and_search_reports_truncation():
    javascript = _static("app.js")
    translations = _static("i18n.js")
    page_size = int(re.search(r"const SNAP_PAGE_SIZE = (\d+);", javascript).group(1))
    assert 1 <= page_size <= queries.SNAP_PAGE_MAX
    url = javascript.split("function snapPageUrl", 1)[1].split("\n}\n", 1)[0]
    assert "/snaps?" in url and 'query.set("intent_id", intentId)' in url
    timeline = javascript.split("function renderSnapsTab", 1)[1].split("\n}\n", 1)[0]
    assert "recent_snaps ||" in timeline and "renderTimeline(timeline)" in timeline and "loadTimelinePage()" in timeline
    assert "offset: timeline.snaps.length" in javascript
    # Recent activity on the overview still reads the newest Snaps from the overview itself.
    assert "activityRows((state.overview.recent_snaps || []).slice(0, 6))" in javascript
    assert "/api/v1/snaps/${encodeURIComponent(rId)}" in javascript.split("async function fetchMissingSnaps", 1)[1]
    assert '"Showing {shown} of {total} — refine the search": "显示前 {shown} 条，共 {total} 条，请细化搜索"' in translations
    assert queries.SEARCH_LIMIT == 50


def test_static_revision_names_the_current_interface():
    for name in ("index.html", "auth-redirect.html"):
        assert "rev=teams-1" not in _static(name) and "rev=history-1" not in _static(name)
        assert "rev=options-1" in _static(name)



def test_flow_draws_curves_cards_pins_and_a_quiet_time_axis():
    javascript = _static("app.js")
    css = _static("styles.css")
    translations = _static("i18n.js")
    # Bends are tangent-continuous cubics with a generous reach across a gap, clamped to half a shared leg.
    bend = re.search(r"const FLOW_BEND = \{ across: (\d+), along: (\d+), fullness: ([\d.]+) \};", javascript)
    assert 24 <= int(bend.group(1)) <= 36 and int(bend.group(2)) >= int(bend.group(1)) and 0.5 < float(bend.group(3)) < 1
    curve = javascript.split("function flowCurve(", 1)[1].split("\n}\n", 1)[0]
    assert "shared ? length / 2" in curve and "clear(" in curve
    assert "`C${" in javascript.split("function flowCurvePath", 1)[1].split("\n}\n", 1)[0]
    stroke = _block(css, ".flow-stroke")
    assert "stroke-linecap: round" in stroke and "stroke-linejoin: round" in stroke

    def width(selector):
        return float(re.search(r"stroke-width:\s*([\d.]+)", _block(css, selector)).group(1))

    # Succession strongest, structure medium, constraints thin; rejoins lighter than branches.
    assert width(".flow-flow .flow-stroke") > width(".flow-branch .flow-stroke") > width(".flow-depends .flow-stroke,\n.flow-conflict .flow-stroke")
    rejoin = _block(css, ".flow-rejoin .flow-stroke,\n.flow-lane-line")
    assert "var(--faint)" in rejoin and float(re.search(r"stroke-width:\s*([\d.]+)", rejoin).group(1)) < width(".flow-branch .flow-stroke")
    assert re.search(r"\n\.flow-conflict \.flow-stroke \{[^}]*stroke-dasharray", css)
    # Status shows only in the pill: no coloured accent bars on cards (the owner's rule); ended cards sit flat.
    assert "accent" not in javascript.split("function flowNodeSvg", 1)[1].split("\n}\n", 1)[0]
    assert ".flow-card::before" not in css and "flow-node-accent" not in css
    assert "fill: var(--blue-dot)" in _block(css, ".flow-node.status-active .flow-node-dot")
    assert "filter: none" in _block(css, ".flow-node.status-done .flow-node-box,\n.flow-node.status-cancelled .flow-node-box")
    # Up to two Decision pins under a card, then "+N more"; Project-level ones are chips in the band.
    assert re.search(r"const FLOW_PINS = 2;", javascript) and '"+{count} more": "还有 {count} 条"' in translations
    # A quiet, localized time axis.
    assert "Intl.DateTimeFormat(window.IntHubI18n.language" in javascript.split("function flowAxisLabel", 1)[1].split("\n}\n", 1)[0]
    # On a phone the frame becomes a window that scrolls both ways and opens on the card that matters.
    phone = css.split("@media (max-width: 720px)", 1)[1]
    frame = _block(phone, ".flow-canvas")
    assert "overflow: auto" in frame and "max-height: 72dvh" in frame
    assert "flowViewport(layout, canvas.clientWidth, canvas.clientHeight)" in javascript
