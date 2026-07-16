from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

ROOT_GROUP = "/"


@dataclass
class VarInfo:
    name: str
    dims: tuple[str, ...]
    shape: tuple[int, ...]
    dtype: str
    attrs: dict[str, Any] = field(default_factory=dict)


class Backend:
    """Common interface for reading gridded array data from a file.

    Files are modeled as a tree of groups (netCDF4/HDF5 groups); a flat
    file with no groups is just a tree with a single root group "/".
    """

    path: Path
    groups: list[str]

    def variables(self, group: str) -> dict[str, VarInfo]:
        raise NotImplementedError

    def coord(self, group: str, dim: str) -> np.ndarray | None:
        raise NotImplementedError

    def read(self, group: str, name: str, indexers: dict[str, int]) -> np.ndarray:
        """Read a variable, collapsing each dim named in `indexers` to a
        single index. Remaining dims keep the variable's original order."""
        raise NotImplementedError

    def close(self) -> None:
        raise NotImplementedError


class DataTreeBackend(Backend):
    """Backend for netCDF4/HDF5-netCDF files, using xarray's DataTree so
    that dimensions/coordinates defined in a parent group are inherited by
    variables in child groups, matching netCDF4 group semantics."""

    def __init__(self, path: Path):
        import xarray as xr

        self.path = path
        self._tree = xr.open_datatree(path, decode_times=True)
        self._nodes = {node.path: node for node in self._tree.subtree}
        self.groups = sorted(self._nodes.keys())

    def variables(self, group: str) -> dict[str, VarInfo]:
        ds = self._nodes[group].dataset
        return {
            name: VarInfo(
                name=name,
                dims=tuple(da.dims),
                shape=tuple(da.shape),
                dtype=str(da.dtype),
                attrs=dict(da.attrs),
            )
            for name, da in ds.data_vars.items()
            if da.ndim >= 1
        }

    def coord(self, group: str, dim: str) -> np.ndarray | None:
        ds = self._nodes[group].dataset
        if dim in ds.coords:
            return ds.coords[dim].values
        return None

    def read(self, group: str, name: str, indexers: dict[str, int]) -> np.ndarray:
        da = self._nodes[group].dataset[name]
        sel = {d: i for d, i in indexers.items() if d in da.dims}
        return np.asarray(da.isel(**sel).values)

    def close(self) -> None:
        self._tree.close()


class H5pyBackend(Backend):
    """Fallback for arbitrary (non-CF) HDF5 files: no coordinate inference,
    but datasets are still organized by their native group hierarchy."""

    def __init__(self, path: Path):
        import h5py

        self.path = path
        self._file = h5py.File(path, "r")
        self._vars: dict[str, dict[str, tuple[VarInfo, str]]] = {ROOT_GROUP: {}}
        self._file.visititems(self._visit)
        self.groups = sorted(self._vars.keys())

    def _visit(self, full_name: str, obj) -> None:
        import h5py

        if isinstance(obj, h5py.Dataset) and obj.ndim >= 1:
            if "/" in full_name:
                group, var = full_name.rsplit("/", 1)
                group = "/" + group
            else:
                group, var = ROOT_GROUP, full_name
            dims = tuple(self._dim_name(obj, i, var) for i in range(obj.ndim))
            info = VarInfo(
                name=var,
                dims=dims,
                shape=obj.shape,
                dtype=str(obj.dtype),
                attrs=dict(obj.attrs),
            )
            self._vars.setdefault(group, {})[var] = (info, full_name)

    @staticmethod
    def _dim_name(obj, index: int, var: str) -> str:
        """Prefer the name of the attached HDF5 dimension scale (or its
        label) over a synthetic placeholder, so plain HDF5-netCDF4 files
        show real dimension names like "time" instead of "var:dim0"."""
        dim = obj.dims[index]
        if len(dim) > 0:
            return dim[0].name.rsplit("/", 1)[-1]
        if dim.label:
            return dim.label
        return f"{var}:dim{index}"

    def variables(self, group: str) -> dict[str, VarInfo]:
        return {name: info for name, (info, _) in self._vars.get(group, {}).items()}

    def coord(self, group: str, dim: str) -> np.ndarray | None:
        return None

    def read(self, group: str, name: str, indexers: dict[str, int]) -> np.ndarray:
        info, full_path = self._vars[group][name]
        idx = tuple(indexers.get(d, slice(None)) for d in info.dims)
        return np.asarray(self._file[full_path][idx])

    def close(self) -> None:
        self._file.close()


def open_dataset(path: str | Path) -> Backend:
    path = Path(path)
    try:
        return DataTreeBackend(path)
    except Exception:
        return H5pyBackend(path)
