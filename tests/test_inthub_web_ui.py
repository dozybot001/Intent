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

    assert "soft-cards-2" in html
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
