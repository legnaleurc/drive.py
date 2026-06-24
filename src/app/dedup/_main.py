import sys
from typing import NoReturn

from ._args import parse_args


def main(args: list[str]) -> int:
    action = parse_args(args)
    try:
        return action()
    except Exception as error:
        print(error, file=sys.stderr)
        return 1


def run_as_module() -> NoReturn:
    sys.exit(main(sys.argv[1:]))
