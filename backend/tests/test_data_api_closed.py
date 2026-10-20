from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from tests.conftest import migration_statements, requires_db

pytestmark = requires_db

CLOSE_DATA_API = Path(__file__).parents[1] / "migrations" / "versions" / "0007_close_data_api.sql"

TABLES_WITHOUT_RLS = text(
    "select relname from pg_class where relnamespace = 'public'::regnamespace"
    " and relkind in ('r', 'p') and not relrowsecurity"
)
DATA_API_ROLE_GRANTS = text(
    "with grantees (oid) as (values ('anon'::regrole), ('authenticated'::regrole))"
    " select c.relname::text from pg_class c, aclexplode(c.relacl) a"
    " where c.relnamespace = 'public'::regnamespace and a.grantee in (select oid from grantees)"
    " union all"
    " select p.proname::text from pg_proc p, aclexplode(p.proacl) a"
    " where p.pronamespace = 'public'::regnamespace and a.grantee in (select oid from grantees)"
    " union all"
    " select 'default privileges on ' || d.defaclobjtype::text from pg_default_acl d,"
    " aclexplode(d.defaclacl) a"
    " where d.defaclnamespace = 'public'::regnamespace and a.grantee in (select oid from grantees)"
)


async def supabase_data_api_roles(db: AsyncSession) -> None:
    """The Data API roles with the grants and default privileges a Supabase project starts with."""
    await db.execute(
        text(
            "do $$ begin"
            " if to_regrole('anon') is null then create role anon nologin; end if;"
            " if to_regrole('authenticated') is null then create role authenticated nologin;"
            " end if; end $$"
        )
    )
    for kind in ("tables", "sequences", "functions"):
        await db.execute(text(f"grant all on all {kind} in schema public to anon, authenticated"))
        await db.execute(
            text(
                f"alter default privileges in schema public grant all on {kind}"
                " to anon, authenticated"
            )
        )
    # Postgres's own default, which the migration already revoked in this database when the
    # fixture ran it
    await db.execute(text("alter default privileges grant execute on functions to public"))


async def test_every_public_table_has_row_level_security(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as db:
        assert (await db.scalars(TABLES_WITHOUT_RLS)).all() == []


async def test_the_data_api_roles_lose_every_grant_on_public(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    # Roles are cluster-wide, so the session is never committed
    async with sessions() as db:
        await supabase_data_api_roles(db)
        assert (await db.scalars(DATA_API_ROLE_GRANTS)).all() != []

        for statement in migration_statements(CLOSE_DATA_API):
            await db.execute(text(statement))
        await db.execute(
            text("create table created_later (id bigint generated always as identity)")
        )
        await db.execute(text("create view created_later_view as select id from created_later"))
        await db.execute(text("create function created_later_fn() returns int return 1"))

        assert (await db.scalars(DATA_API_ROLE_GRANTS)).all() == []
        anon_runs_new_function = await db.scalar(
            text("select has_function_privilege('anon', 'created_later_fn()', 'EXECUTE')")
        )
        assert anon_runs_new_function is False
