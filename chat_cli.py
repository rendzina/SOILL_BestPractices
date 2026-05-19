#!/usr/bin/env python3
"""
SOILL Catalogue of Best Practices (T4.4) — terminal chat (no Chainlit)
Prof. S. Hallett, Cranfield University
19/05/2026
======================================

Use when Chainlit is unavailable (e.g. Python 3.14). Same RAG as app.py.

Usage:
    python chat_cli.py
"""

from __future__ import annotations

import re
import sys

import config as cfg
from soill_chatbot.conversation_log import log_interaction
from soill_chatbot.rag import SourceRef, answer_question


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


def _print_sources(cited: list[SourceRef]) -> None:
    if not cited:
        return
    print('\n--- Sources (cited) ---')
    for source in cited:
        print(f'[{source.label}] {source.project_name} — {source.title}')
        print(f'    {source.url}')
        print(f'    {source.preview[:200]}…' if len(source.preview) > 200 else f'    {source.preview}')


def main() -> None:
    if not cfg.MISTRAL_API_KEY:
        print('ERROR: Set MISTRAL_API_KEY in .env', file=sys.stderr)
        sys.exit(1)

    print('SOILL Catalogue assistant (terminal)')
    print('Ask questions about indexed articles. Type quit or exit to stop.\n')

    while True:
        try:
            question = input('You: ').strip()
        except (EOFError, KeyboardInterrupt):
            print('\nGoodbye.')
            break
        if not question:
            continue
        if question.lower() in ('quit', 'exit', 'q', 'end', 'stop'):
            print('Goodbye.')
            break

        try:
            result = answer_question(question, top_k=cfg.RAG_TOP_K)
        except (FileNotFoundError, RuntimeError) as exc:
            print(f'\nError: {exc}\n')
            log_interaction(question=question, answer=None, error=str(exc))
            continue

        cited = _sources_cited_in_answer(result.answer, result.sources)
        print(f'\nSOILL: {result.answer}')
        _print_sources(cited)
        print()
        log_interaction(
            question=question,
            answer=result.answer,
            cited_sources_count=len(cited),
        )


if __name__ == '__main__':
    main()
