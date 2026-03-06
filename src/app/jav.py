import asyncio
import re
import sys
from argparse import ArgumentParser, Namespace
from collections.abc import AsyncIterator, Iterable
from pathlib import Path
from typing import Sequence, TypedDict

import yaml
from wcpan.jav import generate_detailed_products
from wcpan.logging import ConfigBuilder


class ProductDict(TypedDict):
    product_id: str
    title: str
    actresses: list[str]


class ManifestDict(TypedDict):
    id: str
    name: str
    need_review: bool
    products: dict[str, ProductDict]
    title: dict[str, str]


_MAX_BYTES = 255
_MAX_CHARS = 255
_ELLIPSIS = "\u2026"


async def main(args: list[str] | None = None) -> int:
    kwargs = parse_args(args)
    setup_logging()
    action = kwargs.action
    if not action:
        return 1
    return await action(kwargs)


def parse_args(args: list[str] | None = None) -> Namespace:
    parser = ArgumentParser("jav")

    command = parser.add_subparsers()

    g_parser = command.add_parser("scan", aliases=["s"])
    g_parser.add_argument("path", type=str)
    g_parser.add_argument("--allow-empty", action="store_true", default=False)
    g_parser.set_defaults(action=_scan)

    v_parser = command.add_parser("update", aliases=["u"])
    v_parser.add_argument("--pending", action="store_true", default=False)
    v_parser.set_defaults(action=_update)

    a_parser = command.add_parser("rename", aliases=["r"])
    a_parser.add_argument("--ready", action="store_true", default=False)
    a_parser.set_defaults(action=_rename)

    kwargs = parser.parse_args(args)
    return kwargs


def setup_logging():
    from logging.config import dictConfig

    dictConfig(ConfigBuilder().add("app.jav", level="D").to_dict())


async def _scan(kwargs: Namespace) -> int:
    root_path = Path(kwargs.path)
    async for node in _process_path_list(root_path.iterdir(), kwargs.allow_empty):
        yaml.safe_dump(
            [node],
            sys.stdout,
            encoding="utf-8",
            allow_unicode=True,
            default_flow_style=False,
        )
        await asyncio.sleep(1)
    return 0


async def _rename(kwargs: Namespace) -> int:
    manifest: list[ManifestDict] = yaml.safe_load(sys.stdin)
    for row in manifest:
        if kwargs.ready and row["need_review"]:
            continue
        path = Path(row["id"])
        title_dict = row["title"]

        for value in title_dict.values():
            if not value:
                continue

            print(f"rename {path.name} -> {value}")
            _rename_local(path, value)
            break
    return 0


async def _update(kwargs: Namespace) -> int:
    manifest: list[ManifestDict] = yaml.safe_load(sys.stdin)
    for entry in manifest:
        _fill_titles(entry)
    if kwargs.pending:
        manifest = [e for e in manifest if e["need_review"]]
    yaml.safe_dump(
        manifest,
        sys.stdout,
        encoding="utf-8",
        allow_unicode=True,
        default_flow_style=False,
    )
    return 0


async def _process_path_list(
    paths: Iterable[Path], allow_empty: bool = False
) -> AsyncIterator[ManifestDict]:
    for path in sorted(paths):
        if path.name.startswith("."):
            continue

        products = {sauce: prod async for sauce, prod in _collect_products(path.name)}
        if not products:
            if not allow_empty:
                continue
            entry: ManifestDict = {
                "id": str(path),
                "name": path.name,
                "need_review": True,
                "products": {
                    "dummy": {
                        "product_id": path.name,
                        "title": "",
                        "actresses": [],
                    },
                },
                "title": {"dummy": ""},
            }
            yield entry
            continue

        entry = {
            "id": str(path),
            "name": path.name,
            "need_review": False,
            "products": products,
            "title": {},
        }
        _fill_titles(entry)
        yield entry


def _fill_titles(entry: ManifestDict) -> None:
    pairs = [
        (sauce, _compute_title(sauce, prod))
        for sauce, prod in entry["products"].items()
    ]
    title_dict = dict(_pad_keys(pairs))
    entry["title"] = title_dict
    entry["need_review"] = any(_ELLIPSIS in v for v in title_dict.values())


def _rename_local(path: Path, new_name: str) -> None:
    if path.is_dir():
        if new_name == path.name:
            print("skipped")
            return
        path.rename(path.parent / new_name)
        return

    new_dir = path.parent / new_name
    new_dir.mkdir()
    path.rename(new_dir / path.name)


def _fits(name: str) -> bool:
    return len(name.encode("utf-8")) <= _MAX_BYTES and len(name) <= _MAX_CHARS


def _actress_name_variants(actress: str) -> list[str]:
    return [p.strip() for p in re.split(r"[（）()]", actress) if p.strip()]


def _split_keep_tail(title: str, actresses: list[str]) -> tuple[str, str, set[int]]:
    """Scan the tail of title to build the keep window.

    Iteratively strips actress name variants (any variant of each actress)
    from the tail, then looks for a single trailing series number.

    Returns:
        head: the truncatable portion before the keep window
        keep_tail: series number and actress tokens to always preserve
        found: indices into actresses whose variants were found in the tail
    """
    all_variants = [_actress_name_variants(a) for a in actresses]
    remaining = list(range(len(actresses)))
    actress_tokens: list[str] = []
    head = title

    _WRAPPERS = [(" ", ""), ("【", "】"), ("（", "）"), ("(", ")")]

    changed = True
    while changed:
        changed = False
        for idx in list(remaining):
            for v in all_variants[idx]:
                for open_b, close_b in _WRAPPERS:
                    token = f"{open_b}{v}{close_b}"
                    if head.endswith(token):
                        actress_tokens.insert(0, v)
                        head = head[: -len(token)]
                        remaining.remove(idx)
                        changed = True
                        break
                if changed:
                    break
            if changed:
                break

    series_token = ""
    m = re.search(r" (\d+)$", head)
    if m:
        series_token = m.group(1)
        head = head[: m.start()]
        assert isinstance(series_token, str)

    tail_parts = [t for t in [series_token, *actress_tokens] if t]
    keep_tail = " ".join(tail_parts)
    found = set(range(len(actresses))) - set(remaining)
    return head, keep_tail, found


def _shrink_title(product_id: str, head: str, suffix: str) -> str:
    suffix_str = f" {suffix}" if suffix else ""
    for i in range(len(head), -1, -1):
        candidate = f"{product_id} {head[:i]}{_ELLIPSIS}{suffix_str}"
        if _fits(candidate):
            return candidate
    return f"{product_id}{_ELLIPSIS}{suffix_str}"


def _make_name(product_id: str, title: str, actresses: list[str]) -> str:
    head, keep_tail, found = _split_keep_tail(title, actresses)

    missing = [
        a
        for i, a in enumerate(actresses)
        if i not in found and not any(v in title for v in _actress_name_variants(a))
    ]
    append_str = " ".join(missing)

    full = f"{product_id} {title}"
    if append_str:
        full += f" {append_str}"
    if _fits(full):
        return full

    suffix_parts = [p for p in [keep_tail, append_str] if p]
    suffix = " ".join(suffix_parts)
    return _shrink_title(product_id, head, suffix)


async def _collect_products(name: str) -> AsyncIterator[tuple[str, ProductDict]]:
    async for product in generate_detailed_products(name):
        yield (
            product.sauce,
            {
                "product_id": product.id,
                "title": product.title,
                "actresses": list(product.actresses),
            },
        )


def _compute_title(sauce: str, product: ProductDict) -> str:
    match sauce:
        case "mgstage" | "heyzo" | "heydouga":
            return _make_name(product["product_id"], product["title"], [])
        case "carib" | "caribpr" | "1pondo" | "10musume" | "fanza" | "dummy":
            return _make_name(
                product["product_id"], product["title"], product["actresses"]
            )
        case _:
            return product["title"]


def _pad_keys[V](pairs: Sequence[tuple[str, V]]) -> list[tuple[str, V]]:
    if not pairs:
        return []

    ml = max(len(_[0]) for _ in pairs)
    padded = [(f"{k:_>{ml}}", v) for k, v in pairs]
    return padded


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
