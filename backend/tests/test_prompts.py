from pathlib import Path

import pytest

from app.conversation.turns import system_prompt
from app.prompts import load_prompt

HEADINGS = ("## Writing style", "## Making posts", "## Publishing", "## Rules")
ANCHORS = ("Vera", "vos", "create_post", "approve_post", "[post ... published]")


def test_orchestrator_prompt_is_fully_composed() -> None:
    prompt = system_prompt("Vera")
    assert "{{include" not in prompt
    assert "{" not in prompt
    assert "}" not in prompt
    for expected in (*HEADINGS, *ANCHORS):
        assert expected in prompt


def test_include_is_relative_to_the_including_file_and_nests(tmp_path: Path) -> None:
    (tmp_path / "shared").mkdir()
    (tmp_path / "shared" / "leaf.md").write_text("leaf\n")
    (tmp_path / "shared" / "mid.md").write_text("mid\n{{include leaf.md}}\n")
    root = tmp_path / "root.md"
    root.write_text("top\n\n{{include shared/mid.md}}\n\nbottom\n")
    assert load_prompt(root) == "top\n\nmid\nleaf\n\nbottom"


def test_missing_include_raises(tmp_path: Path) -> None:
    root = tmp_path / "root.md"
    root.write_text("{{include nope.md}}\n")
    with pytest.raises(FileNotFoundError):
        load_prompt(root)


def test_include_cycle_raises(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("{{include b.md}}\n")
    (tmp_path / "b.md").write_text("{{include a.md}}\n")
    with pytest.raises(ValueError, match="include cycle: a.md -> b.md -> a.md"):
        load_prompt(tmp_path / "a.md")


def test_self_include_raises(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("{{include a.md}}\n")
    with pytest.raises(ValueError, match="include cycle"):
        load_prompt(tmp_path / "a.md")


def test_video_events_and_tool_reach_the_prompt_only_with_the_flag() -> None:
    off, on = system_prompt("Vera"), system_prompt("Vera", with_video=True)

    for text in (
        "create_video",
        "video sent to the Owner",
        "[video ... failed]",
        "video_daily_limit",
    ):
        assert text not in off
        assert text in on
    assert "invalid_arguments" in on
    assert "{" not in on
    assert "}" not in on


def test_a_post_or_reel_that_arrives_gets_one_final_publish_question() -> None:
    prompt = system_prompt("Vera", with_video=True)

    assert "¿Te gusta?" not in prompt
    assert "¿Lo subo así o le cambio algo?" in prompt
    assert "¿Lo subo así como Reel o le cambio algo?" in prompt
