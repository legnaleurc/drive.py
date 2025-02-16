from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class AnalyzedData:
    author: str
    title: str


@dataclass(frozen=True, kw_only=True)
class CrawledData:
    title: str
    url: str
