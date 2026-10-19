import itertools
from collections import defaultdict
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import OwnerNote
from app.knowledge.base import Note, short_id
from app.knowledge.db import business_of

MAX_NOTE_CHARS = 300


class OwnerNotes(Protocol):
    """Facts and standing preferences the Owner told the orchestrator to keep (ADR 0030)."""

    async def list(self, sender: str) -> list[Note]: ...

    async def add(self, sender: str, text: str) -> Note | None:
        """The new note, or None when the sender has no Business."""
        ...

    async def archive(self, sender: str, note_id: str) -> bool: ...


class InMemoryNotes:
    """Notes without a database (local runs, tests). Lost on restart."""

    def __init__(self) -> None:
        self._notes: defaultdict[str, list[Note]] = defaultdict(list)
        self._ids = itertools.count(1)

    async def list(self, sender: str) -> list[Note]:
        return list(self._notes[sender])

    async def add(self, sender: str, text: str) -> Note | None:
        note = Note(f"n{next(self._ids)}", text[:MAX_NOTE_CHARS])
        self._notes[sender].append(note)
        return note

    async def archive(self, sender: str, note_id: str) -> bool:
        notes = self._notes[sender]
        kept = [note for note in notes if note.id != note_id]
        self._notes[sender] = kept
        return len(kept) < len(notes)


class DbNotes:
    """Notes in `owner_notes`; forgetting one archives it."""

    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def list(self, sender: str) -> list[Note]:
        async with self._sessions() as db:
            business = await business_of(db, sender)
            if business is None:
                return []
            rows = await db.scalars(
                select(OwnerNote)
                .where(OwnerNote.business_id == business.id, OwnerNote.archived_at.is_(None))
                .order_by(OwnerNote.created_at, OwnerNote.id)
            )
            return [Note(short_id(row.id), row.text) for row in rows]

    async def add(self, sender: str, text: str) -> Note | None:
        async with self._sessions() as db:
            business = await business_of(db, sender)
            if business is None:
                return None
            row = OwnerNote(business_id=business.id, text=text[:MAX_NOTE_CHARS])
            db.add(row)
            await db.commit()
            return Note(short_id(row.id), row.text)

    async def archive(self, sender: str, note_id: str) -> bool:
        async with self._sessions() as db:
            business = await business_of(db, sender)
            if business is None:
                return False
            rows = (
                await db.scalars(
                    select(OwnerNote).where(
                        OwnerNote.business_id == business.id, OwnerNote.archived_at.is_(None)
                    )
                )
            ).all()
            matches = [row for row in rows if short_id(row.id) == note_id]
            for row in matches:
                row.archived_at = func.now()
            await db.commit()
            return bool(matches)
