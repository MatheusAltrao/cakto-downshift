"""Linha de comando. Os subcomandos entram nas tasks seguintes."""
import argparse
import sys

from cakto_downshift import __version__


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cakto-downshift")
    parser.add_argument("--version", action="version", version=f"cakto-downshift {__version__}")
    parser.add_subparsers(dest="comando")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = construir_parser()
    # argparse encerra com SystemExit tanto no --version quanto em erro de uso;
    # capturar aqui devolve o código como retorno, para quem chama main() como função.
    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code or 0)
    if args.comando is None:
        parser.print_help()
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
