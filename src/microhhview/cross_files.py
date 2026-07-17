from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

CROSS_FILENAME_RE = re.compile(
    r"^(?P<var>.+)\.(?P<plane>xy|xz|yz)\.cross\.(?P<domain>\d+)\.(?P<ext>[^.]+)$"
)


@dataclass
class CrossFileInfo:
    path: Path
    var: str
    plane: str
    domain: int
    domain_str: str
    ext: str


def parse_cross_filename(path: Path) -> CrossFileInfo | None:
    """Parse a MicroHH cross-section filename, e.g. "thl.xy.cross.00.h5".
    Returns None if it doesn't match that naming convention."""
    m = CROSS_FILENAME_RE.match(path.name)
    if not m:
        return None
    return CrossFileInfo(
        path=path,
        var=m["var"],
        plane=m["plane"],
        domain=int(m["domain"]),
        domain_str=m["domain"],
        ext=m["ext"],
    )


def resolve_domain_files(paths: list[Path]) -> list[Path]:
    """Validate a multi-file selection as one MicroHH cross-section variable
    split across nested domains, returning the files ordered coarsest
    (domain 00, the base/outermost domain) first and finest last -- the
    draw order for overlay plotting.

    Only the domain-index token may differ between files (this also rejects
    a glob like "thl.*.cross.00.h5" whose "*" matched the plane instead of
    just the domain index); a single file is returned unchanged with no
    naming-convention check, so arbitrary NetCDF/HDF5 files keep working."""
    if len(paths) <= 1:
        return list(paths)

    infos = []
    for p in paths:
        info = parse_cross_filename(p)
        if info is None:
            raise ValueError(
                f"{p.name!r} doesn't look like a MicroHH cross-section file "
                "(expected <var>.<xy|xz|yz>.cross.<NN>.<ext>); can't overlay "
                "multiple files unless they're all nested-domain cross "
                "sections of the same variable."
            )
        infos.append(info)

    first = infos[0]
    for info in infos[1:]:
        if (info.var, info.plane, info.ext) != (first.var, first.plane, first.ext):
            raise ValueError(
                f"Can't overlay {first.path.name!r} and {info.path.name!r}: "
                "only the domain index may differ between files (variable, "
                "plane, and extension must match)."
            )

    domains = [info.domain for info in infos]
    if len(set(domains)) != len(domains):
        raise ValueError("Duplicate domain index among the selected files.")

    infos.sort(key=lambda info: info.domain)
    return [info.path for info in infos]
