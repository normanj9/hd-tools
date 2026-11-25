# HD-Tools

Personal Helldivers 2 tools: static HTML pages that are opened locally in a browser. There's no build step, no framework and no server. Game data is scraped from helldivers.wiki.gg and baked into the pages.

## Files

| File | What it is |
|---|---|
| `loadouts.html` | Loadout tracker: saved builds with slots, notes, tags, roles, faction filters, faction boards, and a "breakpoints vs heavies" table per loadout |
| `damage-calc.html` | Damage calculator: weapon slots vs. enemy parts (shots to kill, penetration), plus a faction view of the heavies |
| `randomizer.html` | Stratagem randomizer with a warbond filter |
| `hd-calc.js` | Shared damage engine (`calcComponent`, `calcHit`, `stk`, `partHP`, `FACTION_HEAVIES`). Both the calc and loadouts load it, so **all game math goes here** to keep the two pages in agreement |
| `scraper/scrape.py` | Wiki scraper. Writes `scraper/data/*.json` and rewrites the data blocks inside the HTML pages |
| `scraper/data/enemies_manual.json` | Manual per-part overrides applied over the scraped enemy data (e.g. marking a part fatal when the wiki doesn't) |
| `scraper/debug_page.py` | Dumps a wiki page's attack-data tables, for fixing scraper parsing |

## Generated data blocks: don't hand-edit

The scraper replaces whatever sits between these markers:

- `damage-calc.html`: `// DATA_BEGIN` … `// DATA_END` (`WEAPONS`, `ENEMIES`)
- `randomizer.html`: `// DATA_BEGIN` … `// DATA_END` (`STRATAGEMS`)
- `loadouts.html`: `// ITEMS_BEGIN` … `// ITEMS_END` (pick lists) and `// CALC_BEGIN` … `// CALC_END` (`CALC_WEAPONS`, `CALC_ENEMIES`)

To change data, fix the scraper or `enemies_manual.json` and rerun it. Don't patch the blobs. They're single very long lines, so grep with `-o` or `cut` rather than printing them whole.

`// SEED_BEGIN` … `// SEED_END` in `loadouts.html` is not generated. It's the starter data used when localStorage is empty, and `exportHTML()` rewrites it.

## Scraper

```
cd scraper
pip install requests beautifulsoup4
python scrape.py                 # full: enemies + weapons + stratagems
python scrape.py --weapons       # or --enemies / --stratagems
python scrape.py --only "Sai"    # targeted; merges into existing JSON
```

- To add a new weapon or enemy, add it to `WEAPON_PAGES` or `ENEMY_PAGES` in `scrape.py`, then scrape it with `--only`.
- If a page fails to fetch or parse, the scraper keeps the last known entry rather than dropping it.
- The `AP_MAP` armor ladder follows the wiki's current tier names (Very Light was added; the AT tiers go up to VI).
- A patch refresh usually means a full rerun, then adding any new items to the page lists, then a commit like "Refresh data for <patch> + <warbond>".

## Damage model (hd-calc.js)

- Penetration: AP > AV gives full damage, AP == AV gives 65%, AP < AV gives 0.
- Explosive damage is scaled by the part's ExDR. Durable% blends standard and durable damage.
- Every pellet and every hit is assumed to land (best case). Fire/gas ticks, Constitution decay and charge-up aren't modeled in the loadout breakpoints.
- `partHP` = health (or main health if `health_is_main`) + constitution.
- Loadout breakpoints (`bestKill`) take the fewest hits through any fatal part or Main, using the best fire mode.
- `damage-calc.html` deep link: `#w=<weapon-id>,<weapon-id>&faction=bugs|bots|squids`.

## Loadouts: where the real data lives

**The user's real loadouts are not in this repo.** They live on the user's own machine:

- `loadouts.json`, a save file linked through the File System Access API (gitignored). Its shape is `{ schema, rows, boards }`.
- Browser localStorage keys: `hd2_v1` (rows), `hd2_v1_prefs`, `hd2_v1_boards`.

The `SEED` in `loadouts.html` is an old snapshot from before the slot schema, so it's out of date. A cloud session can't read or write the live file. When suggesting or changing loadouts, give the details in chat (or as JSON rows the user can import) unless the user has provided a current export. The user plans to solve syncing later. `todo.md` is also local and gitignored.

Row shape (schema 2, see the comment above `const SCHEMA` in `loadouts.html`):

```
{ id, name, role, factions[], tags[], favorite,
  slots: { armor, booster, primary, secondary, grenade, stratagems[4] },
  extra, notes, dateAdded, updatedAt, lastUsed, uses, schema: 2 }
```

- `factions` takes `bugs`, `bots` and `squids` (Illuminate). An empty list means "General".
- `tags` takes `experimental`, `fun`, `stealth`, `arc`, `fire`, `gas` and `solo`.
- `role` presets: Anti-tank, Crowd control, Generalist, Support, Stealth, Fun.
- `favorite` means a go-to build (★; the old 💎 name prefix).
- A slot value can be `"A / B"` for an either-or pick. A stratagem can be `"Flex"` for an open slot.
- Use exact item names from the pick lists (e.g. `R-36 Eruptor`, `GP-20 Ultimatum`). Otherwise breakpoints and the calc link won't match. Common shorthand is mapped in `ALIASES`.

## Suggesting loadouts

**Who it's for:** the user usually plays in a 4-person squad on Difficulty 10 (Super Helldive). Every loadout has to hold up there: it needs a real answer to that faction's heavies and to large patrols/breaches, whether that comes from the build itself or from a stated role in the squad. Since it's a full squad, a build can specialize (e.g. dedicated anti-tank, or crowd control that leans on teammates for heavies), but say what it leans on the team for.

**Taste:** fun and variety over pure meta. Don't default to the same meta staples (Eruptor especially) in every build. A strong pick is fine when the build is about it, but look for less common weapons and stratagems that still work at D10, and give the reason they work (breakpoints, armor pen, synergy). Several of the user's existing builds already lean on Eruptor/Ultimatum, so new ideas should branch out.

Present a suggested loadout in the same structure as a row: armor (passive), booster, primary, secondary, grenade, four stratagems, then notes. That makes it quick to enter. Base breakpoint claims on the data in this repo, and run the numbers through `hd-calc.js` where you can rather than going from memory. Patches change values often, so if the scraped data might be stale, say so.

## Conventions

- Plain HTML/CSS/JS in a single file per page. Keep it that way; don't add dependencies or a build step.
- `hd-calc.js` has to be next to the HTML files (an exported `loadouts.html` needs it alongside for breakpoints).
- Pages are opened from `file://` too, so features have to degrade gracefully (e.g. File System Access falls back to localStorage only).
