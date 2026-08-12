"""Async scraper for 1TamilMV with enhanced headers for Render environment bypass."""
import asyncio
import logging
from typing import List, Dict, Optional
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

from bot.config import Config

logger = logging.getLogger(__name__)

class TamilMVScraper:
    """Scraper for 1TamilMV movie listings with cloud block bypass."""

    KNOWN_EXTENSIONS = [
        "ing", "dad", "in", "app", "immo", "blue", "tw", "yt", "pk", 
        "life", "rest", "pro", "baby", "hair", "click", "lat", 
        "world", "wiki", "ws", "fi", "be", "pl", "ong", "cz", "cards"
    ]

    # Mobile-optimized browser headers to bypass strict data-center flagging
    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 14; SM-S928B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ta;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-Ch-Ua": '"Google Chrome";v="125", "Chromium";v="125", "Not.A/Brand";v="24"',
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": '"Android"',
        "Upgrade-Insecure-Requests": "1",
    }

    def __init__(self):
        config_domains = getattr(Config, "PROXY_DOMAINS", [])
        auto_domains = [f"https://www.1tamilmv.{ext}/" for ext in self.KNOWN_EXTENSIONS]
        self.domains = list(dict.fromkeys(config_domains + auto_domains))
        self.working_domain: Optional[str] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=25)
            self._session = aiohttp.ClientSession(timeout=timeout)
        return self._session

    async def _find_working_domain(self) -> Optional[str]:
        """Iterate through domains using mobile headers to find a clear gateway."""
        session = await self._get_session()
        for domain in self.domains:
            try:
                logger.info(f"Checking gateway: {domain}")
                async with session.get(domain, headers=self.HEADERS, ssl=False) as resp:
                    if resp.status == 200:
                        html = await resp.text()
                        
                        if any(block in html for block in ["Just a moment...", "cf-browser-verification", "Enable JavaScript"]):
                            logger.warning(f"Cloudflare challenge detected on {domain}. Skipping...")
                            continue
                            
                        if "ipsDataItem" not in html and "1TamilMV" not in html:
                            logger.warning(f"Invalid content structure on {domain}. Skipping...")
                            continue

                        logger.info(f"✅ Active bypass gateway established: {domain}")
                        self.working_domain = domain
                        return domain
            except Exception as e:
                logger.debug(f"Gateway failed {domain}: {e}")
                continue
                
        logger.error("❌ All domains intercepted by Cloudflare security shield.")
        return None

    async def get_latest(self, limit: int = 10) -> List[Dict]:
        """Fetch latest movie updates safely."""
        domain = self.working_domain or await self._find_working_domain()
        if not domain:
            return []

        session = await self._get_session()

        try:
            async with session.get(domain, headers=self.HEADERS, ssl=False) as resp:
                html = await resp.text()
                
                if "Just a moment..." in html:
                    logger.warning("Cloudflare intercept triggered. Refreshing gateway...")
                    self.working_domain = None
                    return []
                    
                return self._parse_movies(html, domain, limit)
        except Exception as e:
            logger.error(f"Fetch execution failed: {e}")
            self.working_domain = None
            return []

    def _parse_movies(self, html: str, base_url: str, limit: int) -> List[Dict]:
        """Parse structured movie entries."""
        soup = BeautifulSoup(html, "html.parser")
        movies = []

        entries = soup.select(".ipsDataItem_main, .structItem-title, article, .xtt-post-title")
        if not entries:
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

            quality = "HD"
            for q in ["4K", "2160p", "1080p", "720p", "480p", "HDRip", "WEB-DL", "BluRay", "HQ"]:
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

        logger.info(f"Successfully parsed {len(movies)} items from {base_url}")
        return movies

    async def search(self, query: str, limit: int = 10) -> List[Dict]:
        """Search query filter."""
        all_movies = await self.get_latest(limit=50)
        q = query.lower()
        filtered = [m for m in all_movies if q in m["title"].lower()]
        return filtered[:limit]

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
