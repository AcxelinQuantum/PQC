# Acxelin Quantum products

Post-quantum security products, each standalone: its own package, command, console, documentation, installer, tests and
release. A customer installs only the product that fits their problem.

| Product | Folder | Command | Status |
|---|---|---|---|
| **Acxelin QReadiness + CBOM**: find the cryptography in code, configuration, keys and endpoints, write a CycloneDX 1.6 CBOM, and rank what to migrate | [`products/readiness`](products/readiness/README.md) | `acxelin-qreadiness` | 1.4.0 |
| **Acxelin QGuard** with **QCertificate**: post-quantum TLS 1.3 in front of any TCP service, mutual TLS, and QCertificate, its ML-DSA certificate authority | [`products/tls`](products/tls/README.md) | `acxelin-qguard` | 1.3.0 |
| **Acxelin QVPN**: site-to-site IPsec with hybrid ML-KEM, WireGuard remote access and the desktop app | [`products/vpn`](products/vpn/README.md) | `acxelin-qvpn` | 1.3.0 |

Start with a product's own README: install (one command: `products/*/install.sh`, or `install.ps1` on Windows), first
steps, the console and the manual. The website is https://acxelinquantum.github.io/PQC/ (GitHub Pages from this repository; products at `/PQC/qreadiness/`,
`/PQC/qguard/` and `/PQC/qvpn/`). The products were Acxelin Readiness, TLS and VPN: the folders and Python modules keep
those names, and the old commands (`acxelin-readiness`, `acxelin-tls`, `acxelin-vpn`) work through 1.x.

## Repository layout

```
core/                 acxelin-core: shared mechanisms only (config, safe files, OpenSSL 3.5 binding, TLS contexts, CA, CRLs,
                      signers, EST, the console shell); no product names or policies
products/readiness/   Acxelin QReadiness + CBOM: src, tests, docs, examples, deploy (Docker), action.yml, installers
products/tls/         Acxelin QGuard and QCertificate (its CA): src, tests, docs, config, deploy (Docker, systemd), installers
products/vpn/         Acxelin QVPN: src, tests, docs, config, deploy (gateway image, systemd), packaging (desktop installers), installers
documents/            the release-verification guide and the product film script
website/              the shared home page and one section per product, built by tools/build_site.py
tools/                repository tooling: the site build, release gate, wheelhouse, browser test kit
```

No product imports another, and core works with nothing else installed; tests enforce both.

## Working on this repository

[CONTRIBUTING.md](CONTRIBUTING.md): the test commands per product, how releases work (one tag per product, core first),
and the rules every change follows. Security reports: [SECURITY.md](SECURITY.md).

© 2026 Acxelin Quantum, all rights reserved. See [LICENSE](LICENSE).
