#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from starlette.staticfiles import StaticFiles

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers import TextIteratorStreamer
from sentence_transformers import SentenceTransformer
import json
from threading import Thread
import re as _re

try:
    import mcp_hyperliquid as hl
except Exception:
    hl = None  # type: ignore

# Reuse chat building utilities
import rag_chat as rc


app = FastAPI(title="HyperLiquid Chat Server", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _strip_api_phrases(text: str) -> str:
    banned = ["POST ", "Content-Type", "endpoint", "https://", "http://"]
    for b in banned:
        text = text.replace(b, "")
    return text


@app.on_event("startup")
def _startup() -> None:
    # Configuration via environment
    dataset = os.getenv("RAG_DATASET")
    if not dataset or not os.path.exists(dataset or ""):
        # Try a sensible default next to this file
        candidate = os.path.join(os.path.dirname(__file__), "runs", "current", "chunks.cleaned.jsonl")
        if os.path.exists(candidate):
            dataset = candidate
        else:
            raise RuntimeError(
                "Set RAG_DATASET env var to your chunks.jsonl path (e.g., "
                "/srv/shared/Models/hyperLiquidAgent/test/runs/current/chunks.cleaned.jsonl)"
            )
    index_dir = os.getenv("RAG_INDEX_DIR", "./rag_index")
    embedder_id = os.getenv("RAG_EMBEDDER", "sentence-transformers/all-MiniLM-L6-v2")
    model_id = os.getenv("RAG_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
    lora_path = os.getenv("RAG_LORA")

    # Load dataset and embedder/index
    chunks = rc.load_chunks(dataset)
    embedder = SentenceTransformer(embedder_id)
    index, _ = rc.build_or_load_index(chunks, embedder, index_dir)

    # Model
    # Honor explicit device override
    forced_device = (os.getenv("RAG_DEVICE") or "").strip().lower()
    if forced_device in {"cpu", "cuda", "mps"}:
        device = forced_device
    else:
        device = "cuda" if torch.cuda.is_available() else ("mps" if torch.backends.mps.is_available() else "cpu")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id,
        torch_dtype=torch.float16 if device == "cuda" else None,
    )
    if lora_path:
        from peft import PeftModel
        model = PeftModel.from_pretrained(model, lora_path)
    try:
        model = model.to(device)
    except torch.OutOfMemoryError:
        # Fallback to CPU automatically if GPU is OOM
        device = "cpu"
        model = model.to("cpu")

    # Shared state
    app.state.chunks = chunks
    app.state.embedder = embedder
    app.state.index = index
    app.state.tokenizer = tokenizer
    app.state.model = model
    app.state.device = device
    app.state.model_id = model_id
    app.state.embedder_id = embedder_id


@app.post("/api/chat")
def chat(payload: Dict[str, Any]) -> JSONResponse:
    message: str = str(payload.get("message", "")).strip()
    if not message:
        raise HTTPException(status_code=400, detail="message is required")
    rt_mode: str = str(payload.get("rt_mode", "prefer"))
    top_k: int = int(payload.get("top_k", 5))

    chunks = app.state.chunks
    embedder: SentenceTransformer = app.state.embedder
    index = app.state.index
    tokenizer: AutoTokenizer = app.state.tokenizer
    model: AutoModelForCausalLM = app.state.model
    device: str = app.state.device

    # Retrieve docs
    retrieved_base = rc.retrieve(message, chunks, index, embedder, top_k=top_k)
    retrieved = rc._merge_exact_matches(message, chunks, retrieved_base, top_k=top_k)
    context = rc.build_context(retrieved)
    # Build RT context with trace of MCP calls
    try:
        from nl_tool_selector import build_realtime_context_structured
        rt_text, rt_calls = build_realtime_context_structured(message, max_tools=3) if rt_mode != "off" else ("", [])
    except Exception:
        rt_text, rt_calls = (rc.build_realtime_context(message, max_tools=3), []) if rt_mode != "off" else ("", [])
    # Deterministic market router as before
    market = "" if rt_mode == "off" else rc.get_market_data_summary(message, network="mainnet")
    rt_display = "\n".join([x for x in [rt_text, market] if x])
    prompt, _ = rc.build_prompt_and_rt(message, context, rt_mode)

    # Build chat template when available
    # Tailor system prompt to present real-time types
    rt_types: set[str] = set()
    if rt_display:
        for line in rt_display.splitlines():
            if ":" in line:
                name = line.split(":", 1)[0].strip()
                if name:
                    rt_types.add(name)
    messages = [
        {"role": "system", "content": rc._build_system_message(rt_types, rt_mode)},
        {"role": "user", "content": message + "\n\n" + ("[Real-time]\n" + rt_display if rt_display else "") + ("\n\n" + context if rt_mode == "merge" and not rt_display else "")},
    ]
    try:
        text_input = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text_input, return_tensors='pt').to(device)
    except Exception:
        inputs = tokenizer(prompt, return_tensors='pt').to(device)

    gen_kwargs = dict(
        max_new_tokens=int(payload.get("max_new_tokens", 384)),
        pad_token_id=tokenizer.eos_token_id,
        do_sample=False,
        temperature=0.0,
    )
    out = model.generate(**inputs, **gen_kwargs)
    try:
        gen_only = out[:, inputs["input_ids"].shape[-1]:]
        text = tokenizer.decode(gen_only[0], skip_special_tokens=True)
    except Exception:
        text = tokenizer.decode(out[0], skip_special_tokens=True)
    text = _strip_api_phrases(text)
    for marker in ("<|system|>", "<|user|>", "<|assistant|>"):
        text = text.replace(marker, "")
    # Post-filter: remove emojis/hashtags and enforce <=2 sentences
    text = re.sub(r"[#][\w-]+", "", text)
    text = re.sub(r"[\U00010000-\U0010FFFF]", "", text)
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    text = " ".join(sentences[:2])
    if '<|assistant|>' in text:
        text = text.split('<|assistant|>')[-1].strip()

    return JSONResponse({"ok": True, "text": text, "rt": rt_display})


@app.get("/api/config")
def config() -> JSONResponse:
    return JSONResponse({
        "ok": True,
        "model": getattr(app.state, "model_id", None),
        "embedder": getattr(app.state, "embedder_id", None),
        "rt_modes": ["prefer", "merge", "off"],
    })


@app.get("/api/chat_stream")
def chat_stream(message: str, rt_mode: str = "prefer", top_k: int = 5, max_new_tokens: int = 384) -> StreamingResponse:
    message = (message or "").strip()
    if not message:
        return StreamingResponse((x for x in []), media_type="text/event-stream")

    chunks = app.state.chunks
    embedder: SentenceTransformer = app.state.embedder
    index = app.state.index
    tokenizer: AutoTokenizer = app.state.tokenizer
    model: AutoModelForCausalLM = app.state.model
    device: str = app.state.device

    # Retrieve docs and RT
    retrieved_base = rc.retrieve(message, chunks, index, embedder, top_k=top_k)
    retrieved = rc._merge_exact_matches(message, chunks, retrieved_base, top_k=top_k)
    context = rc.build_context(retrieved)
    # Build RT context with trace of MCP calls
    try:
        from nl_tool_selector import build_realtime_context_structured
        rt_text, rt_calls = build_realtime_context_structured(message, max_tools=3) if rt_mode != "off" else ("", [])
    except Exception:
        rt_text, rt_calls = (rc.build_realtime_context(message, max_tools=3), []) if rt_mode != "off" else ("", [])
    market = "" if rt_mode == "off" else rc.get_market_data_summary(message, network="mainnet")
    rt_display = "\n".join([x for x in [rt_text, market] if x])
    prompt, _ = rc.build_prompt_and_rt(message, context, rt_mode)

    # Tailored system prompt
    rt_types: set[str] = set()
    if rt_display:
        for line in rt_display.splitlines():
            if ":" in line:
                name = line.split(":", 1)[0].strip()
                if name:
                    rt_types.add(name)
    messages = [
        {"role": "system", "content": rc._build_system_message(rt_types, rt_mode)},
        {"role": "user", "content": message + "\n\n" + ("[Real-time]\n" + rt_display if rt_display else "") + ("\n\n" + context if rt_mode == "merge" and not rt_display else "")},
    ]
    try:
        text_input = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text_input, return_tensors='pt').to(device)
    except Exception:
        inputs = tokenizer(prompt, return_tensors='pt').to(device)

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
    gen_kwargs = dict(
        max_new_tokens=max_new_tokens,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=False,
        temperature=0.0,
        streamer=streamer,
    )

    def _run():
        model.generate(**inputs, **gen_kwargs)

    thread = Thread(target=_run, daemon=True)
    thread.start()

    def _extract_ticker(text: str) -> Optional[str]:
        m = _re.search(r"(?<![A-Za-z0-9_])\$([A-Z]{2,10})\b", text.upper())
        return m.group(1) if m else None

    def _draft_summary() -> Optional[str]:
        try:
            coin = _extract_ticker(message)
            if not coin or hl is None:
                return None
            mp = hl.get_full_market_picture(coin=coin, network="mainnet", depth=50, trades=30)
            snap = mp.get("marketSnapshot", {}) if isinstance(mp, dict) else {}
            sig = mp.get("signal", {}) if isinstance(mp, dict) else {}
            mid = snap.get("mid")
            fund = snap.get("funding")
            oi = snap.get("OI")
            prem = snap.get("premium")
            label = sig.get("label")
            score = sig.get("score")
            parts = []
            if mid is not None: parts.append(f"mid {mid}")
            if fund is not None: parts.append(f"funding {fund}")
            if oi is not None: parts.append(f"OI {oi}")
            if prem is not None: parts.append(f"prem {prem}")
            sig_s = f"Signal {label} ({score})" if label is not None else None
            core = ", ".join(parts)
            return (f"{coin}: {core}. " + (sig_s or "")).strip()
        except Exception:
            return None

    def event_gen():
        # Send RT block upfront
        yield f"event: rt\ndata: {json.dumps(rt_display)}\n\n"
        # Emit MCP call traces for transparency
        try:
            # Only show calls relevant to the first $TICKER in the query
            coin = None
            m = _re.search(r"(?<![A-Za-z0-9_])\$([A-Z]{2,10})\b", message.upper())
            if m:
                coin = m.group(1)
            for call in (rt_calls or []):
                try:
                    k = call.get("kwargs", {})
                    call_coin = (k.get("coin") or k.get("tickers") or k.get("coins"))
                    if isinstance(call_coin, list):
                        match = coin in call_coin if coin else True
                    else:
                        match = (call_coin == coin) if coin else True
                    if not match:
                        continue
                    # Trim response to key fields to avoid data dumps
                    resp = call.get("response")
                    trimmed = resp
                    try:
                        if call.get("tool") == "full_market_picture" and isinstance(resp, dict):
                            trimmed = {
                                "marketSnapshot": {k: resp.get("marketSnapshot", {}).get(k) for k in ["mid", "funding", "OI", "premium"]},
                                "signal": resp.get("signal"),
                                "analytics": {k: resp.get("analytics", {}).get(k) for k in ["imbalance", "vwap", "vwapDrift"]},
                            }
                        elif call.get("tool") == "orderbook" and isinstance(resp, dict):
                            d = resp.get("data", {})
                            trimmed = {"bids": (d.get("bids") or [])[:5], "asks": (d.get("asks") or [])[:5]}
                        elif call.get("tool") == "trades" and isinstance(resp, dict):
                            trimmed = (resp.get("data") or [])[-5:]
                        elif isinstance(resp, dict) and "data" in resp and isinstance(resp["data"], list):
                            trimmed = {"data": resp["data"][:20]}
                    except Exception:
                        trimmed = resp
                    out = dict(call)
                    out["response"] = trimmed
                    yield f"event: mcp\ndata: {json.dumps(out)}\n\n"
                except Exception:
                    continue
        except Exception:
            pass
        # Emit MCP call traces for transparency
        try:
            for call in (rt_calls or []):
                yield f"event: mcp\ndata: {json.dumps(call)}\n\n"
        except Exception:
            pass
        draft = _draft_summary()
        if draft:
            yield f"event: draft\ndata: {json.dumps(draft)}\n\n"
        try:
            for chunk in streamer:
                # Basic filtering
                data = _strip_api_phrases(chunk)
                data = data.replace("<|system|>", "").replace("<|user|>", "").replace("<|assistant|>", "")
                yield f"event: token\ndata: {json.dumps(data)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps(str(e))}\n\n"
        yield "event: done\ndata: {}\n\n"

    return StreamingResponse(event_gen(), media_type="text/event-stream")


# Static frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.isdir(static_dir):
    os.makedirs(static_dir, exist_ok=True)

app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(static_dir, "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=int(os.getenv("PORT", "7860")), reload=False)


