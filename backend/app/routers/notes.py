from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Note, User
from ..schemas import Items, NoteGenerate, NoteOut, NotePatch
from ..services import demo_ai
from ..services.ai import ai
from ..services.export import to_pdf
from ..services.lecture_service import get_owned_lecture, segment_tuples

router = APIRouter(tags=["notes"])


def _note_or_404(db: Session, user: User, note_id: int) -> Note:
    from ..models import Lecture

    note = db.get(Note, note_id)
    if note is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    lecture = db.get(Lecture, note.lecture_id)
    if lecture is None or lecture.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    return note


@router.post("/lectures/{lecture_id}/notes/generate", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def generate_note(
    lecture_id: int,
    payload: NoteGenerate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteOut:
    if payload.kind == "manual":
        raise HTTPException(422, "Use the manual note endpoint for your own notes")
    lecture = get_owned_lecture(db, user, lecture_id)
    segs = segment_tuples(lecture)
    if not segs:
        raise HTTPException(status.HTTP_409_CONFLICT, "This lecture has no transcript yet")

    chapters = [(c.title, c.start) for c in sorted(lecture.chapters, key=lambda x: x.idx)]
    parsed = [(0.0, s[3]) for s in segs]

    if payload.kind == "summary":
        fallback = lambda: demo_ai.summary_note(lecture.title, chapters, segs)  # noqa: E731
        system = "Write concise student revision notes in Markdown using only the transcript."
        instruction = "Produce a Markdown summary: Overview, Sections with timestamps, Key points, Key terms."
    elif payload.kind == "chapters":
        spans = []
        for name, start in chapters:
            span = [s for s in segs if s[1] >= start]
            nxt = [c[1] for c in chapters if c[1] > start]
            if nxt:
                span = [s for s in segs if start <= s[1] < min(nxt)]
            spans.append((name, start, span or segs))
        fallback = lambda: demo_ai.chapters_note(lecture.title, spans)  # noqa: E731
        system = "Write chapter-wise revision notes in Markdown using only the transcript."
        instruction = "Produce Markdown notes grouped by chapter with timestamps."
    else:
        fallback = lambda: demo_ai.definitions_note(lecture.title, segs)  # noqa: E731
        system = "Extract definitions exactly as stated in the transcript. Markdown only."
        instruction = "Produce a Markdown list of definitions found in the transcript."

    # Bound transcript size to avoid HTTP gateway 504 timeouts on massive lectures
    max_chars = 24000
    lines = []
    total_len = 0
    for i, s in enumerate(segs[:300]):
        line = f"[{s[1]:.0f}s] {s[3]}" if lecture.source != "document" else f"[Excerpt {i+1}] {s[3]}"
        if total_len + len(line) > max_chars:
            break
        lines.append(line)
        total_len += len(line)
    transcript_block = "\n".join(lines)
    if lecture.source == "document":
        instruction = instruction.replace("with timestamps", "with supporting excerpts").replace("Sections with timestamps", "Sections with supporting excerpts") + " This is a document: never invent video timestamps or page numbers."
    content, mode = ai.complete_text(
        f"Lecture: {lecture.title}\n\nTranscript:\n{transcript_block}\n\n{instruction}",
        system=system + " Use plain-text formulas (for example F = m × a), standard headings and lists. Do not use LaTeX, HTML or Markdown tables.",
        temperature=0.3,
        fallback=fallback,
        timeout_ms=35000,
        max_output_tokens=4096,
    )

    # replace same-kind note for this lecture (one note per kind)
    db.execute(delete(Note).where(Note.lecture_id == lecture.id, Note.kind == payload.kind))
    title = {
        "summary": f"{lecture.title} — Summary",
        "chapters": f"{lecture.title} — Chapter notes",
        "definitions": f"{lecture.title} — Definitions",
    }[payload.kind]
    note = Note(lecture_id=lecture.id, kind=payload.kind, title=title, content_md=content, mode=mode)
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteOut.model_validate(note)


@router.get("/lectures/{lecture_id}/notes", response_model=Items)
def list_notes(
    lecture_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Items:
    lecture = get_owned_lecture(db, user, lecture_id)
    rows = db.scalars(
        select(Note).where(Note.lecture_id == lecture.id).order_by(Note.created_at.desc())
    ).all()
    return Items(items=[NoteOut.model_validate(n) for n in rows])


@router.get("/notes/{note_id}", response_model=NoteOut)
def get_note(
    note_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteOut:
    return NoteOut.model_validate(_note_or_404(db, user, note_id))


@router.patch("/notes/{note_id}", response_model=NoteOut)
def patch_note(
    note_id: int,
    payload: NotePatch,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> NoteOut:
    note = _note_or_404(db, user, note_id)
    if payload.title is not None:
        note.title = payload.title
    if payload.content_md is not None:
        note.content_md = payload.content_md
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteOut.model_validate(note)


@router.delete("/notes/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    note = _note_or_404(db, user, note_id)
    db.delete(note)
    db.commit()


@router.get("/notes/{note_id}/export")
def export_note(
    note_id: int,
    format: str = "md",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    note = _note_or_404(db, user, note_id)
    safe_title = "".join(c for c in note.title if c.isalnum() or c in " -_").strip() or "oraya-notes"
    if format == "pdf":
        data = to_pdf(note.content_md, note.title)
        return Response(
            content=data,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{safe_title}.pdf"'},
        )
    if format != "md":
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "format must be md or pdf")
    return Response(
        content=note.content_md.encode("utf-8"),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{safe_title}.md"'},
    )
