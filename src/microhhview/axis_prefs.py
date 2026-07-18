from __future__ import annotations

import numpy as np

# Preferred axis orientation for LES-style dimension names.
X_AXIS_DIMS = {"time", "x", "xh"}
Y_AXIS_DIMS = {"z", "zh"}

# Staggered ("h"-suffixed) dims share a physical direction with their
# cell-center counterpart, e.g. "xh" is still the x-direction.
_STAGGER_BASE = {"xh": "x", "yh": "y", "zh": "z"}


def spatial_letter(dim: str) -> str:
    """The physical direction ("x", "y", or "z") a dim represents,
    collapsing staggered variants (xh/yh/zh) onto their base direction.
    Non-spatial dims (e.g. "time") are returned unchanged."""
    return _STAGGER_BASE.get(dim, dim)


def default_xy(dims: tuple[str, str]) -> tuple[str, str]:
    """Pick (y_dim, x_dim) from a pair of dims, preferring time/x/xh on the
    x-axis and z/zh on the y-axis over the raw dimension order."""
    d0, d1 = dims
    x_candidates = [d for d in dims if d in X_AXIS_DIMS]
    if x_candidates:
        x_dim = x_candidates[0]
        y_dim = d1 if x_dim == d0 else d0
        return y_dim, x_dim
    y_candidates = [d for d in dims if d in Y_AXIS_DIMS]
    if y_candidates:
        y_dim = y_candidates[0]
        x_dim = d1 if y_dim == d0 else d0
        return y_dim, x_dim
    return d0, d1


def default_sweep_dim(dims: tuple[str, ...]) -> str:
    """Pick the preferred dimension to vary along a line plot's x-axis from
    an arbitrary list of dims: time/x/xh first, else the first dim."""
    for d in dims:
        if d in X_AXIS_DIMS:
            return d
    return dims[0] if dims else ""


def dim_label(name: str, units: str | None) -> str:
    """"name (units)" for axis/coordinate labels. Skips units for "time":
    either it's a decoded datetime (self-explanatory) or a raw "seconds
    since ..." style unit that's meaningless out of context."""
    if units and name != "time":
        return f"{name} ({units})"
    return name


def dim_edges(coord: np.ndarray, dim: str) -> tuple[float, float]:
    """Domain edges along `dim`, inferred purely from its coordinate array
    -- MicroHH cross-section files carry no domain-boundary metadata of
    their own. Staggered ("h"-suffixed) dims already store cell edges, so
    the first/last value are the domain edges directly. Cell-center dims
    (x, y, z) extrapolate half a cell past each end using the local
    spacing there -- exact on the equidistant x/y grid, an approximation
    on the generally non-equidistant z grid."""
    coord = np.asarray(coord)
    if dim.endswith("h"):
        return float(coord[0]), float(coord[-1])
    if len(coord) < 2:
        return float(coord[0]), float(coord[0])
    lo = coord[0] - (coord[1] - coord[0]) / 2
    hi = coord[-1] + (coord[-1] - coord[-2]) / 2
    return float(lo), float(hi)
