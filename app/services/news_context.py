"""
Fetches recent crypto headlines for the AI agent (RSS + optional CryptoPanic).

- Never raises from `fetch_for_symbol`: failures log at warning and return [].
- When `NEWS_CONTEXT_ENABLED=false`, returns [] without HTTP calls.
- Headlines are a snapshot only; the LLM must treat them as auxiliary, possibly stale.
"""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

import httpx

from app.agents.schemas import NewsHeadline
from app.core.config import Settings
from app.core.logging import get_logger

log = get_logger(__name__)

_ASSET_ALIASES: dict[str, list[str]] = {
    "BTC": ["bitcoin"],
    "ETH": ["ethereum"],
    "SOL": ["solana"],
    "BNB": ["binance coin", "bnb"],
    "XRP": ["ripple"],
    "DOGE": ["dogecoin"],
    "ADA": ["cardano"],
}


def _local_tag(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def trading_pair_to_base_asset(symbol: str) -> str:
    u = symbol.upper().strip()
    for suffix in ("USDT", "USDC", "BUSD", "FDUSD", "TUSD", "USD", "EUR", "GBP", "BTC"):
        if u.endswith(suffix) and len(u) > len(suffix):
            return u[: -len(suffix)]
    return u


def keywords_for_symbol(symbol: str) -> list[str]:
    base = trading_pair_to_base_asset(symbol)
    extra = _ASSET_ALIASES.get(base, [])
    return [base, *extra]


def title_matches_keywords(title: str, keywords: list[str]) -> bool:
    t = title.lower()
    return any(kw.lower() in t for kw in keywords)


def parse_rss_items(xml_text: str | bytes, source_label: str) -> list[NewsHeadline]:
    """Parse RSS/Atom-ish XML; best-effort for common crypto feeds."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        log.debug("RSS parse error for %s: %s", source_label, exc)
        return []

    out: list[NewsHeadline] = []
    for el in root.iter():
        if _local_tag(el.tag) != "item":
            continue
        title = link = pub = None
        for child in el:
            ln = _local_tag(child.tag)
            text = (child.text or "").strip()
            if not text:
                continue
            if ln == "title":
                title = text
            elif ln == "link":
                link = text
            elif ln == "pubDate":
                pub = text
        if title:
            out.append(
                NewsHeadline(
                    title=title,
                    source=source_label,
                    url=link,
                    published_at=pub,
                )
            )
    return out


def prioritize_headlines(
    items: list[NewsHeadline],
    keywords: list[str],
    max_count: int,
) -> list[NewsHeadline]:
    """Symbol-relevant titles first, then general feed items."""
    if max_count <= 0:
        return []
    matched = [h for h in items if title_matches_keywords(h.title, keywords)]
    matched_keys = {h.title.strip().lower()[:200] for h in matched}
    rest = [h for h in items if h.title.strip().lower()[:200] not in matched_keys]
    combined = matched + rest
    seen: set[str] = set()
    unique: list[NewsHeadline] = []
    for h in combined:
        key = h.title.strip().lower()[:200]
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
        if len(unique) >= max_count:
            break
    return unique


class NewsContextService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def fetch_for_symbol(self, symbol: str) -> list[NewsHeadline]:
        if not self._settings.news_context_enabled:
            return []

        timeout = httpx.Timeout(self._settings.news_context_timeout)
        max_h = self._settings.news_context_max_headlines
        keywords = keywords_for_symbol(symbol)
        base = trading_pair_to_base_asset(symbol)

        merged: list[NewsHeadline] = []
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                cp = await self._fetch_cryptopanic(client, base)
                merged.extend(cp)

                for url in self._rss_urls():
                    label = urlparse(url).netloc or "rss"
                    items = await self._fetch_one_rss(client, url, label)
                    merged.extend(items)
        except Exception as exc:  # noqa: BLE001
            log.warning("News context aggregate fetch failed for %s: %s", symbol, exc)
            return []

        return prioritize_headlines(merged, keywords, max_h)

    def _rss_urls(self) -> list[str]:
        raw = self._settings.news_rss_feed_urls
        return [u.strip() for u in raw.split(",") if u.strip()]

    async def _fetch_one_rss(
        self,
        client: httpx.AsyncClient,
        url: str,
        source_label: str,
    ) -> list[NewsHeadline]:
        try:
            r = await client.get(url, headers={"User-Agent": "crypto-bot-news-context/1.0"})
            r.raise_for_status()
            text = r.text
        except Exception as exc:  # noqa: BLE001
            log.warning("RSS fetch failed %s: %s", url, exc)
            return []
        return parse_rss_items(text, source_label)

    async def _fetch_cryptopanic(
        self,
        client: httpx.AsyncClient,
        currency: str,
    ) -> list[NewsHeadline]:
        token = self._settings.cryptopanic_api_token.strip()
        if not token:
            return []
        url = "https://cryptopanic.com/api/v1/posts/"
        params = {"auth_token": token, "currencies": currency, "kind": "news"}
        try:
            r = await client.get(url, params=params)
            r.raise_for_status()
            data = r.json()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            log.warning("CryptoPanic fetch failed: %s", exc)
            return []

        out: list[NewsHeadline] = []
        for row in data.get("results") or []:
            title = (row.get("title") or "").strip()
            if not title:
                continue
            src_title = None
            s = row.get("source")
            if isinstance(s, dict):
                src_title = s.get("title")
            out.append(
                NewsHeadline(
                    title=title,
                    source=(src_title or "CryptoPanic"),
                    url=row.get("url"),
                    published_at=row.get("published_at"),
                )
            )
        return out
