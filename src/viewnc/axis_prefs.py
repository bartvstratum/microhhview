from __future__ import annotations

# Preferred axis orientation for LES-style dimension names.
X_AXIS_DIMS = {"time", "x", "xh"}
Y_AXIS_DIMS = {"z", "zh"}


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
