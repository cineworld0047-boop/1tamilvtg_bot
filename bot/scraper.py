"""Async scraper for 1TamilMV with proxy rotation."""
import asyncio
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from bot.config import Config

logger = logging.getLogger(__name__)

class TamilMVScraper:
    """Scraper for 1TamilMV movie listings."""

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/126.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
    }

    def __init__(self):
        self.domains = Config.PROXY_DOMAINS.copy()
        self.working_domain: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _find_working_domain(self) -> Optional[str]:
        """Rotate through domains and find one that responds."""
        session = await self._get_session()
        for domain in self.domains:
            try:
                async with session.get(domain, headers=self.HEADERS, ssl=False) as resp:
                    if resp.status == 200:
                        logger.info(f"Working domain found: {domain}")
                        self.working_domain = domain
                        return domain
            except Exception as e:
                logger.debug(f"Domain failed {domain}: {e}")
                continue
        logger.error("No working 1TamilMV domain found.")
        return None

    async def get_latest(self, limit: int = 10) -> List[Dict]:
        """Fetch latest movies from 1TamilMV."""
        domain = self.working_domain or await self._find_working_domain()
        if not domain:
            return []

        url = urljoin(domain, "/")
        session = await self._get_session()

        try:
            async with session.get(url, headers=self.HEADERS, ssl=False) as resp:
                html = await resp.text()
                return self._parse_movies(html, domain, limit)
        except Exception as e:
            logger.error(f"Failed to fetch movies: {e}")
            # Reset working domain to retry rotation next time
            self.working_domain = None
            return []

    def _parse_movies(self, html: str, base_url: str, limit: int) -> List[Dict]:
        """Parse movie entries from HTML."""
        soup = BeautifulSoup(html, "html.parser")
        movies = []

        # 1TamilMV typically uses forum post listings
        entries = soup.select(".ipsDataItem_main, .structItem-title, article, .xtt-post-title")
        if not entries:
            # Fallback: look for any anchor with movie-like text
            entries = soup.find_all("a", href=True)

        seen = set()
        for entry in entries[:limit * 3]:
            title_tag = entry if entry.name == "a" else entry.find("a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            href = title_tag.get("href", "")

            if not title or len(title) < 5 or href in seen:
                continue
            seen.add(href)

            # Extract quality hints from title
            quality = "Unknown"
            for q in ["4K", "2160p", "1080p", "720p", "480p", "HDRip", "WEB-DL", "BluRay"]:
                if q.lower() in title.lower():
                    quality = q
                    break

            movie_url = urljoin(base_url, href)
            movies.append({
                "title": title,
                "url": movie_url,
                "quality": quality,
                "source": "1TamilMV",
            })

            if len(movies) >= limit:
                break

        logger.info(f"Parsed {len(movies)} movies from {base_url}")
        return movies

    async def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search 1TamilMV (uses latest + filter as search endpoint varies)."""
        all_movies = await self.get_latest(limit=50)
        q = query.lower()
        filtered = [m for m in all_movies if q in m["title"].lower()]
        return filtered[:limit]

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
