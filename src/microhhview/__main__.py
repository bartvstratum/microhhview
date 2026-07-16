from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(prog="microhhview", description="Quick NetCDF/HDF5 variable viewer")
    parser.add_argument("file", nargs="?", help="Path to a NetCDF or HDF5 file to open")
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = MainWindow(args.file)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
