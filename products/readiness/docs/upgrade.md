# Upgrading Acxelin QReadiness

## From Acxelin Readiness (1.3 and earlier) to QReadiness (1.4 and later)

The product was renamed. Nothing you have stops working.

| Before | Now |
|---|---|
| `acxelin-readiness` command | `acxelin-qreadiness`; the old command still works through 1.x and prints a one-line reminder |
| package `acxelin-readiness` | `acxelin-qreadiness` (the installer writes both commands) |
| release tags `readiness-vX.Y.Z` | `qreadiness-vX.Y.Z` |
| download `acxelin-readiness-VERSION-wheelhouse.tar.gz` | `acxelin-qreadiness-VERSION-wheelhouse.tar.gz` |
| GitHub Action `AcxelinQuantum/PQC/products/readiness@readiness-v…` | the same path `@qreadiness-v…`; the inputs are the same |
| container image `acxelin-readiness` | `acxelin-qreadiness` (build it yourself: see the manual) |

Unchanged: the settings file `.acxelin-readiness.toml`, the console's folder `~/.acxelin-readiness`, output folder and file
names, and the CBOM and SARIF formats, including the tool name `acxelin-readiness` inside them, so code-scanning alerts and
CBOM comparisons carry on.

Since 1.5.0 the console and report lead with "things to fix now" instead of the 0–100 score; `summary.score` is still
written for tools that read it.

## From Wolf Pack CBOM 1.x to Acxelin Readiness 1.0

Acxelin Readiness replaced Wolf Pack CBOM 1.x. The commands below use today's name, `acxelin-qreadiness`.

### Commands

| Before | Now |
|---|---|
| `wolfpack scan PATH` | `acxelin-qreadiness scan PATH` |
| `wolfpack merge ...` | `acxelin-qreadiness merge ...` |
| `wolfpack bench` | removed; the quality gate runs in the product's tests |
| `wolfpack scan --without ROLE` | removed; every detector always runs |

### Names read through every 1.x release

Each old name still works and prints a one-line warning naming the new one. Old names are removed no earlier than 2.0.0.

| Old | New | When both exist |
|---|---|---|
| `wolfpack:ignore` comments | `acxelin:ignore` | both are honoured (each applies to its own line) |
| `.wolfpack.toml` | `.acxelin-readiness.toml` | the new file is used and the old one is ignored, with a warning |
| `wolfpack:*` properties in CBOMs given to `merge` | `acxelin:*` | the new property wins |

### Changed results

- **CNSA 2.0:** AES whose key size wasn't observed is now reported as "unverified" and fails `--fail-on-policy`. Before, it passed. This is a deliberate fix, because compliance that wasn't observed isn't proven.
- **`merge`:** assets are now matched by what they are. Algorithms match by name and parameters, certificates and public keys by fingerprint. Secret material and protocol instances are never merged across systems.
  - When systems disagree about a field, every system's value is kept in `acxelin:observations`, and the field is named in `acxelin:conflict`.
  - `bom-ref` values are now `<asset type>/<hash>`.
- **GitHub Action path:** the Action is now `AcxelinQuantum/PQC/products/readiness`. Change `uses:` to it; the inputs are the same.
- **Output names:** the folder is `readiness-out/` (was `wolfpack-out/`), the SARIF file `readiness.sarif` (was `wolfpack.sarif`), and the report's CSV download `migration.csv` (was `wolfpack-migration.csv`). In `findings.json`, `sightings` is now `detections`.

## Rolling back

Reinstall the previous release. Scan outputs are files you keep; the command line has no state to restore. Baselines written by 1.0 still name every asset and its locations, so Wolf Pack 1.x can read them.
