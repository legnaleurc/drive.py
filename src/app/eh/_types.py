from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class AnalyzedData:
    author: str
    title: str
    item_id: int


@dataclass(frozen=True, kw_only=True)
class CrawledData:
    title: str
    url: str
