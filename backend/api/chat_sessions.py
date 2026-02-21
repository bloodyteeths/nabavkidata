"""
Chat Session Endpoints
CRUD for persistent chat sessions with memory.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from models import User
from api.auth import get_current_user

router = APIRouter(prefix="/chat", tags=["chat"])


@router.get("/sessions")
async def list_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """List user's chat sessions (latest 20)."""
    result = await db.execute(
        text("""
            SELECT session_id, title, message_count, context_type, created_at, updated_at
            FROM chat_sessions
            WHERE user_id = CAST(:user_id AS uuid)
            ORDER BY updated_at DESC
            LIMIT 20
        """),
        {"user_id": str(current_user.user_id)}
    )
    sessions = [
        {
            "session_id": str(row[0]),
            "title": row[1],
            "message_count": row[2],
            "context_type": row[3],
            "created_at": row[4].isoformat() if row[4] else None,
            "updated_at": row[5].isoformat() if row[5] else None,
        }
        for row in result.fetchall()
    ]
    return {"sessions": sessions}


@router.post("/sessions")
async def create_session(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new chat session."""
    result = await db.execute(
        text("""
            INSERT INTO chat_sessions (user_id)
            VALUES (CAST(:user_id AS uuid))
            RETURNING session_id
        """),
        {"user_id": str(current_user.user_id)}
    )
    session_id = str(result.scalar())
    await db.commit()
    return {"session_id": session_id}


@router.get("/sessions/{session_id}")
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a chat session with its messages."""
    # Verify ownership
    session_result = await db.execute(
        text("""
            SELECT session_id, title, message_count, context_type, memory_summary, created_at, updated_at
            FROM chat_sessions
            WHERE session_id = CAST(:sid AS uuid) AND user_id = CAST(:uid AS uuid)
        """),
        {"sid": session_id, "uid": str(current_user.user_id)}
    )
    session = session_result.fetchone()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Fetch messages
    messages_result = await db.execute(
        text("""
            SELECT message_id, role, content, sources, confidence, created_at
            FROM chat_messages
            WHERE session_id = CAST(:sid AS uuid)
            ORDER BY created_at ASC
            LIMIT 50
        """),
        {"sid": session_id}
    )
    messages = [
        {
            "message_id": str(row[0]),
            "role": row[1],
            "content": row[2],
            "sources": row[3],
            "confidence": row[4],
            "created_at": row[5].isoformat() if row[5] else None,
        }
        for row in messages_result.fetchall()
    ]

    return {
        "session_id": str(session[0]),
        "title": session[1],
        "message_count": session[2],
        "context_type": session[3],
        "memory_summary": session[4],
        "created_at": session[5].isoformat() if session[5] else None,
        "updated_at": session[6].isoformat() if session[6] else None,
        "messages": messages,
    }


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a chat session and its messages."""
    result = await db.execute(
        text("""
            DELETE FROM chat_sessions
            WHERE session_id = CAST(:sid AS uuid) AND user_id = CAST(:uid AS uuid)
            RETURNING session_id
        """),
        {"sid": session_id, "uid": str(current_user.user_id)}
    )
    deleted = result.scalar()
    if not deleted:
        raise HTTPException(status_code=404, detail="Session not found")
    await db.commit()
    return {"success": True}
