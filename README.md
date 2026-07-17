# microhhview

A NetCDF/HDF5 viewer focused on [MicroHH](https://github.com/microhh/microhh) LES output — not a general-purpose NetCDF/HDF5 viewer.

## Install

No release yet — install from a clone:

```bash
git clone https://github.com/bartvstratum/microhhview.git
cd microhhview
pip install -e .
```

Run it:

```bash
microhhview /path/to/output.nc
```

Passing multiple nested-domain cross-section files that differ only in
domain index (e.g. `microhhview thl.xy.cross.*.h5`) overlays them in one
figure, coarsest domain first.

## Config file

Settings (e.g. available colormaps) are stored in a config file, created on first run at the platform user config dir (via `platformdirs`), e.g. `~/.config/microhhview/config.json` on Linux.
