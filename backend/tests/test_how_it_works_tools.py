from pathlib import Path

import pytest

from app.conversation.tools import CREATE_VIDEO, TOOLS
from app.llm.client import Tool

HOW_IT_WORKS = Path(__file__).parents[2] / "docs" / "architecture" / "how-it-works.md"


@pytest.mark.parametrize("tool", [*TOOLS, CREATE_VIDEO], ids=lambda tool: tool["name"])
def test_every_orchestrator_tool_is_named_in_how_it_works(tool: Tool) -> None:
    assert f"`{tool['name']}`" in HOW_IT_WORKS.read_text(encoding="utf-8")


def test_how_it_works_no_longer_counts_two_tools() -> None:
    assert "the two tools" not in HOW_IT_WORKS.read_text(encoding="utf-8")
