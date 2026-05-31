# Flag assets

The `<iso>.svg` files in this directory are the 4x3 country flags from
**flag-icons** by Panayiotis Lipiridis, vendored at v7.2.3.

- Source: https://github.com/lipis/flag-icons
- License: MIT
- Filenames are ISO 3166-1 alpha-2 codes, lowercased (e.g. `gb.svg`, `mx.svg`).

Only the codes the 48 qualified World Cup teams resolve to are vendored (see
`WorldCupTeam.iso_code` / `_FIFA_TO_ISO` in `games/worldcup/models.py`). When a
future qualifier maps to a new ISO code, add its `<iso>.svg` here from the same
flag-icons 4x3 set; `tests/test_worldcup_flag_emoji.py` fails until it exists.

`_tbd.svg` is a locally-authored neutral placeholder (not from flag-icons),
rendered for knockout-bracket shells that have no team assigned yet.

Why self-hosted SVG instead of emoji: Windows (Segoe UI Emoji) ships no
country-flag glyphs, so Unicode regional-indicator flag emoji render as bare
two-letter codes there. SVG images render identically on every platform.
