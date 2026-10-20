import warnings
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

BACKEND = Path(__file__).parents[1]


def test_the_migrations_form_one_line_of_unique_revisions() -> None:
    with warnings.catch_warnings():
        # Alembic only warns when two files share a revision id, and then runs just one of them
        warnings.simplefilter("error", UserWarning)
        script = ScriptDirectory.from_config(Config(BACKEND / "alembic.ini"))
        revisions = list(script.walk_revisions())

    assert len(script.get_heads()) == 1
    assert len(revisions) == len(list((BACKEND / "migrations" / "versions").glob("*.py")))
