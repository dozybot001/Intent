from pathlib import Path
from html.parser import HTMLParser
import json
import os
import re
import shutil
import subprocess

import pytest

from apps.inthub_api import queries
from apps.inthub_api.http_common import REVISION_PAGE_MAX
from apps.inthub_web import BUNDLES, bundle, product_version
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
    """One file, or the whole app or stylesheet as it is served: nothing here cares which part holds a rule."""
    if f"/{name}" in BUNDLES:
        return bundle(STATIC_DIR, BUNDLES[f"/{name}"][0]).decode("utf-8")
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


def test_the_app_reaches_the_browser_as_one_script_and_one_stylesheet():
    html = _static("index.html")
    assert re.findall(r'<script src="(/[\w./-]+)\?', html) == ["/theme.js", "/i18n.js", "/help.js", "/app.js"]
    assert re.findall(r'<link rel="stylesheet" href="(/[\w./-]+)\?', html) == ["/styles.css"]
    # A part missing from its order list would simply never load.
    for folder, suffix in (("js", ".js"), ("css", ".css")):
        listed = (STATIC_DIR / folder / "order.txt").read_text(encoding="utf-8").split()
        assert sorted(listed) == sorted(path.name for path in (STATIC_DIR / folder).glob(f"*{suffix}"))


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
    for script in ("web/run.cjs", "inthub_theme_logic.cjs"):
        result = subprocess.run(["node", str(Path(__file__).parent / script)], capture_output=True, text=True, env=env)
        assert result.returncode == 0, f"{script} failed:\n{result.stdout}\n{result.stderr}"


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


def test_web_checkpoint_keys_match_the_stored_snap_contract():
    javascript = _static("app.js")
    keys = re.search(r"const CHECKPOINT_KEYS = \[([^\]]*)\];", javascript).group(1)
    assert tuple(re.findall(r'"(\w+)"', keys)) == store.CHECKPOINT_FIELDS
    # Display and continuation health must read one checkpoint source.
    for function in ("parseCheckpoint", "continuationHealth", "conciseSnapTitle"):
        body = javascript.split(f"function {function}(", 1)[1].split("\n}\n", 1)[0]
        assert "snapCheckpointParts(" in body
        assert "extractCheckpointParts(" not in body


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


def test_no_control_falls_back_to_the_browsers_own_look():
    javascript = _static("app.js")
    html = _static("index.html")
    css = _static("styles.css")
    # Selects are listboxes of our own, in the top layer so a dialog or a scrolling pane cannot clip them.
    assert "<select" not in html + javascript and "<option" not in html + javascript
    assert 'role="listbox" popover="manual"' in javascript and "position: fixed" in _rule(css, ".select-menu")
    # An id equal to the name makes form.elements[name] a list, whose value reads empty.
    for identifier, name in re.findall(r'selectField\(\{ id: "([^"]+)", name: "([^"]+)"', javascript):
        assert identifier != name
    assert "aria-selected" in javascript and all(key in javascript for key in ("ArrowDown", "Home:", "End:"))
    # Hints use the page's popover, not the browser's title tooltip. The form's own title attributes stay out too.
    assert not re.search(r'<[a-z][^>]*\stitle="', html + javascript)
    assert ".title =" not in javascript.replace("document.title =", "")
    assert "data-tip" in javascript and 'data-tip]' in _static("help.js")
    assert not re.search(r"\b(alert|confirm|prompt)\(", javascript.replace("window.confirm", ""))
    for kind in ("checkbox", "radio", "date", "number", "range", "file", "color"):
        assert f'type="{kind}"' not in html + javascript


def test_visitors_see_what_this_is_and_every_page_names_its_operator():
    html = _static("index.html")
    javascript = _static("app.js")
    markup = _MarkupTags(html)
    # The sign-in page says what the product is, in the markup, and how to start.
    pitch = markup.by_id("auth-pitch")
    assert pitch[0] == "section" and "Semantic history for agent-driven development" in html
    assert 'el.authStart.innerHTML = commandSnippet([INSTALL_COMMAND, "itt init"]);' in javascript
    # Someone reading a public project who chose to sign in is not shown the pitch.
    assert 'el.authPitch.classList.toggle("is-hidden", keepPage);' in javascript
    # The operator's terms, privacy policy, contact and filing number, on the app and on the sign-in page.
    assert html.count('class="site-footer') == 2
    for target in ("https://tenon.asia/legal/terms/", "/privacy", "https://tenon.asia/legal/acceptable-use/",
                   "mailto:support@tenonai.cn", "https://beian.miit.gov.cn/"):
        assert html.count(f'href="{target}"') >= 2, target
    # Public projects can be reported; a project's managers have no need to.
    assert 'id="report-link"' in html and 'project?.visibility === "public" && !canManageProject()' in javascript
    assert 'property="og:image"' in html and (STATIC_DIR / "og.png").is_file()


def test_commit_links_use_the_clis_hosts_and_open_safely():
    javascript = _static("app.js")
    url = javascript.split("function commitUrl(", 1)[1].split("\n}\n", 1)[0]
    for host in identity.REPOSITORY_HOSTS.split("|"):
        assert f'"{host.replace(chr(92), "")}"' in url
    assert 'target="_blank" rel="noopener noreferrer"' in javascript.split("function commitLine(", 1)[1].split("\n}\n", 1)[0]


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
