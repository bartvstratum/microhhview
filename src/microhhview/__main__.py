from __future__ import annotations

import argparse
import sys

from PySide6.QtWidgets import QApplication

from .main_window import MainWindow


def main() -> int:
    parser = argparse.ArgumentParser(prog="microhhview", description="Quick NetCDF/HDF5 variable viewer")
    parser.add_argument(
        "files",
        nargs="*",
        help=(
            "Path(s) to NetCDF/HDF5 file(s) to open. Pass multiple nested-domain "
            "cross-section files (e.g. thl.xy.cross.*.h5) to overlay them in one figure."
        ),
    )
    args = parser.parse_args()

    app = QApplication(sys.argv)
    window = MainWindow(args.files)
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
