"""
SOILL Catalogue of Best Practices (T4.4) — Chainlit RAG UI
Prof. S. Hallett, Cranfield University
19/05/2026
======================================

Retrieval from MongoDB + FAISS over scraped articles; answers via Mistral chat API.

Multi-turn: prior Q&A in the model prompt; follow-up questions expand the FAISS
search query (see CHAT_HISTORY_* in .env). Refreshes client metadata each message
(get_context().session). History in user_session and optionally MongoDB (thread_id).

Usage:
    chainlit run app.py

Requires Python 3.10–3.13 and a built FAISS index (build_faiss_index.py).
"""

from __future__ import annotations

import re
import uuid

import chainlit as cl

import config as cfg
from soill_chatbot.chat_history import ChatTurn, append_turn, trim_history
from soill_chatbot.conversation_log import fetch_recent_turns, log_interaction
from soill_chatbot.rag import SourceRef, answer_question
from soill_chatbot.user_identity import (
    metadata_from_chainlit,
    metadata_to_dict,
)

_SESSION_SOURCES_PREFIX = 'rag_sources_'
_SESSION_HISTORY_KEY = 'chat_history'


def _sources_cited_in_answer(answer: str, sources: list[SourceRef]) -> list[SourceRef]:
    if not sources:
        return []
    max_label = max(source.label for source in sources)
    cited: set[int] = set()
    for match in re.finditer(r'\[([^\]]+)\]', answer or ''):
        for part in match.group(1).split(','):
            token = part.strip()
            if token.isdigit():
                number = int(token)
                if 1 <= number <= max_label:
                    cited.add(number)
    by_label = {source.label: source for source in sources}
    return [by_label[i] for i in sorted(cited) if i in by_label]


def _get_session_history() -> list[ChatTurn]:
    raw = cl.user_session.get(_SESSION_HISTORY_KEY)
    if not raw:
        return []
    return [ChatTurn(question=item['question'], answer=item['answer']) for item in raw]


def _set_session_history(turns: list[ChatTurn]) -> None:
    cl.user_session.set(
        _SESSION_HISTORY_KEY,
        [{'question': turn.question, 'answer': turn.answer} for turn in turns],
    )


@cl.on_chat_start
async def on_chat_start() -> None:
    client_meta = metadata_from_chainlit()
    cl.user_session.set('client_metadata', metadata_to_dict(client_meta))

    if cfg.CHAT_HISTORY_ENABLED and cfg.LOG_CONVERSATIONS:
        prior = fetch_recent_turns(client_meta.thread_id)
        _set_session_history(trim_history(prior))

    await cl.Message(
        content=(
            'I am the **SOILL Catalogue** assistant. Ask questions about best practices for soil health, '
            'Living Labs, and Lighthouses using the web content indexed from partner projects.'
        )
    ).send()
    if not cfg.MISTRAL_API_KEY:
        await cl.Message(
            content='Set `MISTRAL_API_KEY` in your `.env` file, then restart.',
        ).send()


@cl.action_callback('show_sources')
async def on_show_sources(action: cl.Action) -> None:
    session_id = (action.payload or {}).get('sid')
    if not session_id or not isinstance(session_id, str):
        await cl.Message(
            author='SOILL',
            content='Could not load sources (missing reference).',
        ).send()
        return
    text = cl.user_session.get(f'{_SESSION_SOURCES_PREFIX}{session_id}')
    if not text:
        await cl.Message(
            author='SOILL',
            content='Sources for this answer are no longer available. Ask again to refresh.',
        ).send()
        return
    await cl.Message(author='SOILL', content=text).send()


def _sources_block(cited_sources: list[SourceRef]) -> str:
    if not cited_sources:
        return ''
    lines = ['**Sources (cited)**\n']
    for source in cited_sources:
        lines.append(
            f'- **[{source.label}]** {source.project_name} — *{source.title}* '
            f'(chunk {source.chunk_index})\n'
            f'  {source.url}\n'
            f'  {source.preview}\n'
        )
    return ''.join(lines)


@cl.on_message
async def on_message(message: cl.Message) -> None:
    text = (message.content or '').strip()
    if not text:
        return

    client_meta = metadata_from_chainlit()
    cl.user_session.set('client_metadata', metadata_to_dict(client_meta))
    history = _get_session_history() if cfg.CHAT_HISTORY_ENABLED else []

    try:
        result = answer_question(text, top_k=cfg.RAG_TOP_K, history=history)
    except (FileNotFoundError, RuntimeError) as exc:
        log_interaction(
            question=text,
            answer=None,
            error=str(exc),
            client=client_meta,
        )
        await cl.Message(author='SOILL', content=str(exc)).send()
        return
    except Exception as exc:
        log_interaction(
            question=text,
            answer=None,
            error=str(exc),
            client=client_meta,
        )
        await cl.Message(
            author='SOILL',
            content=f'An unexpected error occurred: {exc}',
        ).send()
        return

    cited = _sources_cited_in_answer(result.answer, result.sources)
    sources_text = _sources_block(cited)
    actions: list[cl.Action] = []
    if sources_text:
        session_id = str(uuid.uuid4())
        cl.user_session.set(f'{_SESSION_SOURCES_PREFIX}{session_id}', sources_text)
        actions.append(
            cl.Action(
                name='show_sources',
                payload={'sid': session_id},
                label=f'Show cited sources ({len(cited)})',
                tooltip='Opens the cited source list for this answer.',
            )
        )

    await cl.Message(
        author='SOILL',
        content=result.answer,
        actions=actions,
    ).send()

    if cfg.CHAT_HISTORY_ENABLED and result.answer:
        updated = append_turn(history, text, result.answer)
        _set_session_history(updated)

    log_interaction(
        question=text,
        answer=result.answer,
        cited_sources_count=len(cited),
        client=client_meta,
    )
