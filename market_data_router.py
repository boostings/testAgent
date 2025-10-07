#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
from typing import Dict, List, Tuple
import re as _re
import time as _time

try:
    # Reuse the server's lightweight wrappers to the Info and WS
    import mcp_hyperliquid as hl
except Exception as e:  # pragma: no cover
    hl = None  # type: ignore


_TICKER_RE = re.compile(r"(?<![A-Za-z0-9_])\$([A-Z]{2,10})\b")


def extract_tickers(text: str) -> List[str]:
    matches = _TICKER_RE.findall(text.upper())
    # Deduplicate while preserving order
    seen: set[str] = set()
    ordered: List[str] = []
    for t in matches:
        if t not in seen:
            seen.add(t)
            ordered.append(t)
    return ordered


_ETH_ADDR_RE = _re.compile(r"\b0x[a-fA-F0-9]{40}\b")


def extract_eth_addresses(text: str) -> List[str]:
    return _ETH_ADDR_RE.findall(text)


def _contains_all(text: str, needles: List[str]) -> bool:
    t = text.lower()
    return all(n in t for n in needles)


def _contains_any(text: str, needles: List[str]) -> bool:
    t = text.lower()
    return any(n in t for n in needles)


def _load_universe_and_ctxs(network: str) -> Tuple[List[Dict], List[Dict]]:
    if hl is None:
        raise RuntimeError("mcp_hyperliquid module not available")
    resp = hl.get_meta_and_asset_ctxs(network=network)
    data = resp.get("data")
    if not isinstance(data, list) or len(data) != 2:
        raise RuntimeError("Unexpected metaAndAssetCtxs response structure")
    universe_obj, ctxs = data[0], data[1]
    universe = universe_obj.get("universe", []) if isinstance(universe_obj, dict) else []
    if not isinstance(universe, list) or not isinstance(ctxs, list):
        raise RuntimeError("Malformed metaAndAssetCtxs data")
    return universe, ctxs


def _orderbook_imbalance(bids: list[tuple[float, float]], asks: list[tuple[float, float]]) -> float:
    bid_vol = sum(sz for _, sz in bids[:20]) if bids else 0.0
    ask_vol = sum(sz for _, sz in asks[:20]) if asks else 0.0
    total = bid_vol + ask_vol
    if total <= 0:
        return 0.0
    return (bid_vol - ask_vol) / total


def get_market_data_summary(prompt: str, network: str = "mainnet") -> str:
    tickers = extract_tickers(prompt)
    if not tickers:
        # If no tickers, but an address is present, always fetch account summary
        addrs = extract_eth_addresses(prompt)
        if addrs and hl is not None:
            addr = addrs[0]
            try:
                ch = hl.get_clearinghouse_state(user=addr, network=network).get("data", {})
                ms = ch.get("marginSummary", {}) if isinstance(ch, dict) else {}
                positions = ch.get("assetPositions", []) if isinstance(ch, dict) else []
                pnl = None
                try:
                    # sum unrealized pnl over positions if present
                    pnl = sum(float(p.get("position", {}).get("unrealizedPnl", 0.0)) for p in positions if isinstance(p, dict))
                except Exception:
                    pnl = None
                ntl = ms.get("totalNtlPos")
                av = ms.get("accountValue")
                return f"Wallet {addr} — AccountValue {av}, NtlPos {ntl}, UnrealizedPnL {pnl if pnl is not None else 'n/a'}"
            except Exception:
                return ""
        # No address: support global intents without tickers (OI caps, predicted funding overview)
        if hl is not None:
            # OI caps
            if _contains_any(prompt, ["oi cap", "open interest cap"]):
                try:
                    caps = hl.get_perps_at_open_interest_cap(network=network).get("data", [])
                    if isinstance(caps, list):
                        head = ", ".join(caps[:20]) + ("..." if len(caps) > 20 else "")
                        return f"Perps at OI cap: {head if head else 'none'}"
                except Exception:
                    pass
            # Predicted funding (overview)
            if _contains_any(prompt, ["predicted funding", "predicted rates", "predicted fundings"]):
                try:
                    pf = hl.get_predicted_fundings(network=network).get("data", [])
                    if isinstance(pf, list) and pf:
                        coins = [e[0] for e in pf if isinstance(e, list) and e]
                        head = ", ".join(coins[:15]) + ("..." if len(coins) > 15 else "")
                        return f"Predicted funding available for: {head}"
                except Exception:
                    pass
        return ""
    try:
        universe, ctxs = _load_universe_and_ctxs(network)
        # Build name->index map
        name_to_idx = {a.get("name"): i for i, a in enumerate(universe) if isinstance(a, dict) and "name" in a}
        lines: List[str] = ["Market data (Hyperliquid):"]
        for t in tickers:
            # Intent: average funding rate for coin
            if _contains_all(prompt, ["average", "funding"]) and hl is not None:
                try:
                    now_ms = int(_time.time() * 1000)
                    days = 7 if "week" in prompt.lower() else 1
                    start_ms = now_ms - days * 24 * 60 * 60 * 1000
                    fh = hl.get_funding_history(coin=t, startTime=start_ms, endTime=now_ms, network=network).get("data", [])
                    vals: List[float] = []
                    for row in fh:
                        try:
                            vals.append(float(row.get("fundingRate")))
                        except Exception:
                            continue
                    if vals:
                        avg = sum(vals) / len(vals)
                        return f"Avg funding ({days}d) for {t}: {avg:.6f}"
                except Exception:
                    pass

            # Intent: predicted funding rates
            if _contains_any(prompt, ["predicted funding", "predicted rates"]) and hl is not None:
                try:
                    pf = hl.get_predicted_fundings(network=network).get("data", [])
                    # pf is list of [coin, [[venue, {fundingRate, nextFundingTime}], ...]]
                    per_coin = None
                    for entry in pf:
                        if isinstance(entry, list) and entry and entry[0] == t:
                            per_coin = entry[1]
                            break
                    if per_coin:
                        parts: List[str] = []
                        for venue, meta in per_coin:
                            try:
                                parts.append(f"{venue}:{meta.get('fundingRate')}")
                            except Exception:
                                continue
                        if parts:
                            return f"Predicted funding for {t}: " + ", ".join(parts)
                except Exception:
                    pass

            # Intent: tickers at OI cap
            if _contains_any(prompt, ["oi cap", "open interest cap"]) and hl is not None:
                try:
                    caps = hl.get_perps_at_open_interest_cap(network=network).get("data", [])
                    if isinstance(caps, list) and caps:
                        return "Perps at OI cap: " + ", ".join(caps)
                except Exception:
                    pass

            # Intent: active asset data with user + coin
            addrs = extract_eth_addresses(prompt)
            if addrs and _contains_any(prompt, ["active asset", "available to trade", "max trade"]) and hl is not None:
                try:
                    a = hl.get_active_asset_data(user=addrs[0], coin=t, network=network).get("data", {})
                    lev = a.get("leverage", {}) if isinstance(a, dict) else {}
                    at = a.get("availableToTrade")
                    msz = a.get("maxTradeSzs")
                    mp = a.get("markPx")
                    return f"Active asset {t} for {addrs[0]} — lev {lev.get('type')}/{lev.get('value')}, avail {at}, maxSz {msz}, mark {mp}"
                except Exception:
                    pass
            idx = name_to_idx.get(t)
            if idx is None or idx >= len(ctxs):
                lines.append(f"- {t}: not found")
                continue
            c = ctxs[idx]
            # Common fields per docs: markPx, oraclePx, funding, openInterest, midPx, dayNtlVlm
            mark = c.get("markPx")
            oracle = c.get("oraclePx")
            funding = c.get("funding")
            oi = c.get("openInterest")
            vlm = c.get("dayNtlVlm")
            prem = c.get("premium")
            # Perp asset context intent (explicit)
            if _contains_any(prompt, ["asset context", "funding", "open interest", "mark price", "premium"]):
                # always include basic context
                pass

            try:
                full = hl.get_full_market_picture(coin=t, network=network, depth=50, trades=30)
                sig = full.get("signal", {})
                imb = full.get("analytics", {}).get("imbalance")
                lines.append(
                    f"- {t}: mark {mark}, oracle {oracle}, funding {funding}, OI {oi}, vol {vlm}, prem {prem}, obImb {imb:.2f if isinstance(imb, (int,float)) else 'n/a'}, signal {sig.get('label')} ({sig.get('score')})"
                )
            except Exception:
                ob = {}
                try:
                    ob = hl.get_orderbook(coin=t, network=network, depth=50).get("data", {})
                except Exception:
                    ob = {}
                bids = ob.get("bids", []) if isinstance(ob, dict) else []
                asks = ob.get("asks", []) if isinstance(ob, dict) else []
                imb = _orderbook_imbalance(bids, asks)
                signal = "buy" if imb > 0.1 else ("sell" if imb < -0.1 else "neutral")
                lines.append(
                    f"- {t}: mark {mark}, oracle {oracle}, funding {funding}, OI {oi}, vol {vlm}, prem {prem}, obImb {imb:.2f}, signal {signal}"
                )
        return "\n".join(lines)
    except Exception:
        # Fail open: do not block chat if market fetch fails
        return ""


