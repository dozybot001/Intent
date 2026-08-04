from pathlib import Path


STATIC_DIR = Path(__file__).resolve().parents[1] / "apps" / "inthub_web" / "static"


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

    assert "uiux-p2-1" in html
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

    assert html.count('class="brand-mark"') == 2
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
