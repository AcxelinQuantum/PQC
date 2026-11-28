# Tools

Scripts for the repository, not shipped with any product.

| Tool | What it does | Run by |
|---|---|---|
| `build_site.py` | Builds the showcase website from `website/` into `build/site` | the website and pages workflows |
| `capture_screens.py` | Remakes the website's screenshots from the real consoles in this checkout (needs Playwright, and OpenSSL 3.5 for QGuard) | by hand, when a console changes; the website tests say when |
| `wheelhouse.py` | Builds a product's offline install folder | the release workflow |
| `release_check.py` | Refuses a release tag whose version, changelog or core range does not match | the release workflow |
| `sbom.py` | Writes the CycloneDX SBOM of a release folder | the release workflow |
| `verify_release.py` | The customer's offline check of a release's checksums (shipped in each release folder) | customers; `documents/verify-a-release.md` |
| `perf.py` | The performance harness (`review/performance.md`) | the performance workflow, or by hand |
| `baselines.json` | The released commits the upgrade and rollback tests compare against | `tests/test_upgrade_rollback.py` |
| `browser/` | Playwright and axe-core for the browser tests | the test suites |
| `tests/` | Repository checks: layout, licences, citations, wording, release and supply-chain tools | `python -m pytest tools/tests` |
