"""
RAG: retrieve with FAISS, enrich from MongoDB, answer with Mistral chat.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import List, Optional, Sequence, Union

from soill_chatbot.chat_history import ChatTurn

import numpy as np

import config as cfg
from soill_chatbot.mistral_chat import complete_chat
from soill_chatbot.mistral_client import (
    AssistantMessage,
    Mistral,
    SystemMessage,
    UserMessage,
)
from soill_chatbot import embeddings, store_faiss, store_mongo

SYSTEM_RAG = (
    'You are a helpful assistant for the SOILL Catalogue of Best Practices (Task T4.4). '
    'You are used by researchers to answer questions about SOILL Best Practices and technical solutions across the Living labs and lighthouses. '
    'You answer questions about Living Labs, Lighthouses, and soil health content '
    'from Living Lab and Lighthouse partner project websites that have been crawled and indexed. '
    'Answer only using the numbered context excerpts below. '
    'If the answer is not in the context, say you do not have enough information. '
    'Cite only context you rely on: use markers such as [1] or [2, 3] next to supported sentences. '
    'Where you cite, mention the project name, source website and article title where helpful. '
    'Earlier user and assistant turns may be included for follow-up questions only; '
    'ground every factual claim in the numbered context excerpts, not in chat history alone. '
    'Use UK English spelling in your answers.'
)


@dataclass
class SourceRef:
    label: int
    chunk_id: str
    project_name: str
    title: str
    url: str
    chunk_index: int
    preview: str


@dataclass
class RAGResult:
    answer: str
    sources: list[SourceRef]
    top_k: int


def _load_meta() -> dict:
    with open(cfg.FAISS_META_PATH, encoding='utf-8') as handle:
        return json.load(handle)


def _mmr_indices(sim_q: np.ndarray, vectors: np.ndarray, k: int, lam: float) -> list[int]:
    count = int(vectors.shape[0])
    if count <= k:
        return list(range(count))
    selected = [int(np.argmax(sim_q))]
    remaining = set(range(count)) - set(selected)
    similarity = vectors @ vectors.T
    while len(selected) < k and remaining:
        best_index = -1
        best_score = -np.inf
        for candidate in remaining:
            redundancy = max(float(similarity[candidate, chosen]) for chosen in selected)
            score = lam * float(sim_q[candidate]) - (1.0 - lam) * redundancy
            if score > best_score:
                best_score = score
                best_index = int(candidate)
        selected.append(best_index)
        remaining.remove(best_index)
    return selected


def _deduped_candidates_from_faiss(
    faiss_row: list,
    dist_row: list,
    order: Sequence[str],
) -> tuple[list[int], list[str], list[float]]:
    faiss_ids: list[int] = []
    chunk_ids: list[str] = []
    scores: list[float] = []
    seen: set[str] = set()
    for index, row_id in enumerate(faiss_row):
        if row_id is None or (isinstance(row_id, float) and math.isnan(row_id)):
            continue
        if isinstance(row_id, (int, float)) and int(row_id) < 0:
            continue
        faiss_id = int(row_id)
        if not (0 <= faiss_id < len(order)):
            continue
        chunk_id = str(order[faiss_id])
        if chunk_id in seen:
            continue
        seen.add(chunk_id)
        faiss_ids.append(faiss_id)
        chunk_ids.append(chunk_id)
        scores.append(float(dist_row[index]) if index < len(dist_row) else 0.0)
    return faiss_ids, chunk_ids, scores


def _assistant_content_to_str(content: Union[str, list, None]) -> str:
    if content is None:
        return ''
    if isinstance(content, str):
        return content
    parts: list[str] = []
    for item in content:
        text = getattr(item, 'text', None)
        if text:
            parts.append(text)
    return ''.join(parts)


def retrieve(
    client: Mistral,
    question: str,
    top_k: int,
) -> tuple[list[SourceRef], str]:
    index = store_faiss.try_load_index()
    if index is None or not cfg.FAISS_META_PATH.is_file():
        raise FileNotFoundError(
            'FAISS index is missing. Run `python build_faiss_index.py` after scraping.'
        )
    meta = _load_meta()
    vector_count = int(meta.get('n_vectors', 0))
    if not vector_count:
        raise FileNotFoundError('The FAISS index is empty. Run `python build_faiss_index.py`.')

    order: list = list(meta.get('chunk_id_order', []))
    query_vector = embeddings.embed_query(client, question)
    query_flat = np.asarray(query_vector, dtype=np.float32).reshape(-1)

    use_mmr = bool(cfg.RAG_MMR_ENABLED) and top_k >= 2 and vector_count >= 2
    if use_mmr:
        fetch_k = min(
            vector_count,
            max(top_k * int(cfg.RAG_MMR_FETCH_MULT), top_k + 1),
            int(cfg.RAG_MMR_FETCH_CAP),
        )
    else:
        fetch_k = min(vector_count, top_k)

    distances, ids = store_faiss.search(query_vector, fetch_k, index)
    faiss_row = ids[0].tolist() if ids is not None else []
    dist_row = distances[0].tolist() if distances is not None else []

    faiss_ids, chunk_ids_order, _ = _deduped_candidates_from_faiss(
        faiss_row, dist_row, order
    )
    if not chunk_ids_order:
        return [], ''

    if use_mmr and len(chunk_ids_order) > top_k:
        try:
            matrix = store_faiss.reconstruct_rows_for_search_ids(index, faiss_ids)
            sim_q = matrix @ query_flat
            picks = _mmr_indices(sim_q, matrix, top_k, float(cfg.RAG_MMR_LAMBDA))
            chunk_ids_unique = [chunk_ids_order[i] for i in picks]
        except Exception:
            try:
                matrix = store_mongo.fetch_embeddings_matrix_ordered(chunk_ids_order)
                sim_q = matrix @ query_flat
                picks = _mmr_indices(sim_q, matrix, top_k, float(cfg.RAG_MMR_LAMBDA))
                chunk_ids_unique = [chunk_ids_order[i] for i in picks]
            except Exception:
                chunk_ids_unique = chunk_ids_order[:top_k]
    else:
        chunk_ids_unique = chunk_ids_order[: min(top_k, len(chunk_ids_order))]

    rows = store_mongo.fetch_chunks_by_ids(chunk_ids_unique)
    sources: list[SourceRef] = []
    context_lines: list[str] = []
    for number, row in enumerate(rows, start=1):
        text = (row.get('text') or '').strip()
        preview = text[:280] + ('…' if len(text) > 280 else '')
        project = row.get('project_name', 'unknown project')
        title = row.get('title', 'Untitled')
        url = row.get('url', '')
        chunk_index = int(row.get('chunk_index', 0))
        sources.append(
            SourceRef(
                label=number,
                chunk_id=row.get('chunk_id', ''),
                project_name=project,
                title=title,
                url=url,
                chunk_index=chunk_index,
                preview=preview,
            )
        )
        context_lines.append(
            f'[{number}] (project: {project}, article: {title}, chunk {chunk_index}):\n'
            f'{text}\n'
            f'URL: {url}\n'
        )
    return sources, '\n\n'.join(context_lines)


def _build_chat_messages(
    user_block: str,
    history: Optional[Sequence[ChatTurn]],
) -> list:
    messages: list = [SystemMessage(content=SYSTEM_RAG)]
    if history:
        for turn in history:
            messages.append(UserMessage(content=turn.question))
            messages.append(AssistantMessage(content=turn.answer))
    messages.append(UserMessage(content=user_block))
    return messages


def answer_question(
    user_message: str,
    top_k: Optional[int] = None,
    history: Optional[Sequence[ChatTurn]] = None,
) -> RAGResult:
    k = int(top_k or cfg.RAG_TOP_K)
    client = embeddings.get_client()
    sources, context_block = retrieve(client, user_message, k)
    if not context_block:
        return RAGResult(
            answer=(
                'I do not have any indexed articles to search. '
                'Run SOILL_scrape.py, then `python build_faiss_index.py`.'
            ),
            sources=[],
            top_k=k,
        )

    user_block = f'Question: {user_message}\n\nContext:\n{context_block}'
    chat = complete_chat(
        client,
        _build_chat_messages(user_block, history),
    )
    if not chat or not chat.choices:
        return RAGResult(answer='No response from the model.', sources=sources, top_k=k)
    content = chat.choices[0].message.content
    text = _assistant_content_to_str(content)
    return RAGResult(answer=text.strip(), sources=sources, top_k=k)
