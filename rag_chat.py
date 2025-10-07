#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
from typing import Any, List

import numpy as np
import re
from sentence_transformers import SentenceTransformer
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import torch
from market_data_router import get_market_data_summary
from nl_tool_selector import build_realtime_context

try:  # Prefer shared retriever if available and FAISS works there
    from rag_query import load_chunks, build_or_load_index, retrieve  # type: ignore
    _RQ_AVAILABLE = True
except Exception:
    _RQ_AVAILABLE = False

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
            self.embeddings = embeddings.astype(np.float32)

        def search(self, queries: np.ndarray, top_k: int) -> tuple[np.ndarray, np.ndarray]:
            queries = queries.astype(np.float32)
            scores = queries @ self.embeddings.T
            idx = np.argpartition(-scores, kth=min(top_k - 1, scores.shape[1] - 1), axis=1)[:, :top_k]
            row = np.arange(scores.shape[0])[:, None]
            top_scores = np.take_along_axis(scores, idx, axis=1)
            order = np.argsort(-top_scores, axis=1)
            sorted_idx = np.take_along_axis(idx, order, axis=1)
            sorted_scores = np.take_along_axis(top_scores, order, axis=1)
            return sorted_scores, sorted_idx

    def build_or_load_index(
        chunks: List[dict],
        embedder: SentenceTransformer,
        index_dir: str,
    ) -> tuple[Any, np.ndarray]:
        texts = [c['text'] for c in chunks]
        embeddings = embedder.encode(texts, batch_size=64, show_progress_bar=True, convert_to_numpy=True, normalize_embeddings=True)
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


def build_context(chunks: List[dict], max_chars: int = 3000) -> str:
    buf: List[str] = []
    used = 0
    for c in chunks:
        piece = f"Title: {c['title']}\nSource: {c['source_url']}\n\n{c['text']}\n"
        if used + len(piece) > max_chars and buf:
            break
        buf.append(piece)
        used += len(piece)
    return "\n\n---\n\n".join(buf)


_ADDR_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_TX_RE = re.compile(r"\b0x[a-fA-F0-9]{64}\b")


def _extract_identifiers(text: str) -> List[str]:
    ids: List[str] = []
    ids.extend(_TX_RE.findall(text))
    # Avoid double-adding when a 64-hex also matches 40-hex suffix
    tx_set = set(ids)
    for a in _ADDR_RE.findall(text):
        if a not in tx_set:
            ids.append(a)
    # Deduplicate preserving order
    seen: set[str] = set()
    out: List[str] = []
    for s in ids:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def _merge_exact_matches(
    query: str,
    chunks: List[dict],
    retrieved: List[dict],
    top_k: int,
) -> List[dict]:
    identifiers = _extract_identifiers(query)
    if not identifiers:
        return retrieved[:top_k]
    matches: List[dict] = []
    # Index existing by a stable key to avoid duplicates
    def _key_of(item: dict) -> str:
        return str(item.get("id") or f"{item.get('doc_path')}#{item.get('chunk_index')}")
    seen_keys: set[str] = set(_key_of(r) for r in retrieved)
    for c in chunks:
        text = c.get("text", "")
        title = c.get("title", "")
        meta = f"{c.get('source_url','')} {c.get('doc_path','')}"
        if any(ident in text or ident in title or ident in meta for ident in identifiers):
            item = c.copy()
            # Give a high score to force top placement
            item["score"] = 1.1
            k = _key_of(item)
            if k not in seen_keys:
                matches.append(item)
                seen_keys.add(k)
            if len(matches) >= top_k:
                break
    # Order: exact matches first, then fill with baseline retrieval without duplicates
    out: List[dict] = []
    for i, m in enumerate(matches):
        m["rank"] = i
        out.append(m)
        if len(out) >= top_k:
            return out
    for r in retrieved:
        k = _key_of(r)
        if any(_key_of(x) == k for x in out):
            continue
        out.append(r)
        if len(out) >= top_k:
            break
    return out


def _build_system_message(rt_types: set[str], rt_mode: str) -> str:
    base = (
        "You are a sharp, trader-grade assistant for Hyperliquid.\n"
        "Style guide:\n"
        "- Keep it tight: 1–3 bullets or \u22642 short sentences. No fluff.\n"
        "- Talk like a trader: tickers, bps, px, size, liq, PnL.\n"
        "- Be a bit cocky and dryly funny. Never whiny.\n"
        "- NEVER describe API calls, HTTP requests, endpoints, code, JSON bodies, or how to query data.\n"
        "- Do not expose sources, tool names, or the '[Real-time]' header.\n"
        "- Use exact numbers: don't round prices; include units and signs.\n"
        "- Prefer concrete numbers with symbols ($, x, bps) and proper coin names.\n"
        "- Do not output code blocks, URLs, or the words 'POST', 'Content-Type', 'endpoint'.\n"
        "- Do not use emojis, hashtags, or verbose paragraphs."
        "- Do not use paragraphs. Respond concisely. Every response should be under 100 words."
        "- If unsure, say \"I don't know.\" No hedging or disclaimers.\n"
    )
    if rt_mode == "prefer":
        base = base.replace(
            "Style guide:\n",
            "Style guide:\n- If a [Real-time] section is present, answer ONLY from it; do not mention sources, tools, or the header.\n",
        )
    elif rt_mode == "merge":
        base = base.replace(
            "Style guide:\n",
            "Style guide:\n- If [Real-time] is present, ground the answer in it; supplement with docs only to confirm or fill gaps. Do not mention sources, tools, or the header.\n",
        )
    examples: List[str] = []
    if 'account_summary' in rt_types or 'active_asset_data' in rt_types:
        examples.append(
            "Wallet: This wallet has $13,104.51 available (account value $13,109.48), margin used $4.97. "
            "Open positions: 1 isolated ETH long (0.0335 ETH, entry $2,986.30, 20x, liq $2,866.27), unrealized PnL -$0.01."
        )
    if 'oi_caps' in rt_types:
        examples.append("OI caps: Perps at OI cap — CANTO, FTM, JELLY, LOOM, RLB.")
    if 'funding_history' in rt_types or 'predicted_fundings' in rt_types:
        examples.append("Funding: Avg 7d funding for BTC ≈ 0.0000125. Predicted: HlPerp 0.0000125, BybitPerp 0.0001.")
    if 'slippage' in rt_types:
        examples.append("Slippage: Buying $50k BTC — avg px $64,250, slip ~4bps.")
    if 'full_market_picture' in rt_types:
        examples.append("Market: Signal buy (0.23), mid ~$64,250, funding 0.0000125, OI rising.")
    if 'premium_monitor' in rt_types:
        examples.append("Premium: BTC premium 0.0003, funding 0.0000125.")
    if examples:
        base += "\nExamples:\n" + "\n".join(examples) + "\n"
    base += "If unsure, say you don't know."
    return base


def build_prompt_and_rt(user_query: str, context: str, rt_mode: str) -> tuple[str, str]:
    # Embedding-based tool selection
    rt = "" if rt_mode == "off" else build_realtime_context(user_query, max_tools=3)
    extras: List[str] = []
    if rt:
        extras.append(rt)
    # Always also attempt deterministic router (ensures wallet account summaries are included)
    market = "" if rt_mode == "off" else get_market_data_summary(user_query, network="mainnet")
    if market:
        extras.append(market)
    rt_display = "\n".join(extras) if extras else ""
    if rt_display:
        # Heuristic override: treat premium/mark/vol/liquidity/oi queries as real-time intents too
        ql = user_query.lower()
        rt_keywords = [
            "orderbook", "book", "trades", "funding", "slippage", "signal",
            "oi cap", "open interest cap", "open interest", "oi", "premium", "mark",
            "mid", "liquidity", "depth", "spread", "vwap", "volatility"
        ]
        rt_intent = any(k in ql for k in rt_keywords)
        if rt_mode == "merge" and not rt_intent:
            context = "[Real-time]\n" + rt_display + "\n\n" + context
        else:
            context = "[Real-time]\n" + rt_display
    # Derive tool types present to tailor the system message
    rt_types: set[str] = set()
    if rt_display:
        for line in rt_display.splitlines():
            if ":" in line:
                name = line.split(":", 1)[0].strip()
                if name:
                    rt_types.add(name)
    system = _build_system_message(rt_types, rt_mode)
    # For models with chat templates, we'll construct messages upstream
    prompt = (
        f"<|system|>\n{system}\n<|context|>\n{context}\n"
        f"<|user|>\n{user_query}\n<|assistant|>"
    )
    return prompt, rt_display


def main():
    parser = argparse.ArgumentParser(description='RAG chat over scraped docs using a small HF model')
    parser.add_argument('--dataset', required=True, help='Path to chunks.jsonl')
    parser.add_argument('--index-dir', default='./rag_index', help='Directory to store/load FAISS index')
    parser.add_argument('--embedder', default='sentence-transformers/all-MiniLM-L6-v2', help='SentenceTransformer model id')
    parser.add_argument('--model', default='Qwen/Qwen2.5-1.5B-Instruct', help='HF causal LM id')
    parser.add_argument('--lora', default=None, help='Optional path to LoRA adapter (trained)')
    parser.add_argument('--max-new-tokens', type=int, default=384)
    parser.add_argument('--top-k', type=int, default=5)
    parser.add_argument('--rt-mode', choices=['prefer', 'merge', 'off'], default='prefer', help='How to use real-time context vs docs')
    args = parser.parse_args()

    chunks = load_chunks(args.dataset)
    embedder = SentenceTransformer(args.embedder)
    index, _ = build_or_load_index(chunks, embedder, args.index_dir)

    device = 'cuda' if torch.cuda.is_available() else ('mps' if torch.backends.mps.is_available() else 'cpu')
    tokenizer = AutoTokenizer.from_pretrained(args.model)
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        torch_dtype=torch.float16 if device == 'cuda' else None,
    )
    if args.lora:
        model = PeftModel.from_pretrained(model, args.lora)
    model = model.to(device)

    print('\n' + '='*50)
    print('🤖  Welcome to HyperLiquid Chat!  📚')
    print('Type your questions below.')
    print('Press Ctrl+C to exit at any time.')
    print('='*50 + '\n')
    try:
        while True:
            q = input('> ').strip()
            if not q:
                continue
            retrieved_base = retrieve(q, chunks, index, embedder, top_k=args.top_k)
            retrieved = _merge_exact_matches(q, chunks, retrieved_base, top_k=args.top_k)
            context = build_context(retrieved)
            prompt, rt_display = build_prompt_and_rt(q, context, args.rt_mode)
            if rt_display:
                # Only print the human-readable summary lines (no internal keys)
                print("\n".join([ln for ln in rt_display.splitlines() if ":" not in ln or ln.split(":",1)[0] not in {"account_summary","oi_caps","funding_history","full_market_picture","slippage","predicted_fundings","meta_and_ctxs","trades","orderbook","asks_to_price"}]))
            # Post-filter: strip any accidental API phrases
            def _strip_api_phrases(text: str) -> str:
                banned = ["POST ", "Content-Type", "endpoint", "https://", "http://"]
                for b in banned:
                    text = text.replace(b, "")
                return text
            # Use chat template if available to enforce roles
            # Derive rt_types for a tailored system message
            rt_types: set[str] = set()
            if rt_display:
                for line in rt_display.splitlines():
                    if ":" in line:
                        name = line.split(":", 1)[0].strip()
                        if name:
                            rt_types.add(name)
            messages = [
                {"role": "system", "content": _build_system_message(rt_types, args.rt_mode)},
                {"role": "user", "content": q + "\n\n" + ("[Real-time]\n" + rt_display if rt_display else "") + ("\n\n" + context if args.rt_mode == 'merge' and not rt_display else "")},
            ]
            try:
                text_input = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
                inputs = tokenizer(text_input, return_tensors='pt').to(device)
            except Exception:
                inputs = tokenizer(prompt, return_tensors='pt').to(device)
            gen_kwargs = dict(
                max_new_tokens=args.max_new_tokens,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=False,
                temperature=0.0,
            )
            out = model.generate(**inputs, **gen_kwargs)
            try:
                # Decode only newly generated tokens (exclude prompt)
                gen_only = out[:, inputs["input_ids"].shape[-1]:]
                text = tokenizer.decode(gen_only[0], skip_special_tokens=True)
            except Exception:
                text = tokenizer.decode(out[0], skip_special_tokens=True)
            text = _strip_api_phrases(text)
            # Strip any stray role markers the model might emit
            for marker in ("<|system|>", "<|user|>", "<|assistant|>"):
                text = text.replace(marker, "")
            # Hard post-filter: remove emojis/hashtags and enforce <=2 sentences
            text = re.sub(r"[#][\w-]+", "", text)
            text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)
            sentences = re.split(r"(?<=[.!?])\s+", text.strip())
            text = " ".join(sentences[:2])
            # Heuristic: print the assistant slice after the last marker
            if '<|assistant|>' in text:
                text = text.split('<|assistant|>')[-1].strip()
            print(text)
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()


