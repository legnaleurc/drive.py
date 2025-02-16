from argparse import ArgumentParser
from collections.abc import Sequence
from pathlib import PurePath


def parse_args(args: Sequence[str]) -> PurePath:
    parser = ArgumentParser("eh")
    parser.add_argument("path", type=str)

    kwargs = parser.parse_args(args)
    return PurePath(kwargs.path)
