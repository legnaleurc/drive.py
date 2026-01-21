from urllib.parse import urljoin

from aiohttp import ClientSession
from bs4 import BeautifulSoup

from ._types import AnalyzedData, CrawledData


_HOST = "https://sukebei.nyaa.si/"


async def crawl(analyzed: AnalyzedData) -> list[CrawledData]:
    html = await _get_from_nyaa(analyzed.title)

    anchors = html.select("tr > td:nth-child(2) > a:nth-child(1)")
    pairs = ((a.get("title"), a.get("href")) for a in anchors)
    return [
        CrawledData(title=title.strip(), url=urljoin(_HOST, href))
        for title, href in pairs
        if isinstance(title, str) and isinstance(href, str) and _is_allowed(title)
    ]


async def _get_from_nyaa(text: str) -> BeautifulSoup:
    async with (
        ClientSession() as session,
        session.get(
            _HOST,
            params={
                "f": "0",
                "c": "1_0",
                "q": text,
            },
        ) as response,
    ):
        response.raise_for_status()
        html = await response.text(errors="ignore")
    return BeautifulSoup(html, "html.parser")


def _is_allowed(title: str) -> bool:
    if title.find("zhonyk") >= 0:
        return False
    return True
