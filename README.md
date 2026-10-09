# MXL Item Collector

A desktop companion for **Median XL** (Diablo II mod): browse your stashes and characters with in-game tooltips,
track every unique and set item you have found, keep the best copy of each in a personal collection, and move items
around safely.

Unofficial fan tool, not affiliated with the Median XL team or Blizzard Entertainment.

## Features

- **Stashes and characters**: personal stash, shared stash, Horadric Cube, inventory, worn items and mercenary,
  read straight from your save files (`.stash`, `.shared`, `.d2s`).
- **In-game tooltips**: item names, stats and requirements as the game shows them, plus the roll range of every
  variable stat (`+52% Enhanced Damage [40-60]`) and where each value comes from (base, runeword, jewels, Mystic Orbs).
- **Item quality**: a single percentage per item, weighted by the stats you care about (priorities you can set per
  item type).
- **Library**: the full catalog of unique items (tiered, sacred, SSU, SSSU…) and set items, with search, filters,
  drop information and the items you have already discovered.
- **Collection**: store the best copy of each item (normal and ethereal kept apart), compare new finds automatically,
  take items back out when you need them; separate storage for good superior bases.
- **Skill explanations**: hover a skill on an item to see what it does, with the game's numbers.
- **Mystic Orbs**: applied orbs listed under the tooltip, with their effects on hover.
- **Drag and drop**: move items inside a stash, between stashes, the cube and your inventory.
- **Translations**: English included; add your own language file in `lang/` (see below).

## Safety

- Nothing is ever written while Median XL is running.
- Every file is backed up before its first change (the latest backup of each file is kept).
- Each write is checked by reading the file back; on any doubt, the file is left untouched.

Still, keep your own copy of your save folder before trying a new tool.

## Install

### Windows executable

Coming later. For now, run from source (see below).

### From source

Requires Windows and Python 3.10 or later.

```
pip install ttkbootstrap pillow
python mxl_gui.py
```

On first launch, choose your Median XL installation folder: the game tables and icons are extracted from it
(nothing from the game is shipped with this tool).

To build the executable: `pip install pyinstaller`, then `python build_exe.py` (result in `dist/`).

## Where your data lives

Everything that belongs to you is in one folder next to your game saves:
`%APPDATA%\MedianXL\save\MXL Item Collector\`

- `settings.json`: language, last stash, game folder, priorities;
- `library.json`: discoveries and your collection (the stored items themselves);
- `backups\`: backups of game files changed by the tool;
- `lang\`: extra or corrected translations (`xx.json`, same keys as `lang/en.json`).

## Tests

```
python tests/run_tests.py --base
```

Options: `--no-gui` (skip interface tests), `--slow` (also build the executable and rebuild the game tables),
`-k text` (only matching cases). Tests that need the game look for it in your settings (`game_dir`) or in the
`MXL_GAME_DIR` environment variable.

## Project layout

- `mxl_gui.py`: main window (entry point); `mxl_library*.py`: Library, collection and storage;
- `mxl_save.py`, `mxl_format.py`: reading and safe writing of save files;
- `mxl_data.py`, `mxl_install.py`, `extract_data.py`: game tables extracted from your installation;
- `mxl_tooltip.py`, `mxl_stat_text.py`, `mxl_skill*.py`: tooltips and skill explanations;
- `docs/`: notes on the file formats and design (in French);
- `tests/`: regression tests and test save files.

## License

[MIT](LICENSE)
