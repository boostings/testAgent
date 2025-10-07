#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from sentence_transformers import SentenceTransformer, util

import mcp_hyperliquid as hl


_ETH_ADDR_RE = re.compile(r"\b0x[a-fA-F0-9]{40}\b")
_TICKER_RE = re.compile(r"(?<![A-Za-z0-9_])\$([A-Z]{2,10})\b")
_PRICE_RE = re.compile(r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?)")


def _extract_tickers(text: str) -> List[str]:
    seen: set[str] = set()
    out: List[str] = []
    for t in _TICKER_RE.findall(text.upper()):
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _extract_address(text: str) -> Optional[str]:
    m = _ETH_ADDR_RE.search(text)
    return m.group(0) if m else None


def _parse_time_window_days(text: str) -> int:
    lower = text.lower()
    if any(k in lower for k in ["7d", "7 d", "week", "weekly"]):
        return 7
    if any(k in lower for k in ["30d", "30 d", "month", "monthly"]):
        return 30
    if any(k in lower for k in ["24h", "24 h", "day", "daily", "today"]):
        return 1
    return 1


def _parse_target_price(text: str) -> Optional[float]:
    lower = text.lower()
    if not any(k in lower for k in ["until", "up to", "to "]):
        return None
    m = _PRICE_RE.search(text)
    if not m:
        return None
    try:
        val = float(m.group(1).replace(",", ""))
        return val
    except Exception:
        return None


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class ToolSpec:
    name: str
    description: str
    builder: Callable[[str], Optional[Tuple[Callable[..., Any], Dict[str, Any]]]]


def _b_meta_and_ctxs(_: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    return hl.get_meta_and_asset_ctxs, {"network": "mainnet"}


def _b_full_market(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    return hl.get_full_market_picture, {"coin": tickers[0], "network": "mainnet", "depth": 50, "trades": 30}


def _b_orderbook(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    return hl.get_orderbook, {"coin": tickers[0], "network": "mainnet", "depth": 50}


def _b_trades(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    return hl.get_recent_trades, {"coin": tickers[0], "network": "mainnet", "maxMessages": 30}


def _b_funding_history(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    days = _parse_time_window_days(prompt)
    end = _now_ms()
    start = end - days * 24 * 60 * 60 * 1000
    return hl.get_funding_history, {"coin": tickers[0], "startTime": start, "endTime": end, "network": "mainnet"}


def _b_predicted_funding(_: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    return hl.get_predicted_fundings, {"network": "mainnet"}


def _b_oi_caps(_: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    return hl.get_perps_at_open_interest_cap, {"network": "mainnet"}


def _b_asks_to_price(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    tgt = _parse_target_price(prompt)
    if not tickers or tgt is None:
        return None
    # We will fetch orderbook and compute client-side
    return hl.get_orderbook, {"coin": tickers[0], "network": "mainnet", "depth": 200}


def _b_account_summary(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    addr = _extract_address(prompt)
    if not addr:
        return None
    return hl.get_clearinghouse_state, {"user": addr, "network": "mainnet"}


def _b_active_asset(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    addr = _extract_address(prompt)
    tickers = _extract_tickers(prompt)
    if not addr or not tickers:
        return None
    return hl.get_active_asset_data, {"user": addr, "coin": tickers[0], "network": "mainnet"}


def _b_slippage(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    side = "buy" if "buy" in prompt.lower() else ("sell" if "sell" in prompt.lower() else "buy")
    # rough notional guess if present
    m = re.search(r"\b(\d{2,9})(?:\s?USD|\s?usdc|\s?usd|\s?\$)\b", prompt.lower())
    notional = float(m.group(1)) if m else 10000.0
    return hl.get_slippage, {"coin": tickers[0], "side": side, "notionalUsd": notional, "network": "mainnet", "depth": 100}


def _b_user_pnl(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    addr = _extract_address(prompt)
    if not addr:
        return None
    days = _parse_time_window_days(prompt)
    return hl.get_user_pnl_summary, {"user": addr, "network": "mainnet", "days": days}


def _b_liquidity_profile(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    return hl.get_liquidity_profile, {"coin": tickers[0], "network": "mainnet", "depth": 100}


def _b_volatility_metrics(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    return hl.get_volatility_metrics, {"coin": tickers[0], "network": "mainnet", "trades": 200}


def _b_trend_ma(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    return hl.get_trend_ma, {"coin": tickers[0], "network": "mainnet", "short": 20, "long": 50}


def _b_premium_monitor(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    return hl.get_premium_monitor, {"coin": tickers[0], "network": "mainnet"}


def _b_oi_trend(prompt: str) -> Optional[Tuple[Callable[..., Any], Dict[str, Any]]]:
    tickers = _extract_tickers(prompt)
    if not tickers:
        return None
    return hl.get_oi_trend, {"coin": tickers[0], "network": "mainnet"}


TOOLS: List[ToolSpec] = [
    ToolSpec(
        name="full_market_picture",
        description="Fused Info + WebSocket snapshot with analytics and buy/sell signal for a coin like $BTC.",
        builder=_b_full_market,
    ),
    ToolSpec(
        name="funding_history",
        description="Historical funding rate series for a coin to compute averages over day or week.",
        builder=_b_funding_history,
    ),
    ToolSpec(
        name="predicted_fundings",
        description="Predicted funding rates across venues (overview, not coin-specific).",
        builder=_b_predicted_funding,
    ),
    ToolSpec(
        name="oi_caps",
        description="List perps currently at open interest caps (global).",
        builder=_b_oi_caps,
    ),
    ToolSpec(
        name="orderbook",
        description="Orderbook snapshot with top of book for a specific coin like $ETH.",
        builder=_b_orderbook,
    ),
    ToolSpec(
        name="trades",
        description="Recent trades for a specific coin like $ETH to see flow and VWAP.",
        builder=_b_trades,
    ),
    ToolSpec(
        name="asks_to_price",
        description="Sum asks up to a target price mentioned in the prompt (e.g., 'until $115,000').",
        builder=_b_asks_to_price,
    ),
    ToolSpec(
        name="account_summary",
        description="Wallet account summary using clearinghouseState when a 0x address is provided.",
        builder=_b_account_summary,
    ),
    ToolSpec(
        name="active_asset_data",
        description="Active asset data (limits, leverage, mark) for a wallet and coin like $APT.",
        builder=_b_active_asset,
    ),
    ToolSpec(
        name="slippage",
        description="Slippage/price impact estimate for buying/selling a USD notional on a coin.",
        builder=_b_slippage,
    ),
    ToolSpec(
        name="meta_and_ctxs",
        description="Perp asset contexts including mark price, funding, open interest, premium.",
        builder=_b_meta_and_ctxs,
    ),
    ToolSpec(
        name="user_pnl",
        description="User PnL summary over a window (1d/7d/30d) for a 0x wallet.",
        builder=_b_user_pnl,
    ),
    ToolSpec(
        name="liquidity_profile",
        description="Cumulative depth profile for bids/asks to gauge top-N liquidity.",
        builder=_b_liquidity_profile,
    ),
    ToolSpec(
        name="volatility_metrics",
        description="Realized volatility snapshot from recent trades for a coin.",
        builder=_b_volatility_metrics,
    ),
    ToolSpec(
        name="trend_ma",
        description="Simple moving average trend and cross (e.g., 20/50).",
        builder=_b_trend_ma,
    ),
    ToolSpec(
        name="premium_monitor",
        description="Current perp premium vs oracle and funding for a coin.",
        builder=_b_premium_monitor,
    ),
    ToolSpec(
        name="oi_trend",
        description="Open interest level and delta vs prior cached snapshot.",
        builder=_b_oi_trend,
    ),
]


_EMBEDDER: Optional[SentenceTransformer] = None


def _get_embedder() -> SentenceTransformer:
    global _EMBEDDER
    if _EMBEDDER is None:
        _EMBEDDER = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _EMBEDDER


def build_realtime_context(prompt: str, max_tools: int = 3) -> str:
    # Backward compatible wrapper around structured builder
    text, _ = build_realtime_context_structured(prompt, max_tools=max_tools)
    return text


def build_realtime_context_structured(prompt: str, max_tools: int = 3) -> tuple[str, List[Dict[str, Any]]]:
    embedder = _get_embedder()
    # Rank tools by similarity of prompt to tool descriptions
    tool_texts = [t.description for t in TOOLS]
    em_tools = embedder.encode(tool_texts, normalize_embeddings=True, convert_to_numpy=True)
    em_query = embedder.encode([prompt], normalize_embeddings=True, convert_to_numpy=True)[0]
    sims = util.cos_sim(em_query, em_tools).cpu().numpy()[0]
    ranked: List[Tuple[float, ToolSpec]] = sorted(zip(sims, TOOLS), key=lambda x: x[0], reverse=True)

    # Context gating: if a wallet address is present, prefer user-scoped tools only;
    # if only a ticker is present, prefer ticker tools; else allow global tools.
    has_addr = _extract_address(prompt) is not None
    has_ticker = len(_extract_tickers(prompt)) > 0

    def _allowed(name: str) -> bool:
        user_only = {"account_summary", "active_asset_data", "user_pnl"}
        global_only = {"oi_caps", "predicted_fundings", "meta_and_ctxs"}
        ticker_tools = {
            "full_market_picture", "orderbook", "trades", "funding_history",
            "asks_to_price", "slippage", "premium_monitor", "volatility_metrics",
            "trend_ma", "oi_trend", "liquidity_profile",
        }
        if has_addr and has_ticker:
            return (name in user_only) or (name in ticker_tools)
        if has_addr:
            return name in user_only
        if has_ticker:
            return name in ticker_tools
        # no addr/ticker → allow global only
        return name in global_only

    lines: List[str] = []
    calls: List[Dict[str, Any]] = []
    used = 0
    for _, spec in ranked:
        if used >= max_tools:
            break
        if not _allowed(spec.name):
            continue
        try:
            built = spec.builder(prompt)
            if not built:
                continue
            fn, kwargs = built
            res = fn(**kwargs)
            try:
                calls.append({"tool": spec.name, "function": getattr(fn, "__name__", str(fn)), "kwargs": kwargs, "response": res})
            except Exception:
                pass
            # prefer summary; fallback to minimal key-values
            if isinstance(res, dict) and res.get("ok") is False:
                continue
            summary = res.get("summary") if isinstance(res, dict) else None
            payload = {}
            # attach a compact structured slice to aid the model
            try:
                if spec.name == "account_summary":
                    d = (res.get("data") if isinstance(res, dict) else {}) or {}
                    ms = d.get("marginSummary", {}) if isinstance(d, dict) else {}
                    positions = d.get("assetPositions", []) if isinstance(d, dict) else []
                    payload = {
                        "accountValue": ms.get("accountValue"),
                        "totalNtlPos": ms.get("totalNtlPos"),
                        "positions": len(positions),
                        "withdrawable": d.get("withdrawable"),
                    }
                elif spec.name == "asks_to_price":
                    # Sum asks up to a target price
                    target = _parse_target_price(prompt)
                    data = res.get("data") if isinstance(res, dict) else None
                    asks = (data or {}).get("asks") if isinstance(data, dict) else []
                    total_units = 0.0
                    total_notional = 0.0
                    try:
                        for level in asks or []:
                            px, sz = level[0], level[1]
                            pxf = float(px)
                            szf = float(sz)
                            if target is not None and pxf <= target:
                                total_units += szf
                                total_notional += pxf * szf
                            else:
                                break
                    except Exception:
                        total_units = 0.0
                        total_notional = 0.0
                    payload = {"asksTo": target, "units": total_units, "notional": total_notional}
                elif spec.name == "oi_caps":
                    caps = res.get("data") if isinstance(res, dict) else []
                    if isinstance(caps, list):
                        payload = {"caps": caps[:20]}
                elif spec.name == "funding_history":
                    rows = res.get("data") if isinstance(res, dict) else []
                    vals: List[float] = []
                    for row in rows or []:
                        try:
                            vals.append(float(row.get("fundingRate")))
                        except Exception:
                            continue
                    avg = (sum(vals) / len(vals)) if vals else None
                    payload = {"avgFunding": avg, "points": len(vals)}
                elif spec.name == "full_market_picture":
                    mp = res if isinstance(res, dict) else {}
                    sig = (mp.get("signal") or {}) if isinstance(mp, dict) else {}
                    snap = (mp.get("marketSnapshot") or {}) if isinstance(mp, dict) else {}
                    payload = {
                        "signal": sig.get("label"),
                        "score": sig.get("score"),
                        "mid": snap.get("mid"),
                        "funding": snap.get("funding"),
                        "OI": snap.get("OI"),
                    }
                elif spec.name == "slippage":
                    payload = {
                        "avgPx": res.get("avgPx") if isinstance(res, dict) else None,
                        "slippageBps": res.get("slippageBps") if isinstance(res, dict) else None,
                    }
                elif spec.name == "predicted_fundings":
                    data = res.get("data") if isinstance(res, dict) else []
                    coins = [e[0] for e in data if isinstance(e, list) and e]
                    payload = {"coins": coins[:15]}
                elif spec.name == "liquidity_profile":
                    bid = res.get("bid") if isinstance(res, dict) else []
                    ask = res.get("ask") if isinstance(res, dict) else []
                    try:
                        bid_total = float(bid[-1][1]) if bid else 0.0
                        ask_total = float(ask[-1][1]) if ask else 0.0
                    except Exception:
                        bid_total, ask_total = 0.0, 0.0
                    payload = {"bidTotal": bid_total, "askTotal": ask_total, "levels": (len(bid), len(ask))}
                elif spec.name == "volatility_metrics":
                    payload = {"realizedVol": res.get("realizedVol") if isinstance(res, dict) else None}
                elif spec.name == "trend_ma":
                    payload = {
                        "s": res.get("smaShort") if isinstance(res, dict) else None,
                        "l": res.get("smaLong") if isinstance(res, dict) else None,
                        "cross": res.get("cross") if isinstance(res, dict) else None,
                    }
                elif spec.name == "premium_monitor":
                    payload = {
                        "premium": res.get("premium") if isinstance(res, dict) else None,
                        "funding": res.get("funding") if isinstance(res, dict) else None,
                    }
                elif spec.name == "oi_trend":
                    payload = {
                        "oi": res.get("openInterest") if isinstance(res, dict) else None,
                        "delta": res.get("delta") if isinstance(res, dict) else None,
                    }
            except Exception:
                payload = {}

            # Natural text, no raw dict printing
            if spec.name == "account_summary" and payload:
                lines.append(
                    f"Wallet: available ${payload.get('withdrawable')}, account ${payload.get('accountValue')}, "
                    f"NtlPos {payload.get('totalNtlPos')}, positions {payload.get('positions')}"
                )
            elif spec.name == "asks_to_price" and payload:
                ticker_list = _extract_tickers(prompt)
                coin = ticker_list[0] if ticker_list else ""
                tgt = payload.get("asksTo")
                units = payload.get("units")
                notion = payload.get("notional")
                if tgt is not None and units is not None:
                    lines.append(
                        f"Asks to ${tgt}: {units:.4f} {coin} (~${notion:.2f})"
                    )
            elif spec.name == "oi_caps" and payload:
                caps = payload.get('caps') or []
                lines.append("OI caps: " + ", ".join(caps))
            elif spec.name == "funding_history" and payload:
                avg = payload.get('avgFunding')
                lines.append(f"Funding: avg {avg}" if avg is not None else "Funding: no data")
            elif spec.name == "full_market_picture" and payload:
                # Convert real-time snapshot into a compact NL summary for the model
                sig = payload.get('signal')
                score = payload.get('score')
                mid = payload.get('mid')
                fund = payload.get('funding')
                oi = payload.get('OI')
                parts = []
                if sig is not None: parts.append(f"signal {sig} ({score})")
                if mid is not None: parts.append(f"mid {mid}")
                if fund is not None: parts.append(f"funding {fund}")
                if oi is not None: parts.append(f"OI {oi}")
                lines.append("Market: " + ", ".join(parts))
            elif spec.name == "slippage" and payload:
                lines.append(
                    f"Slippage: avg px {payload.get('avgPx')}, slip {payload.get('slippageBps')}bps"
                )
            elif spec.name == "liquidity_profile" and payload:
                bt = payload.get('bidTotal')
                at = payload.get('askTotal')
                lines.append(
                    f"Liquidity: top-depth bid {bt}, ask {at}"
                )
            elif spec.name == "volatility_metrics" and payload:
                lines.append(
                    f"Vol: realized {payload.get('realizedVol')}"
                )
            elif spec.name == "trend_ma" and payload:
                lines.append(
                    f"Trend: {payload.get('cross')} 20/50"
                )
            elif spec.name == "premium_monitor" and payload:
                lines.append(
                    f"Premium: {payload.get('premium')}, funding {payload.get('funding')}"
                )
            elif spec.name == "oi_trend" and payload:
                lines.append(
                    f"OI: {payload.get('oi')} Δ {payload.get('delta')}"
                )
            elif summary:
                lines.append(summary)
            else:
                lines.append(f"{spec.name}: done")
            used += 1
        except Exception:
            continue

    return "\n".join(lines), calls


