from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_production_image_declares_gitee_as_its_source():
    dockerfile = (REPOSITORY_ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert (
        'org.opencontainers.image.source="https://gitee.com/dozybot/Intent"'
        in dockerfile
    )
    assert "github.com/dozybot001/Intent" not in dockerfile
