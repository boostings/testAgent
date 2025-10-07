#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import os
from typing import Any, List, Tuple

import numpy as np
from sentence_transformers import SentenceTransformer

# Optional FAISS. If unavailable or incompatible (e.g., NumPy 2.x ABI), fall back to NumPy index.
try:  # noqa: SIM105
    import faiss  # type: ignore
    FAISS_AVAILABLE = True
except Exception:  # pragma: no cover
    faiss = None  # type: ignore
    FAISS_AVAILABLE = False


def load_chunks(jsonl_path: str) -> List[dict]:
    data: List[dict] = []
    with open(jsonl_path, 'r', encoding='utf-8') as f:
        for line in f:
            if not line.strip():
                continue
            data.append(json.loads(line))
    return data


class NumpyIndex:
    def __init__(self, embeddings: np.ndarray) -> None:
        # embeddings expected normalized [N, D]
        self.embeddings = embeddings.astype(np.float32)

    def search(self, queries: np.ndarray, top_k: int) -> Tuple[np.ndarray, np.ndarray]:
        # queries expected normalized [B, D]
        queries = queries.astype(np.float32)
        scores = queries @ self.embeddings.T  # cosine similarity if normalized
        idx = np.argpartition(-scores, kth=min(top_k, scores.shape[1]-1), axis=1)[:, :top_k]
        # sort top_k
        row_indices = np.arange(scores.shape[0])[:, None]
        top_scores = np.take_along_axis(scores, idx, axis=1)
        order = np.argsort(-top_scores, axis=1)
        sorted_idx = np.take_along_axis(idx, order, axis=1)
        sorted_scores = np.take_along_axis(top_scores, order, axis=1)
        return sorted_scores, sorted_idx


def build_or_load_index(
    chunks: List[dict],
    embedder: SentenceTransformer,
    index_dir: str,
) -> Tuple[Any, np.ndarray]:
    os.makedirs(index_dir, exist_ok=True)
    idx_path = os.path.join(index_dir, 'index.faiss')
    map_path = os.path.join(index_dir, 'mapping.json')
    emb_path = os.path.join(index_dir, 'embeddings.npy')

    if FAISS_AVAILABLE and os.path.exists(idx_path):
        try:
            index = faiss.read_index(idx_path)
            # mapping placeholder retained for compatibility
            if os.path.exists(map_path):
                with open(map_path, 'r', encoding='utf-8') as f:
                    _ = json.load(f)
            # We don't need to return embeddings when FAISS is used
            return index, np.empty((0, 0), dtype=np.float32)
        except Exception:
            pass
    if not FAISS_AVAILABLE and os.path.exists(emb_path):
        try:
            embs = np.load(emb_path)
            return NumpyIndex(embs), embs
        except Exception:
            pass

    texts = [c['text'] for c in chunks]
    embeddings = embedder.encode(texts, batch_size=64, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
    if FAISS_AVAILABLE:
        dim = embeddings.shape[1]
        index = faiss.IndexFlatIP(dim)
        index.add(embeddings)
        faiss.write_index(index, idx_path)
        with open(map_path, 'w', encoding='utf-8') as f:
            json.dump({'dim': int(dim), 'count': int(embeddings.shape[0])}, f)
        return index, embeddings
    else:
        # Save for quick reloads without FAISS
        np.save(emb_path, embeddings)
        return NumpyIndex(embeddings), embeddings


def retrieve(
    query: str,
    chunks: List[dict],
    index: Any,
    embedder: SentenceTransformer,
    top_k: int = 5,
) -> List[dict]:
    q_emb = embedder.encode([query], convert_to_numpy=True, normalize_embeddings=True)
    scores, indices = index.search(q_emb, top_k)
    result: List[dict] = []
    for rank, (idx, score) in enumerate(zip(indices[0], scores[0])):
        if idx < 0 or idx >= len(chunks):
            continue
        item = chunks[int(idx)].copy()
        item['score'] = float(score)
        item['rank'] = rank
        result.append(item)
    return result


def main():
    parser = argparse.ArgumentParser(description='Simple local RAG retriever over chunked JSONL dataset')
    parser.add_argument('--dataset', required=True, help='Path to chunks.jsonl produced by scraper')
    parser.add_argument('--index-dir', default='./rag_index', help='Directory to store/load FAISS index')
    parser.add_argument('--model', default='sentence-transformers/all-MiniLM-L6-v2', help='SentenceTransformer model id')
    parser.add_argument('--top-k', type=int, default=5, help='Top K chunks to retrieve')
    parser.add_argument('--query', default=None, help='Optional single-shot query; if omitted, starts REPL')
    args = parser.parse_args()

    chunks = load_chunks(args.dataset)
    embedder = SentenceTransformer(args.model)
    index, _ = build_or_load_index(chunks, embedder, args.index_dir)

    if args.query:
        results = retrieve(args.query, chunks, index, embedder, top_k=args.top_k)
        for r in results:
            print(f"[score={r['score']:.4f}] {r['title']} — {r['source_url']}")
            print(r['text'][:500].replace('\n', ' '))
            print('---')
        return

    print('Enter queries (Ctrl+C to exit):')
    try:
        while True:
            q = input('> ').strip()
            if not q:
                continue
            results = retrieve(q, chunks, index, embedder, top_k=args.top_k)
            for r in results:
                print(f"[score={r['score']:.4f}] {r['title']} — {r['source_url']}")
                print(r['text'][:500].replace('\n', ' '))
                print('---')
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()


