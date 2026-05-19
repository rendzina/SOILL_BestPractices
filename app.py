"""
SOILL Catalogue of Best Practices (T4.4) — Chainlit RAG UI
Prof. S. Hallett, Cranfield University
19/05/2026
======================================

Retrieval from MongoDB + FAISS over scraped articles; answers via Mistral chat API.

Usage:
    chainlit run app.py

Requires Python 3.10–3.13 and a built FAISS index (build_faiss_index.py).
"""

from __future__ import annotations

import re
import uuid

import chainlit as cl

import config as cfg
from soill_chatbot.conversation_log import log_interaction
from soill_chatbot.rag import SourceRef, answer_question

_SESSION_SOURCES_PREFIX = 'rag_sources_'


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


@cl.on_chat_start
async def on_chat_start() -> None:
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
    try:
        result = answer_question(text, top_k=cfg.RAG_TOP_K)
    except (FileNotFoundError, RuntimeError) as exc:
        log_interaction(question=text, answer=None, error=str(exc))
        await cl.Message(author='SOILL', content=str(exc)).send()
        return
    except Exception as exc:
        log_interaction(question=text, answer=None, error=str(exc))
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
    log_interaction(
        question=text,
        answer=result.answer,
        cited_sources_count=len(cited),
    )
