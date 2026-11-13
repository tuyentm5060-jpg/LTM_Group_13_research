"""Entrypoint for load_generator: launches CLI if arguments are given, else Tkinter GUI."""

from __future__ import annotations

from pathlib import Path
import sys

_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))


def main(argv: list[str] | None = None):
    args = sys.argv[1:] if argv is None else argv
    if args:
        from load_generator.benchmark import main as cli_main
        cli_main(args)
    else:
        from load_generator.gui.main_window import LoadGeneratorApp
        LoadGeneratorApp().mainloop()


if __name__ == "__main__":
    main()
