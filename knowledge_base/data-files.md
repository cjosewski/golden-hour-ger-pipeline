---
paths:
  - "assets/data/**"
---

# Data File Rules

> **Carve-out: Unreal DataTable source files** *(added 2026-07-24, VERB-02
> review)*. The rules below assume hand-authored JSON consumed by our own code.
> A CSV/JSON file whose sole purpose is to be **imported into an Unreal
> `DataTable` asset** is exempt from the naming and key-casing rules, because
> both are dictated by the engine rather than freely chosen:
>
> - **Filename mirrors the DataTable asset it feeds** (e.g.
>   `DT_CasualtyArchetypes.csv` → `/Game/GoldenHour/Data/DT_CasualtyArchetypes`),
>   so source and asset are 1:1 discoverable. Mirror the asset's engine folder
>   under `assets/data/` (e.g. `assets/data/GoldenHour/`).
> - **Column headers must match the row struct's field names verbatim**
>   (PascalCase), or Unreal's importer silently fails to map them.
> - **CSV is acceptable** (and usually preferred) — Unreal's DataTable importer
>   takes CSV or JSON, and CSV diffs far more readably for single-row-per-entity
>   data.
> - **Note that Unreal's CSV importer has no comment syntax** — the first row is
>   always literal headers. Put per-value sourcing/placeholder documentation in a
>   sibling `<Name>.notes.md`, never inline.
> - Everything else below still applies: documented schema, numeric values
>   explained in a companion doc, sensible defaults, no orphaned entries.
>
> First instance: `assets/data/GoldenHour/DT_CasualtyArchetypes.csv` (VERB-02).

- All JSON files must be valid JSON — broken JSON blocks the entire build pipeline
- File naming: lowercase with underscores only, following `[system]_[name].json` pattern
- Every data file must have a documented schema (either JSON Schema or documented in the corresponding design doc)
- Numeric values must include comments or companion docs explaining what the numbers mean
- Use consistent key naming: camelCase for keys within JSON files
- No orphaned data entries — every entry must be referenced by code or another data file
- Version data files when making breaking schema changes
- Include sensible defaults for all optional fields

## Examples

**Correct** naming and structure (`combat_enemies.json`):

```json
{
  "goblin": {
    "baseHealth": 50,
    "baseDamage": 8,
    "moveSpeed": 3.5,
    "lootTable": "loot_goblin_common"
  },
  "goblin_chief": {
    "baseHealth": 150,
    "baseDamage": 20,
    "moveSpeed": 2.8,
    "lootTable": "loot_goblin_rare"
  }
}
```

**Incorrect** (`EnemyData.json`):

```json
{
  "Goblin": { "hp": 50 }
}
```

Violations: uppercase filename, uppercase key, no `[system]_[name]` pattern, missing required fields.
