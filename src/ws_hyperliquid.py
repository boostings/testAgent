#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, List, Tuple
import threading
import asyncio
import time
from collections import defaultdict, deque

import websockets


MAINNET_WS = "wss://api.hyperliquid.xyz/ws"
TESTNET_WS = "wss://api.hyperliquid-testnet.xyz/ws"


def _select_ws_base(network: str) -> str:
    network_norm = (network or "mainnet").strip().lower()
    if network_norm in {"testnet", "test"}:
        return os.getenv("HYPERLIQUID_TESTNET_WS", TESTNET_WS)
    return os.getenv("HYPERLIQUID_MAINNET_WS", MAINNET_WS)


class SharedSession:
    def __init__(self, network: str) -> None:
        self.network = network
        self.url = _select_ws_base(network)
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.ws = None
        self.sub_queues: Dict[str, deque] = defaultdict(lambda: deque(maxlen=200))
        self.connected = False
        self._lock = threading.Lock()
        self._reader_task = None
        self.thread.start()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _key(self, subscription: Dict[str, Any]) -> str:
        return json.dumps(subscription, sort_keys=True)

    async def _ensure_connected(self) -> None:
        if self.connected and self.ws and not self.ws.closed:
            return
        try:
            self.ws = await websockets.connect(self.url, ping_interval=20, ping_timeout=20)
            self.connected = True
            if self._reader_task is None or self._reader_task.done():
                self._reader_task = asyncio.create_task(self._reader())
        except Exception:
            self.connected = False
            await asyncio.sleep(1.0)

    async def _reader(self) -> None:
        while True:
            try:
                if not self.ws or self.ws.closed:
                    await self._ensure_connected()
                    await asyncio.sleep(0.1)
                    continue
                raw = await self.ws.recv()
                data = json.loads(raw)
                if not isinstance(data, dict):
                    continue
                # Route message by embedded subscription signature if present; else broadcast best-effort
                sub = data.get("subscription") or data.get("channel") or data.get("type")
                if isinstance(sub, dict):
                    key = self._key(sub)
                    self.sub_queues[key].append(data)
                else:
                    # best effort: push to all queues
                    for q in self.sub_queues.values():
                        q.append(data)
            except Exception:
                self.connected = False
                try:
                    if self.ws:
                        await self.ws.close()
                except Exception:
                    pass
                await asyncio.sleep(1.0)

    async def _subscribe(self, subscription: Dict[str, Any]) -> None:
        await self._ensure_connected()
        msg = {"method": "subscribe", "subscription": subscription}
        await self.ws.send(json.dumps(msg))

    def collect(self, subscription: Dict[str, Any], max_messages: int, timeout_s: float) -> List[Dict[str, Any]]:
        key = self._key(subscription)
        # Ensure subscription
        fut = asyncio.run_coroutine_threadsafe(self._subscribe(subscription), self.loop)
        try:
            fut.result(timeout=5.0)
        except Exception:
            pass
        # Collect
        out: List[Dict[str, Any]] = []
        deadline = time.time() + timeout_s
        while len(out) < max_messages and time.time() < deadline:
            q = self.sub_queues[key]
            try:
                item = q.popleft()
                out.append(item)
            except Exception:
                time.sleep(0.05)
        return out


_SESSIONS: Dict[str, SharedSession] = {}


def _get_shared_session(network: str) -> SharedSession:
    if network not in _SESSIONS:
        _SESSIONS[network] = SharedSession(network)
    return _SESSIONS[network]


def collect_subscription(
    subscription: Dict[str, Any],
    network: str = "mainnet",
    max_messages: int = 3,
    timeout_s: float = 3.0,
) -> List[Dict[str, Any]]:
    use_shared = os.getenv("HYPERLIQUID_WS_SHARED", "1") != "0"
    if use_shared:
        sess = _get_shared_session(network)
        return sess.collect(subscription, max_messages=max_messages, timeout_s=timeout_s)
    # Fallback single-use connection
    loop = asyncio.new_event_loop()
    async def _temp():
        url = _select_ws_base(network)
        msgs: List[Dict[str, Any]] = []
        async with websockets.connect(url, ping_interval=20, ping_timeout=20) as ws:
            sub = {"method": "subscribe", "subscription": subscription}
            await ws.send(json.dumps(sub))
            while len(msgs) < max_messages:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=timeout_s)
                except asyncio.TimeoutError:
                    break
                try:
                    data = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(data, dict):
                    continue
                msgs.append(data)
        return msgs
    try:
        return loop.run_until_complete(_temp())
    finally:
        loop.close()


def fetch_orderbook_snapshot(coin: str, network: str = "mainnet", depth: int = 50, timeout_s: float = 3.0) -> Dict[str, Any]:
    # Allow env-configurable timeout and message budget
    timeout_s = float(os.getenv("HYPERLIQUID_WS_TIMEOUT", str(timeout_s)))
    max_msgs = int(os.getenv("HYPERLIQUID_WS_OB_MSGS", "5"))
    # Try multiple channel variants for robustness
    variants = [
        {"type": "l2Book", "coin": coin},
        {"type": "book", "coin": coin},
        {"type": "l2book", "coin": coin},
    ]
    ob = {}
    msgs: List[Dict[str, Any]] = []
    for sub in variants:
        try:
            msgs = collect_subscription(sub, network=network, max_messages=max_msgs, timeout_s=timeout_s)
            # Pick the most recent message that looks like a book update
            for m in reversed(msgs or []):
                try:
                    candidate = m.get("data") if isinstance(m, dict) else None
                    if isinstance(candidate, dict) and isinstance(candidate.get("bids"), list) and isinstance(candidate.get("asks"), list):
                        ob = m
                        break
                except Exception:
                    continue
            if ob:
                break
        except Exception:
            continue
    if not ob and msgs:
        ob = msgs[-1]
    # Normalize a few common shapes
    bids: List[Tuple[float, float]] = []
    asks: List[Tuple[float, float]] = []
    if isinstance(ob, dict):
        book = ob.get("data") or ob
        b = book.get("bids") if isinstance(book, dict) else None
        a = book.get("asks") if isinstance(book, dict) else None
        if isinstance(b, list) and isinstance(a, list):
            for row in b[:depth]:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    try:
                        bids.append((float(row[0]), float(row[1])))
                    except Exception:
                        continue
            for row in a[:depth]:
                if isinstance(row, (list, tuple)) and len(row) >= 2:
                    try:
                        asks.append((float(row[0]), float(row[1])))
                    except Exception:
                        continue
    return {"bids": bids, "asks": asks}


def fetch_recent_trades(coin: str, network: str = "mainnet", max_messages: int = 5, timeout_s: float = 3.0) -> List[Dict[str, Any]]:
    timeout_s = float(os.getenv("HYPERLIQUID_WS_TIMEOUT", str(timeout_s)))
    return collect_subscription({"type": "trades", "coin": coin}, network=network, max_messages=max_messages, timeout_s=timeout_s)



if __name__ == "__main__":
    import argparse
    import pprint

    parser = argparse.ArgumentParser(description="Hyperliquid WS test client")
    parser.add_argument("--coin", default="BTC", help="Coin symbol, e.g., BTC")
    parser.add_argument("--network", default="mainnet", choices=["mainnet", "testnet"], help="Network")
    parser.add_argument("--mode", default="orderbook", choices=["orderbook", "trades"], help="Subscription mode")
    parser.add_argument("--depth", type=int, default=50, help="Orderbook depth")
    parser.add_argument("--timeout", type=float, default=float(os.getenv("HYPERLIQUID_WS_TIMEOUT", "4")), help="Collect timeout seconds")
    parser.add_argument("--messages", type=int, default=int(os.getenv("HYPERLIQUID_WS_OB_MSGS", "5")), help="Max messages to collect")
    args = parser.parse_args()

    if args.mode == "orderbook":
        ob = fetch_orderbook_snapshot(coin=args.coin, network=args.network, depth=args.depth, timeout_s=args.timeout)
        print("Orderbook (top):")
        print({"bids": ob.get("bids", [])[:5], "asks": ob.get("asks", [])[:5]})
    else:
        msgs = collect_subscription({"type": "trades", "coin": args.coin}, network=args.network, max_messages=args.messages, timeout_s=args.timeout)
        print(f"Trades ({len(msgs)}):")
        for m in msgs[-5:]:
            try:
                d = m.get("data") or {}
                if isinstance(d, list) and d:
                    d = d[-1]
                print({"px": d.get("px"), "sz": d.get("sz"), "side": d.get("side")})
            except Exception:
                pprint.pprint(m)

