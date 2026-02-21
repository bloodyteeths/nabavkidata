"""
Chat Memory Service
Persistent conversation memory with compaction for AI chat.
"""
import json
import os
from datetime import datetime
from typing import Optional, List, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


COMPACTION_THRESHOLD = 30  # Compact after this many unsummarized messages
RECENT_MESSAGES_LIMIT = 10  # Keep last N messages as full context


async def save_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    sources: Optional[list] = None,
    confidence: Optional[str] = None
):
    """Save a chat message and update session counters."""
    await db.execute(
        text("""
            INSERT INTO chat_messages (session_id, role, content, sources, confidence)
            VALUES (CAST(:session_id AS uuid), :role, :content, CAST(:sources AS jsonb), :confidence)
        """),
        {
            "session_id": session_id,
            "role": role,
            "content": content,
            "sources": json.dumps(sources) if sources else None,
            "confidence": confidence,
        }
    )
    await db.execute(
        text("""
            UPDATE chat_sessions
            SET message_count = message_count + 1, updated_at = NOW()
            WHERE session_id = CAST(:session_id AS uuid)
        """),
        {"session_id": session_id}
    )
    # Auto-set title from first user message
    if role == "user":
        await db.execute(
            text("""
                UPDATE chat_sessions
                SET title = :title
                WHERE session_id = CAST(:session_id AS uuid) AND title IS NULL
            """),
            {"session_id": session_id, "title": content[:80]}
        )
    await db.commit()


async def load_context_for_prompt(
    db: AsyncSession,
    session_id: str,
    user_id: str
) -> dict:
    """
    Load full context for Gemini prompt:
    - memory_summary: compressed older conversation
    - recent_messages: last 10 unsummarized messages
    - user_profile: preferences + alerts summary
    """
    # 1. Fetch session memory summary
    session_result = await db.execute(
        text("""
            SELECT memory_summary, message_count
            FROM chat_sessions
            WHERE session_id = CAST(:session_id AS uuid)
        """),
        {"session_id": session_id}
    )
    session_row = session_result.fetchone()
    memory_summary = session_row[0] if session_row else None
    message_count = session_row[1] if session_row else 0

    # 2. Fetch recent unsummarized messages
    messages_result = await db.execute(
        text("""
            SELECT role, content, created_at
            FROM chat_messages
            WHERE session_id = CAST(:session_id AS uuid) AND is_summarized = FALSE
            ORDER BY created_at DESC
            LIMIT :limit
        """),
        {"session_id": session_id, "limit": RECENT_MESSAGES_LIMIT}
    )
    recent_messages = [
        {"role": row[0], "content": row[1], "created_at": row[2].isoformat() if row[2] else ""}
        for row in reversed(messages_result.fetchall())
    ]

    # 3. Build user profile from preferences + alerts
    user_profile = await _build_user_profile(db, user_id)

    # 4. Trigger compaction if needed
    unsummarized_result = await db.execute(
        text("""
            SELECT COUNT(*) FROM chat_messages
            WHERE session_id = CAST(:session_id AS uuid) AND is_summarized = FALSE
        """),
        {"session_id": session_id}
    )
    unsummarized_count = unsummarized_result.scalar() or 0

    if unsummarized_count >= COMPACTION_THRESHOLD:
        try:
            await compact_memory(db, session_id)
            # Re-fetch memory summary after compaction
            session_result2 = await db.execute(
                text("SELECT memory_summary FROM chat_sessions WHERE session_id = CAST(:sid AS uuid)"),
                {"sid": session_id}
            )
            row2 = session_result2.fetchone()
            if row2:
                memory_summary = row2[0]
        except Exception as e:
            print(f"Warning: Memory compaction failed: {e}")

    return {
        "memory_summary": memory_summary,
        "recent_messages": recent_messages,
        "user_profile": user_profile,
    }


async def compact_memory(db: AsyncSession, session_id: str):
    """Summarize older messages into memory_summary using Gemini."""
    # Fetch current summary
    session_result = await db.execute(
        text("SELECT memory_summary FROM chat_sessions WHERE session_id = CAST(:sid AS uuid)"),
        {"sid": session_id}
    )
    existing_summary = (session_result.fetchone() or [None])[0]

    # Fetch unsummarized messages EXCEPT the last RECENT_MESSAGES_LIMIT
    messages_result = await db.execute(
        text("""
            SELECT message_id, role, content FROM chat_messages
            WHERE session_id = CAST(:sid AS uuid) AND is_summarized = FALSE
            ORDER BY created_at ASC
        """),
        {"sid": session_id}
    )
    all_unsummarized = messages_result.fetchall()

    # Keep last N messages as-is, summarize the rest
    to_summarize = all_unsummarized[:-RECENT_MESSAGES_LIMIT] if len(all_unsummarized) > RECENT_MESSAGES_LIMIT else []

    if len(to_summarize) < 10:
        return  # Not enough to warrant compaction

    # Build text from messages to summarize
    messages_text = "\n".join(
        f"{row[1].capitalize()}: {row[2][:500]}" for row in to_summarize
    )

    # Call Gemini for summarization
    import google.generativeai as genai
    genai.configure(api_key=os.getenv('GEMINI_API_KEY'))

    prompt = f"""Summarize this conversation concisely. Preserve:
- User's interests, company name, sector
- Specific tender IDs, CPV codes, entity names mentioned
- Key questions asked and conclusions reached
- Any preferences or requirements expressed

{f"Previous summary: {existing_summary}" if existing_summary else "No previous summary."}

Messages to summarize:
{messages_text}

Write a concise summary paragraph (max 300 words):"""

    model = genai.GenerativeModel(os.getenv('GEMINI_MODEL', 'gemini-2.0-flash'))
    response = model.generate_content(
        prompt,
        generation_config=genai.GenerationConfig(temperature=0.2, max_output_tokens=500)
    )

    new_summary = response.text.strip()

    # Update session summary
    await db.execute(
        text("""
            UPDATE chat_sessions
            SET memory_summary = :summary, memory_summary_updated_at = NOW()
            WHERE session_id = CAST(:sid AS uuid)
        """),
        {"sid": session_id, "summary": new_summary}
    )

    # Mark old messages as summarized
    message_ids = [str(row[0]) for row in to_summarize]
    if message_ids:
        await db.execute(
            text(f"""
                UPDATE chat_messages SET is_summarized = TRUE
                WHERE message_id = ANY(CAST(:ids AS uuid[]))
            """),
            {"ids": message_ids}
        )

    await db.commit()
    print(f"[ChatMemory] Compacted {len(to_summarize)} messages into summary for session {session_id}")


async def _build_user_profile(db: AsyncSession, user_id: str) -> Optional[str]:
    """Build user profile string from preferences and alerts."""
    parts = []

    # Fetch user preferences
    try:
        prefs_result = await db.execute(
            text("""
                SELECT sectors, cpv_codes, entities, min_budget, max_budget,
                       competitor_companies, exclude_keywords
                FROM user_preferences
                WHERE user_id = CAST(:uid AS uuid)
            """),
            {"uid": user_id}
        )
        prefs = prefs_result.fetchone()
        if prefs:
            sectors, cpv_codes, entities, min_b, max_b, competitors, excludes = prefs
            if sectors:
                parts.append(f"Sectors: {', '.join(sectors)}")
            if cpv_codes:
                parts.append(f"CPV codes: {', '.join(cpv_codes[:5])}")
            if entities:
                parts.append(f"Watches entities: {', '.join(entities[:5])}")
            if min_b or max_b:
                budget = f"{min_b:,.0f}" if min_b else "0"
                budget += f" - {max_b:,.0f} MKD" if max_b else "+ MKD"
                parts.append(f"Budget range: {budget}")
            if competitors:
                parts.append(f"Competitors: {', '.join(competitors[:5])}")
    except Exception:
        pass  # Table may not exist or user has no prefs

    # Fetch active alerts
    try:
        alerts_result = await db.execute(
            text("""
                SELECT name, alert_type, criteria
                FROM tender_alerts
                WHERE user_id = CAST(:uid AS uuid) AND is_active = true
                LIMIT 5
            """),
            {"uid": user_id}
        )
        alerts = alerts_result.fetchall()
        if alerts:
            alert_strs = []
            for name, atype, criteria in alerts:
                crit = criteria if isinstance(criteria, dict) else (json.loads(criteria) if isinstance(criteria, str) else {})
                kw = crit.get("keywords", [])
                cpv = crit.get("cpv_codes", [])
                desc = f'"{name}" ({atype}'
                if kw:
                    desc += f", keywords: {', '.join(kw[:3])}"
                if cpv:
                    desc += f", CPV: {', '.join(cpv[:3])}"
                desc += ")"
                alert_strs.append(desc)
            parts.append(f"Active alerts: {'; '.join(alert_strs)}")
    except Exception:
        pass

    return ". ".join(parts) if parts else None
