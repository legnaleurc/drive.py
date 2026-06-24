from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import Path


def parse_args(args: Sequence[str]) -> Path:
    parser = ArgumentParser("eh")
    parser.add_argument("path", type=str)

    kwargs = parser.parse_args(args)
    return Path(kwargs.path)
