#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MCP server exposing Hyperliquid public Info API as tools.

Endpoints implemented (via POST /info):
- perpDexs
- meta
- metaAndAssetCtxs
- clearinghouseState
- userFunding
- userNonFundingLedgerUpdates
- fundingHistory
- predictedFundings
- perpsAtOpenInterestCap
- perpDeployAuctionStatus
- activeAssetData
- perpDexLimits

Usage:
    python mcp_hyperliquid.py

Then connect an MCP-compatible client via stdio using this command.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional, List, Tuple

import requests
from mcp.server.fastmcp import FastMCP
from ws_hyperliquid import fetch_orderbook_snapshot, fetch_recent_trades


MAINNET_INFO = "https://api.hyperliquid.xyz/info"
TESTNET_INFO = "https://api.hyperliquid-testnet.xyz/info"


def _select_info_base(network: str) -> str:
    network_norm = (network or "mainnet").strip().lower()
    if network_norm in {"testnet", "test"}:
        return os.getenv("HYPERLIQUID_TESTNET_INFO", TESTNET_INFO)
    return os.getenv("HYPERLIQUID_MAINNET_INFO", MAINNET_INFO)


_METRICS = {"info_calls": 0, "info_errors": 0}


def _post_info(payload: Dict[str, Any], network: str) -> Any:
    url = _select_info_base(network)
    # Allow override of timeout via env
    timeout_s = float(os.getenv("HYPERLIQUID_HTTP_TIMEOUT", "20"))
    headers = {"Content-Type": "application/json"}
    _METRICS["info_calls"] += 1
    resp = requests.post(url, json=payload, headers=headers, timeout=timeout_s)
    try:
        resp.raise_for_status()
    except requests.HTTPError as e:
        # Attach body for easier debugging in client
        _METRICS["info_errors"] += 1
        raise RuntimeError(f"Hyperliquid info request failed: {e}; body={resp.text}") from e
    try:
        return resp.json()
    except Exception as e:
        _METRICS["info_errors"] += 1
        raise RuntimeError(f"Failed to parse JSON from Hyperliquid: {e}; body={resp.text[:512]}") from e


mcp = FastMCP("hyperliquid-info")


@mcp.tool()
def info_raw(payload: Dict[str, Any], network: str = "mainnet") -> Dict[str, Any]:
    """Call Hyperliquid /info with an arbitrary payload.

    - payload: JSON body to POST (must include key 'type')
    - network: 'mainnet' (default) or 'testnet'
    """
    if not isinstance(payload, dict) or "type" not in payload:
        raise ValueError("payload must be an object and include a 'type' field")
    data = _post_info(payload, network)
    return {"ok": True, "type": payload.get("type"), "data": data}


@mcp.tool()
def get_perp_dexs(network: str = "mainnet") -> Dict[str, Any]:
    """List perpetual DEXs (type=perpDexs)."""
    data = _post_info({"type": "perpDexs"}, network)
    summary = f"{len(data) if isinstance(data, list) else 0} entries"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_meta(dex: str = "", network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve perpetuals metadata (type=meta)."""
    payload = {"type": "meta"}
    if dex:
        payload["dex"] = dex
    data = _post_info(payload, network)
    uni = data.get("universe", []) if isinstance(data, dict) else []
    summary = f"{len(uni)} assets in universe"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_meta_and_asset_ctxs(network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve perpetuals asset contexts (type=metaAndAssetCtxs)."""
    data = _post_info({"type": "metaAndAssetCtxs"}, network)
    uni = data[0].get("universe", []) if isinstance(data, list) and data and isinstance(data[0], dict) else []
    ctxs = data[1] if isinstance(data, list) and len(data) > 1 else []
    summary = f"universe {len(uni)} / ctxs {len(ctxs)}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_clearinghouse_state(user: str, dex: str = "", network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve user's perpetuals account summary (type=clearinghouseState).

    - user: 42-char hex address, e.g., 0x...
    - dex: perp dex name (optional)
    """
    if not isinstance(user, str) or not user.startswith("0x"):
        raise ValueError("user must be a 0x-prefixed address string")
    payload = {"type": "clearinghouseState", "user": user}
    if dex:
        payload["dex"] = dex
    data = _post_info(payload, network)
    ms = data.get("marginSummary", {}) if isinstance(data, dict) else {}
    positions = data.get("assetPositions", []) if isinstance(data, dict) else []
    summary = f"acct {ms.get('accountValue')} ntl {ms.get('totalNtlPos')} pos {len(positions)}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_user_funding(user: str, startTime: int, endTime: Optional[int] = None, network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve user's funding history (type=userFunding).

    - startTime/endTime in milliseconds; endTime optional (defaults to now)
    """
    payload: Dict[str, Any] = {"type": "userFunding", "user": user, "startTime": int(startTime)}
    if endTime is not None:
        payload["endTime"] = int(endTime)
    data = _post_info(payload, network)
    summary = f"events {len(data) if isinstance(data, list) else 0}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_user_non_funding_ledger_updates(user: str, startTime: int, endTime: Optional[int] = None, network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve user's non-funding ledger updates (type=userNonFundingLedgerUpdates)."""
    payload: Dict[str, Any] = {
        "type": "userNonFundingLedgerUpdates",
        "user": user,
        "startTime": int(startTime),
    }
    if endTime is not None:
        payload["endTime"] = int(endTime)
    data = _post_info(payload, network)
    summary = f"events {len(data) if isinstance(data, list) else 0}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_funding_history(coin: str, startTime: int, endTime: Optional[int] = None, network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve historical funding rates (type=fundingHistory)."""
    payload: Dict[str, Any] = {"type": "fundingHistory", "coin": coin, "startTime": int(startTime)}
    if endTime is not None:
        payload["endTime"] = int(endTime)
    data = _post_info(payload, network)
    summary = f"points {len(data) if isinstance(data, list) else 0}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_predicted_fundings(network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve predicted funding rates for different venues (type=predictedFundings)."""
    data = _post_info({"type": "predictedFundings"}, network)
    summary = f"coins {len(data) if isinstance(data, list) else 0}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_perps_at_open_interest_cap(network: str = "mainnet") -> Dict[str, Any]:
    """Query perps at open interest caps (type=perpsAtOpenInterestCap)."""
    data = _post_info({"type": "perpsAtOpenInterestCap"}, network)
    summary = ", ".join(data[:5]) + ("..." if isinstance(data, list) and len(data) > 5 else "") if isinstance(data, list) else ""
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_perp_deploy_auction_status(network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve information about the Perp Deploy Auction (type=perpDeployAuctionStatus)."""
    data = _post_info({"type": "perpDeployAuctionStatus"}, network)
    summary = f"start {data.get('startTimeSeconds')} dur {data.get('durationSeconds')}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_active_asset_data(user: str, coin: str, network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve User's Active Asset Data (type=activeAssetData)."""
    if not isinstance(user, str) or not user.startswith("0x"):
        raise ValueError("user must be a 0x-prefixed address string")
    payload = {"type": "activeAssetData", "user": user, "coin": coin}
    data = _post_info(payload, network)
    lev = data.get("leverage", {}) if isinstance(data, dict) else {}
    summary = f"lev {lev.get('type')}/{lev.get('value')} mark {data.get('markPx')}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_perp_dex_limits(dex: str, network: str = "mainnet") -> Dict[str, Any]:
    """Retrieve Builder-Deployed Perp Market Limits (type=perpDexLimits)."""
    if not dex:
        raise ValueError("dex must be a non-empty string")
    payload = {"type": "perpDexLimits", "dex": dex}
    data = _post_info(payload, network)
    summary = f"oiCap {data.get('totalOiCap')} perPerp {data.get('oiSzCapPerPerp')}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def server_time_ms() -> Dict[str, int]:
    """Return server time in milliseconds (utility)."""
    return {"timeMs": int(time.time() * 1000)}


@mcp.tool()
def get_orderbook(coin: str, network: str = "mainnet", depth: int = 50) -> Dict[str, Any]:
    """Fetch current orderbook snapshot via WS l2Book subscription."""
    data = fetch_orderbook_snapshot(coin=coin, network=network, depth=depth)
    topb = data.get("bids", [[]])
    topa = data.get("asks", [[]])
    bb = topb[0][0] if topb and topb[0] else None
    ba = topa[0][0] if topa and topa[0] else None
    summary = f"bb {bb} ba {ba} levels {len(data.get('bids', []))}/{len(data.get('asks', []))}"
    return {"ok": True, "data": data, "summary": summary}


@mcp.tool()
def get_recent_trades(coin: str, network: str = "mainnet", maxMessages: int = 5) -> Dict[str, Any]:
    """Fetch recent trades via WS trades subscription."""
    data = fetch_recent_trades(coin=coin, network=network, max_messages=maxMessages)
    latest = None
    try:
        row = (data[-1].get('data') or data[-1]) if data else {}
        latest = row.get('px') or row.get('price')
    except Exception:
        latest = None
    summary = f"trades {len(data)} last {latest}"
    return {"ok": True, "data": data, "summary": summary}


############################
# Caching and analytics
############################

_CACHE: Dict[str, Dict[str, Any]] = {}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _get_cache(key: str) -> Optional[Dict[str, Any]]:
    entry = _CACHE.get(key)
    if not entry:
        return None
    ttl_ms = entry.get("ttlMs", 0)
    if _now_ms() - entry.get("ts", 0) > ttl_ms:
        return None
    return entry.get("value")


def _set_cache(key: str, value: Any, ttl_ms: int) -> None:
    _CACHE[key] = {"value": value, "ts": _now_ms(), "ttlMs": ttl_ms}


def _meta_ctxs_cached(network: str) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    ttl_sec = float(os.getenv("HYPERLIQUID_CTXS_TTL", "5"))
    ck = f"ctxs:{network}"
    cached = _get_cache(ck)
    if cached is not None:
        return cached[0], cached[1]
    data = _post_info({"type": "metaAndAssetCtxs"}, network)
    universe_obj, ctxs = data[0], data[1]
    _set_cache(ck, (universe_obj, ctxs), int(ttl_sec * 1000))
    return universe_obj, ctxs


def _orderbook_cached(coin: str, network: str, depth: int) -> Dict[str, Any]:
    ttl_sec = float(os.getenv("HYPERLIQUID_OB_TTL", "2"))
    ck = f"ob:{network}:{coin}:{depth}"
    cached = _get_cache(ck)
    if cached is not None:
        return cached
    ob = fetch_orderbook_snapshot(coin=coin, network=network, depth=depth, timeout_s=float(os.getenv("HYPERLIQUID_WS_TIMEOUT", "6")))
    _set_cache(ck, ob, int(ttl_sec * 1000))
    return ob


def _trades_cached(coin: str, network: str, limit: int) -> List[Dict[str, Any]]:
    ttl_sec = float(os.getenv("HYPERLIQUID_TRADES_TTL", "2"))
    ck = f"trades:{network}:{coin}:{limit}"
    cached = _get_cache(ck)
    if cached is not None:
        return cached
    tr = fetch_recent_trades(coin=coin, network=network, max_messages=limit, timeout_s=float(os.getenv("HYPERLIQUID_WS_TIMEOUT", "6")))
    _set_cache(ck, tr, int(ttl_sec * 1000))
    return tr


def _compute_orderbook_metrics(ob: Dict[str, Any]) -> Dict[str, Any]:
    bids: List[Tuple[float, float]] = ob.get("bids", []) or []
    asks: List[Tuple[float, float]] = ob.get("asks", []) or []
    best_bid = bids[0][0] if bids else None
    best_ask = asks[0][0] if asks else None
    mid = (best_bid + best_ask) / 2.0 if best_bid and best_ask else (best_bid or best_ask)
    spread = (best_ask - best_bid) if (best_ask and best_bid) else None
    spread_bps = (spread / mid * 10000.0) if (spread and mid) else None
    def sum_sz(levels: List[Tuple[float, float]], n: int) -> float:
        return float(sum(sz for _, sz in levels[:n])) if levels else 0.0
    topN = 10
    bid_sz = sum_sz(bids, topN)
    ask_sz = sum_sz(asks, topN)
    total = bid_sz + ask_sz
    imbalance = ((bid_sz - ask_sz) / total) if total > 0 else 0.0
    return {
        "mid": mid,
        "spread": spread,
        "spreadBps": spread_bps,
        "tobVolumes": {"bid": bids[0][1] if bids else 0.0, "ask": asks[0][1] if asks else 0.0},
        "depth": {"bidTopN": bid_sz, "askTopN": ask_sz, "levels": topN},
        "imbalance": imbalance,
    }


def _compute_trades_metrics(trades: List[Dict[str, Any]], ref_mid: Optional[float]) -> Dict[str, Any]:
    prices: List[float] = []
    sizes: List[float] = []
    buys = 0
    sells = 0
    for t in trades:
        d = t.get("data") if isinstance(t, dict) else None
        row = d or t
        px = row.get("px") or row.get("price")
        sz = row.get("sz") or row.get("size")
        side = row.get("side") or row.get("aggressor")
        try:
            if px is not None and sz is not None:
                pxf = float(px)
                szf = float(sz)
                prices.append(pxf)
                sizes.append(szf)
                if side in ("buy", "Buy", "b"):
                    buys += 1
                elif side in ("sell", "Sell", "s"):
                    sells += 1
        except Exception:
            continue
    notional = sum(p * s for p, s in zip(prices, sizes))
    vol = sum(sizes)
    vwap = (notional / vol) if vol > 0 else None
    trade_imb = ((buys - sells) / max(buys + sells, 1))
    vwap_drift = ((vwap - ref_mid) / ref_mid) if (vwap and ref_mid) else None
    return {"vwap": vwap, "tradeImbalance": trade_imb, "vwapDrift": vwap_drift, "count": buys + sells}


def _score_signal(features: Dict[str, Any]) -> Dict[str, Any]:
    # Normalize features and compute a simple weighted score
    score = 0.0
    reasons: List[str] = []
    imb = features.get("obImbalance") or 0.0
    score += 0.5 * float(imb)
    if abs(imb) > 0.05:
        reasons.append(f"orderbook imbalance {imb:.2f}")
    drift = features.get("vwapDrift")
    if isinstance(drift, (int, float)):
        score += 0.3 * float(drift) * 10.0  # scale drift
        reasons.append(f"vwap drift {float(drift)*100:.2f}%")
    funding = features.get("funding")
    if funding is not None:
        try:
            f = float(funding)
            score += 0.2 * (-f)  # negative funding (shorts pay) is bullish
            reasons.append(f"funding {f}")
        except Exception:
            pass
    theta = float(os.getenv("HYPERLIQUID_SIGNAL_THETA", "0.15"))
    label = "neutral"
    if score > theta:
        label = "buy"
    elif score < -theta:
        label = "sell"
    confidence = min(0.99, max(0.0, abs(score)))
    return {"label": label, "score": round(score, 3), "confidence": round(confidence, 3), "reasons": reasons[:4]}


@mcp.tool()
def get_full_market_picture(
    coin: str,
    network: str = "mainnet",
    depth: int = 50,
    trades: int = 30,
) -> Dict[str, Any]:
    """Return fused Info + WS snapshot, analytics, and a rule-based signal for a coin."""
    flags: List[str] = []
    # Info context
    try:
        universe_obj, ctxs = _meta_ctxs_cached(network)
    except Exception as e:
        universe_obj, ctxs = ({"universe": []}, [])
        flags.append(f"ctxs_error:{e}")
    # Map coin -> index
    uni = universe_obj.get("universe", []) if isinstance(universe_obj, dict) else []
    name_to_idx = {a.get("name"): i for i, a in enumerate(uni) if isinstance(a, dict) and "name" in a}
    idx = name_to_idx.get(coin)
    info_slice: Dict[str, Any] = {}
    if idx is not None and idx < len(ctxs):
        c = ctxs[idx]
        if isinstance(c, dict):
            info_slice = c
    # WS data
    try:
        ob = _orderbook_cached(coin, network, depth)
    except Exception as e:
        ob = {"bids": [], "asks": []}
        flags.append(f"ob_error:{e}")
    try:
        tr = _trades_cached(coin, network, trades)
    except Exception as e:
        tr = []
        flags.append(f"trades_error:{e}")
    # Analytics
    obm = _compute_orderbook_metrics(ob)
    trm = _compute_trades_metrics(tr, obm.get("mid"))
    # Assemble snapshot
    market_snapshot = {
        "mid": obm.get("mid"),
        "spread": obm.get("spread"),
        "spreadBps": obm.get("spreadBps"),
        "tobVolumes": obm.get("tobVolumes"),
        "depth": obm.get("depth"),
        "funding": info_slice.get("funding"),
        "premium": info_slice.get("premium"),
        "OI": info_slice.get("openInterest"),
        "vol24h": info_slice.get("dayNtlVlm"),
    }
    analytics = {
        "imbalance": obm.get("imbalance"),
        "vwap": trm.get("vwap"),
        "vwapDrift": trm.get("vwapDrift"),
        "tradeImbalance": trm.get("tradeImbalance"),
        "tradeCount": trm.get("count"),
    }
    signal = _score_signal({
        "obImbalance": analytics.get("imbalance"),
        "vwapDrift": analytics.get("vwapDrift"),
        "funding": market_snapshot.get("funding"),
    })
    raw_slices = {"orderbookTopN": {"bids": ob.get("bids"), "asks": ob.get("asks")}, "recentTradesM": tr}
    response = {
        "coin": coin,
        "ts": _now_ms(),
        "marketSnapshot": market_snapshot,
        "rawSlices": raw_slices,
        "analytics": analytics,
        "signal": signal,
        "meta": {"network": network, "sources": ["Info", "WS"], "ttlHints": {"ctxsSec": os.getenv("HYPERLIQUID_CTXS_TTL", "5"), "wsSec": os.getenv("HYPERLIQUID_OB_TTL", "2")}, "flags": flags},
    }
    return response


############################
# Advanced analytics tools
############################


def _consume_depth(ob: Dict[str, Any], side: str, notional: float) -> Tuple[float, float]:
    levels: List[Tuple[float, float]] = (ob.get("asks") if side == "buy" else ob.get("bids")) or []
    remaining = float(notional)
    cost = 0.0
    filled = 0.0
    for px, sz in (levels if side == "buy" else levels):
        # For buy, levels are asks sorted low->high; for sell, bids high->low (assumed)
        take = min(remaining / max(px, 1e-9), float(sz))
        if take <= 0:
            continue
        cost += take * px
        filled += take
        remaining -= take * px
        if remaining <= 1e-9:
            break
    return cost, filled


@mcp.tool()
def get_slippage(coin: str, side: str, notionalUsd: float, network: str = "mainnet", depth: int = 100) -> Dict[str, Any]:
    """Estimate slippage (bps) and avg fill price for a USD notional using orderbook depth."""
    ob = _orderbook_cached(coin, network, depth)
    obm = _compute_orderbook_metrics(ob)
    mid = obm.get("mid")
    if not isinstance(mid, (int, float)) or mid is None:
        return {"ok": False, "error": "No mid price"}
    side_norm = side.lower()
    if side_norm not in ("buy", "sell"):
        return {"ok": False, "error": "side must be 'buy' or 'sell'"}
    cost, filled = _consume_depth(ob, side_norm, float(notionalUsd))
    if filled <= 0:
        return {"ok": False, "error": "Insufficient depth"}
    avg_px = cost / filled
    slippage_bps = (avg_px - mid) / mid * 10000.0 if side_norm == "buy" else (mid - avg_px) / mid * 10000.0
    return {"ok": True, "avgPx": avg_px, "slippageBps": slippage_bps, "filledUnits": filled, "summary": f"avg {avg_px:.4f} slip {slippage_bps:.2f}bps"}


@mcp.tool()
def get_liquidity_profile(coin: str, network: str = "mainnet", depth: int = 100) -> Dict[str, Any]:
    """Return cumulative depth at each of top-N levels for bids and asks."""
    ob = _orderbook_cached(coin, network, depth)
    bids: List[Tuple[float, float]] = ob.get("bids", []) or []
    asks: List[Tuple[float, float]] = ob.get("asks", []) or []
    def cumul(levels: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
        out: List[Tuple[float, float]] = []
        acc = 0.0
        for px, sz in levels:
            acc += float(sz)
            out.append((float(px), acc))
        return out
    return {"ok": True, "bid": cumul(bids), "ask": cumul(asks), "summary": f"levels {len(bids)}/{len(asks)}"}


@mcp.tool()
def get_volatility_metrics(coin: str, network: str = "mainnet", trades: int = 200) -> Dict[str, Any]:
    """Compute realized volatility from recent trades; ATR is omitted if candles are unavailable."""
    tr = _trades_cached(coin, network, trades)
    prices: List[float] = []
    for t in tr:
        d = t.get("data") if isinstance(t, dict) else None
        row = d or t
        px = row.get("px") or row.get("price")
        try:
            prices.append(float(px))
        except Exception:
            continue
    rets: List[float] = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0:
            rets.append((prices[i] - prices[i-1]) / prices[i-1])
    import math
    vol = math.sqrt(252) * (sum(r*r for r in rets) / max(len(rets), 1))**0.5 if rets else 0.0
    return {"ok": True, "realizedVol": vol, "atr": None, "summary": f"realizedVol {vol:.4f}"}


@mcp.tool()
def get_trend_ma(coin: str, network: str = "mainnet", short: int = 20, long: int = 50) -> Dict[str, Any]:
    """Compute simple moving averages from recent trades; returns cross signal."""
    tr = _trades_cached(coin, network, max(long*5, 200))
    prices: List[float] = []
    for t in tr:
        d = t.get("data") if isinstance(t, dict) else None
        row = d or t
        px = row.get("px") or row.get("price")
        try:
            prices.append(float(px))
        except Exception:
            continue
    def sma(n: int) -> Optional[float]:
        return (sum(prices[-n:]) / n) if len(prices) >= n else None
    s = sma(short)
    l = sma(long)
    cross = "bullish" if (s and l and s > l) else ("bearish" if (s and l and s < l) else "neutral")
    return {"ok": True, "smaShort": s, "smaLong": l, "cross": cross, "summary": f"{cross}: {short}/{long}"}


@mcp.tool()
def get_premium_monitor(coin: str, network: str = "mainnet") -> Dict[str, Any]:
    """Return current premium (mark vs oracle) and funding; z-score omitted without history."""
    _, ctxs = _meta_ctxs_cached(network)
    # build coin map
    # We don't cache name map here; small overhead
    uni, _ = _meta_ctxs_cached(network)
    universe = uni.get("universe", []) if isinstance(uni, dict) else []
    name_to_idx = {a.get("name"): i for i, a in enumerate(universe) if isinstance(a, dict) and "name" in a}
    idx = name_to_idx.get(coin)
    cur = ctxs[idx] if idx is not None and idx < len(ctxs) else {}
    return {"ok": True, "premium": cur.get("premium"), "funding": cur.get("funding"), "zScore": None, "summary": f"prem {cur.get('premium')} fund {cur.get('funding')}"}


@mcp.tool()
def get_oi_trend(coin: str, network: str = "mainnet") -> Dict[str, Any]:
    """Compute open-interest delta vs last cached snapshot."""
    key = f"oi_hist:{network}:{coin}"
    prev = _get_cache(key)
    uni, ctxs = _meta_ctxs_cached(network)
    universe = uni.get("universe", []) if isinstance(uni, dict) else []
    name_to_idx = {a.get("name"): i for i, a in enumerate(universe) if isinstance(a, dict) and "name" in a}
    idx = name_to_idx.get(coin)
    cur = ctxs[idx] if idx is not None and idx < len(ctxs) else {}
    cur_oi = float(cur.get("openInterest", 0.0)) if isinstance(cur.get("openInterest"), (int, float, str)) else 0.0
    _set_cache(key, cur_oi, 60_000)  # keep last for 60s
    delta = None if prev is None else (cur_oi - float(prev))
    return {"ok": True, "openInterest": cur_oi, "delta": delta, "summary": f"OI {cur_oi} Δ {delta}"}


@mcp.tool()
def get_user_pnl_summary(user: str, network: str = "mainnet", days: int = 1) -> Dict[str, Any]:
    """Summarize user performance using funding over window and current unrealized PnL."""
    if not isinstance(user, str) or not user.startswith("0x"):
        return {"ok": False, "error": "user must be 0x address"}
    now_ms = _now_ms()
    start = now_ms - max(1, int(days)) * 24 * 60 * 60 * 1000
    try:
        ch = get_clearinghouse_state(user=user, network=network)["data"]
    except Exception as e:
        ch = {}
    unreal = 0.0
    try:
        for p in ch.get("assetPositions", []):
            unreal += float(p.get("position", {}).get("unrealizedPnl", 0.0))
    except Exception:
        pass
    try:
        uf = get_user_funding(user=user, startTime=start, endTime=now_ms, network=network)["data"]
        funding_pnl = sum(float(x.get("delta", {}).get("usdc", 0.0)) for x in uf)
    except Exception:
        funding_pnl = None
    return {"ok": True, "unrealizedPnl": unreal, "fundingPnl": funding_pnl, "windowDays": days, "summary": f"unreal {unreal} funding {funding_pnl}"}


@mcp.tool()
def get_batch_full_market_picture(coins: List[str], network: str = "mainnet", depth: int = 30, trades: int = 30) -> Dict[str, Any]:
    """Batch get_full_market_picture for a list of coins."""
    out: Dict[str, Any] = {}
    for c in coins:
        try:
            out[c] = get_full_market_picture(c, network=network, depth=depth, trades=trades)
        except Exception as e:
            out[c] = {"error": str(e)}
    return {"ok": True, "data": out, "summary": f"coins {len(out)}"}


@mcp.tool()
def get_metrics() -> Dict[str, Any]:
    """Return basic telemetry counters for info calls/errors."""
    return {"ok": True, "metrics": dict(_METRICS), "summary": f"info calls {_METRICS['info_calls']} errors {_METRICS['info_errors']}"}

if __name__ == "__main__":
    mcp.run()


