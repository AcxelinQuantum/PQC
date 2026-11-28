# How to read this document

This is the knowledge-transfer guide to Acxelin Quantum's three post-quantum products: **QReadiness**, **QGuard** (with
**QCertificate**, its certificate authority) and **QVPN**. It is written for three kinds of reader:

- **Someone who needs to understand the products** (a mentor, a manager, a partner): read *Part 1* and the first section of
  each product chapter.
- **Someone who will install and use them**, including for a customer: *Part 2* (getting the software, now that the website
  has no downloads), then the product chapters.
- **An engineer who will change them**: everything, especially *Part 6* (the shared foundation), *Part 7* (how the
  repository is built, tested and released) and each product's "Where to change things".

Everything here was read from the repository (`AcxelinQuantum/PQC`, branch `main`) at the versions in the table below. Where
the code and the documents disagree, *Part 8* says so instead of guessing.

| Product | Package and command | Folder in the repository | Python module | Next version (unreleased) | Latest release |
|---|---|---|---|---|---|
| QReadiness | `acxelin-qreadiness` | `products/readiness/` | `acxelin_readiness` | 1.5.0 | `qreadiness-v1.4.0` |
| QGuard and QCertificate | `acxelin-qguard` | `products/tls/` | `acxelin_tls` | 1.4.0 | `qguard-v1.3.0` |
| QVPN | `acxelin-qvpn` | `products/vpn/` | `acxelin_vpn` | 1.4.0 | `qvpn-v1.3.0` |
| Shared foundation | `acxelin-core` | `core/` | `acxelin_core` | 1.4.0 | `core-v1.3.0` |

# Part 1: The products in one view

## The problem all three solve

Today's internet relies on public-key cryptography (RSA, elliptic curves, Diffie-Hellman) to agree keys and sign things. A
large enough quantum computer running Shor's algorithm breaks all of it. The danger is already real because of **"harvest
now, decrypt later"**: an attacker who records encrypted traffic today can decrypt it once such a machine exists. Anything
that must stay secret for ten years or more is exposed now.

The fix is standardised. NIST published **ML-KEM** (FIPS 203) for key exchange and **ML-DSA** (FIPS 204) for signatures in
2024. Governments have set deadlines: the US NSA's CNSA 2.0 requires new national-security purchases to comply from 2027 and
everything by 2031; NIST deprecates RSA and elliptic curves after 2030 and disallows them from 2035; the UK, EU, Canada and
India have similar timelines.

Organisations need to do three things: **find** their cryptography, **protect** the traffic that can't wait, and **connect**
their sites and people safely. Each Acxelin product does one of these.

## The three products

| | QReadiness | QGuard (with QCertificate) | QVPN |
|---|---|---|---|
| **The customer's question** | Where does our cryptography break? | How do we protect traffic that must stay secret for years, without rewriting our services? | How do we connect offices and people over links someone may be recording? |
| **What it is** | Software that finds the cryptography in code, configuration, certificates, binaries and live servers, says what a quantum computer (or an attacker today) breaks, and ranks what to change first | Software installed in front of websites, APIs and databases that makes every connection to them quantum-safe, with the customer's own certificate authority (QCertificate) built in | Site-to-site IPsec and WireGuard remote access, with every tunnel's keys agreed over quantum-safe connections using the customer's own certificates, plus a desktop app |
| **Who uses it** | Security and compliance teams, engineers and CI, management (board summary) | Operators of web apps, APIs, partner integrations and databases | Network administrators; staff use the desktop app |
| **What it produces** | A CycloneDX 1.6 CBOM, SARIF, an HTML report, a ranked "things to fix now" list, A–F grades for servers, compliance evidence | Quantum-safe TLS 1.3 in front of unchanged services; ML-DSA certificates; revocation | Encrypted tunnels whose keys are rotated and cut off on revocation |

## Is it a product, a service or a package?

This was the mentor's question about QGuard, and the answer is the same for all three. Each is a **product**: software the
customer downloads, installs on their own machines and runs themselves, the way they run nginx or a database. None is a
**service**: Acxelin Quantum runs nothing for the customer, holds no keys and sees no traffic; the products never contact
Acxelin. Each **ships as a package**: one offline installer folder per product (plus, for QVPN, desktop installers), giving
one command and a local web console.

## How a customer uses them

- **Through a console.** Each product has a local web console (`acxelin-qreadiness console`, `acxelin-qguard console`,
  `acxelin-qvpn console`). It opens in the browser already signed in and covers the everyday work. QVPN also has a desktop app
  for the people who connect.
- **Through the command line** for automation and setup: CI pipelines (QReadiness), running as a system service (QGuard,
  QVPN gateways), scripted certificate work.
- **Each product stands alone.** A customer installs only the one that fits. No product imports another, and the shared
  foundation (`acxelin-core`) works with nothing else installed.

## Naming history

The products have had three names; old names still matter because customers and files may use them.

| Era | Readiness | TLS product | VPN |
|---|---|---|---|
| First | Wolf Pack CBOM (tags `scanner-pack-v*`) | | |
| Until November 2026 | Acxelin Readiness, `acxelin-readiness`, tags `readiness-v*` | Acxelin TLS, `acxelin-tls`, tags `tls-v*` | Acxelin VPN, `acxelin-vpn`, tags `vpn-v*` |
| Now | Acxelin **QReadiness**, `acxelin-qreadiness`, tags `qreadiness-v*` | Acxelin **QGuard** with **QCertificate**, `acxelin-qguard`, tags `qguard-v*` | Acxelin **QVPN**, `acxelin-qvpn`, tags `qvpn-v*` |

What kept the old names, on purpose, so nothing in use breaks:

- Folders and Python modules (`products/tls`, `acxelin_tls`, and so on).
- The old commands: `acxelin-readiness`, `acxelin-tls` and `acxelin-vpn` still work through the 1.x line and print one line
  saying the product was renamed.
- Data folders, settings files (such as `.acxelin-readiness.toml`), systemd unit names, output formats, CBOM and SARIF tool
  names, and every key-derivation label.
- QVPN's desktop app files (`Acxelin VPN.exe`, `Acxelin VPN.app`, the `acxelin-vpn` Linux package), so an upgrade replaces
  the app instead of installing a second one. What people see says Acxelin QVPN.
- QReadiness still reads Wolf Pack's names (`wolfpack:ignore`, `.wolfpack.toml`, `wolfpack:*` CBOM properties) with a
  warning, through 1.x.

# Part 2: Getting and installing the software

The website (https://acxelinquantum.github.io/PQC/) is now a short showcase: one page per product with its film and a real
console screenshot, ending at "Talk to an Expert". It deliberately has **no install instructions and no downloads**. This
part replaces them.

## Where the software comes from

Every release is published on the repository's GitHub releases page: https://github.com/AcxelinQuantum/PQC/releases. Each
product release has:

| File | What it is |
|---|---|
| `acxelin-<product>-<version>-wheelhouse.tar.gz` | The installer folder: the product's wheels with acxelin-core and every dependency for Linux (x86-64, ARM), Windows x64 and Apple-silicon Macs, Python 3.11–3.14; `install.sh`, `install.ps1`, README, manual and other docs, licence, example settings, systemd units, `VERIFY.md` and `verify_release.py` |
| `SHA256SUMS` | The checksum of every file, including every file inside the folder |
| `acxelin-<product>-<version>.cdx.json` | The software bill of materials (CycloneDX 1.6): every wheel with its SHA-256 |
| QVPN only: `Acxelin-QVPN-<version>-Setup.exe`, `Acxelin-QVPN-<version>.dmg`, `acxelin-vpn_<version>_amd64.deb` | The desktop app for Windows, macOS and Ubuntu/Debian |

Nothing is published to PyPI, on purpose. Container images are built by the release, but the GHCR images can't be pulled
anonymously yet, so the documentation tells customers to build them (below).

> **The repository and its releases are public today.** Anyone with the link can download a release, even though the website
> says access is by request and the licence calls the software confidential. For the "by request" model, make the
> repository private (GitHub Pages for a private repository needs a paid GitHub plan) and send customers the release files
> or a time-limited link. See *Part 8*.

## Prerequisites

- **Python 3.11 to 3.14.**
- **OpenSSL 3.5 or newer** for post-quantum TLS. The products load it through their own binding, never the `openssl`
  command.

| System | How to get OpenSSL 3.5+ | What to set |
|---|---|---|
| Debian 13, Ubuntu 25.04 or newer | Already there | Nothing |
| Older Linux | Build or install 3.5 into a folder | `ACXELIN_OPENSSL` and `LD_LIBRARY_PATH` to its `lib` folder (the installer can bake them in) |
| macOS | `brew install openssl@3` | Found automatically, or `ACXELIN_OPENSSL=$(brew --prefix openssl@3)/lib` |
| Windows | `choco install openssl -y` (or winget `ShiningLight.OpenSSL.Light`) | `ACXELIN_OPENSSL=C:\Program Files\OpenSSL-Win64\bin` |

On Windows, anyone who can write to a folder on PATH could plant a DLL, so set `ACXELIN_OPENSSL` and keep PATH folders
admin-only. Intel Macs aren't supported natively; use the Docker image.

## Step 1: verify the download

Before installing, check the files are exactly what Acxelin released. The full guide ships in every folder as `VERIFY.md`.

```
sha256sum -c SHA256SUMS --ignore-missing                    # Linux: each line prints OK
shasum -a 256 acxelin-qguard-1.3.0-wheelhouse.tar.gz        # macOS: compare with SHA256SUMS
Get-FileHash .\acxelin-qguard-1.3.0-wheelhouse.tar.gz       # Windows: compare (case doesn't matter)
gh attestation verify acxelin-qguard-1.3.0-wheelhouse.tar.gz --owner AcxelinQuantum   # optional: "Verification succeeded"
```

After unpacking, `python3 acxelin-…-wheelhouse/verify_release.py SHA256SUMS` checks every file inside the folder and prints
"every file matches its checksum, and nothing else is in the release folder".

## Step 2: install

The installer is the same for every product; only the names change.

**Linux and macOS**

```
tar xzf acxelin-qguard-1.3.0-wheelhouse.tar.gz
cd acxelin-qguard-1.3.0-wheelhouse
sh install.sh
```

**Windows (PowerShell)**

```
tar xzf acxelin-qguard-1.3.0-wheelhouse.tar.gz
cd acxelin-qguard-1.3.0-wheelhouse
Unblock-File .\install.ps1
powershell -ExecutionPolicy RemoteSigned -File .\install.ps1
```

What the installer does:

- Finds Python 3.11+ and creates a private environment: `~/.acxelin/<folder>` on Linux and macOS (`tls`, `vpn` or
  `readiness`), `%LOCALAPPDATA%\Acxelin\<folder>` on Windows. `ACXELIN_PREFIX` changes the location.
- Installs offline from the wheels in the folder, with the product's optional parts where they resolve.
- Writes the command to `~/.local/bin` (or `%LOCALAPPDATA%\Acxelin\bin`, added to the user PATH), under both the new and the
  old name. `ACXELIN_BIN` changes the location.
- Finds OpenSSL 3.5 (the system's if new enough, then Homebrew's, then `ACXELIN_OPENSSL`) and bakes it into the command.
- Runs `doctor` and prints where to start.
- No administrator rights, nothing system-wide. Remove it with `sh install.sh --uninstall` or `install.ps1 -Uninstall`;
  certificates, consoles and settings stay where they are.

**From a repository checkout** (engineers): run the same `install.sh` from `products/<folder>`; it installs `core` and the
product from the checkout.

## Step 3: check the machine and start

```
acxelin-qguard doctor          # or acxelin-qreadiness doctor, acxelin-qvpn doctor
acxelin-qguard console         # opens the console, already signed in
```

`doctor` prints `ok`, `WARN` or `FAIL` lines and exits 0 (ready), 1 (warnings, with `--strict`), 2 (a failure) or 3 (this
machine can't run it).

## Containers (built by the customer)

Each product has a Dockerfile in `products/<folder>/deploy/`, based on `python:3.13-slim-trixie` (Debian 13, OpenSSL 3.5)
pinned by digest. Build from the repository root:

```
docker build -f products/readiness/deploy/Dockerfile -t acxelin-qreadiness .
docker build -f products/tls/deploy/Dockerfile -t acxelin-qguard .
docker build -f products/vpn/deploy/Dockerfile -t acxelin-qvpn .
```

On Windows, clone with `git -c core.autocrlf=false` (the repository also pins shell scripts and Dockerfiles to LF line
endings in `.gitattributes`). A console in a container runs with `console --container`, published only on
`127.0.0.1`.

## QVPN's desktop app

| System | File | Installs |
|---|---|---|
| Windows 10/11 x64 | `Acxelin-QVPN-<version>-Setup.exe` | `C:\Program Files\Acxelin VPN\`, Start-menu shortcut "Acxelin QVPN", optional start at login |
| macOS (Apple silicon) | `Acxelin-QVPN-<version>.dmg` | `Acxelin VPN.app`; WireGuard's tools via `brew install wireguard-tools` |
| Ubuntu, Debian x64 | `acxelin-vpn_<version>_amd64.deb` | `/opt/acxelin-vpn/`, commands `acxelin-qvpn` and `acxelin-vpn`, menu entry "Acxelin QVPN"; `sudo apt install ./acxelin-vpn_<version>_amd64.deb` also installs WireGuard's tools |

The installers aren't code-signed yet: Windows shows SmartScreen ("More info", then "Run anyway") and macOS needs "Open
Anyway". On Windows, install WireGuard for Windows too; the installer reminds you.

# Part 3: QReadiness

## What it is and why a customer needs it

> Find every piece of cryptography your organisation depends on, see which of it a quantum computer breaks, and know what to
> migrate first.

Every national roadmap starts with an inventory. QReadiness builds it: it reads code, configuration, keys and certificates,
binaries and container images, dependency manifests, packet captures, live TLS and SSH servers (including mail servers over
STARTTLS) and AWS KMS and ACM, and writes a **CBOM** (Cryptography Bill of Materials, CycloneDX 1.6). It then ranks what
to change first and gives evidence an auditor accepts.

![The QReadiness console](screens/qreadiness-console.png)
*The QReadiness console: a scanned project, its things to fix now, owners and trend.*

**Who it's for:** engineers and CI (scan, SARIF, a gate that fails the build), security and compliance staff (reports,
standards, evidence), and management (the printable board summary).

## What it finds

| Asset kind | Examples |
|---|---|
| Algorithms | RSA, ECDSA, AES, SHA-1, MD5, ML-KEM, ML-DSA… with parameters, modes and padding |
| Protocols | TLS, SSH, IPsec (IKEv2, including RFC 9370 ML-KEM), QUIC, mail STARTTLS, as configured and as seen on the wire |
| Certificates | Algorithm, key size, issuer, expiry |
| Keys and key material | Private keys, keystores, SSH keys, KMS keys (described, never copied) |
| Libraries | OpenSSL, Bouncy Castle and other crypto packages in dependencies, binaries and images |

| Where it looks | Detail |
|---|---|
| Source code | Python, JavaScript/TypeScript, Java (and Kotlin, Scala, Groovy), Go, C/C++, Rust, C#, Swift, PHP, Ruby, shell, PowerShell, Dockerfiles |
| Configuration | YAML, JSON, TOML, INI, nginx, Apache, sshd, Kubernetes, Terraform |
| Keys and certificates | PEM/DER, SSH keys and `known_hosts`, PKCS#12, JKS/JCEKS (read without a password) |
| Encrypted volumes | LUKS1/2, qcow2, BitLocker, dmg, crypttab (headers only) |
| Binaries and images | Executables, `docker save` and OCI archives |
| Dependencies | Manifests and lockfiles |
| Traffic | Packet captures (`--pcap`): TLS, SSH, QUIC Initial, IKEv2 |
| Live servers | TLS (`--tls`), SSH (`--ssh`), mail (`smtp://`, `submission://`), plus mqtts, amqps, ldaps, imaps, pop3s, smtps, ftps, sips |
| Cloud | AWS KMS and ACM (`--aws REGION`, list and describe permissions only) |
| GitHub | A repository link is downloaded through the API; nothing is executed |

## What it produces

A `scan` writes to `readiness-out/`:

| File | For |
|---|---|
| `cbom.json` | The CycloneDX 1.6 CBOM, readable by any CBOM tool |
| `readiness.sarif` | Code scanning (GitHub shows it as alerts). Rule IDs `ACX-<algorithm>`, `ACX-ALERT`, `ACX-P001`–`P005` |
| `findings.json` | Every detection and its verdict, with short code snippets (treat as sensitive) |
| `relationships.json` | Which code uses which cryptography |
| `report.html` | The human report, critical to OK, with a fix for each finding and a `migration.csv` download |

Other commands write endpoint grades (`grade --json/--html`), compliance evidence (`report`: `report.html`,
`assessment.json`, `assessment.csv`), an organisation inventory (`merge`: `inventory.html`, `inventory.json`, `cbom.json`)
and changes over time (`watch`: `changes.json`).

## How it decides what matters

**"Things to fix now"** is the headline: critical and high findings outside test code. Test-only findings are listed apart
("Only in tests") and drop one tier; they are never hidden. The old 0–100 score is no longer shown because adding harmless
cryptography raised it (it is still written as `summary.score` for tools that read it; the new field is
`summary.headline`).

| Tier | When |
|---|---|
| Critical | Broken today: legacy algorithms, under 112 bits of strength, ECB mode, signatures over MD5/SHA-1 (high if exposure is low) |
| High | Quantum-breakable key exchange or encryption whose data must stay secret past the expected arrival of a quantum computer: *data lifetime + migration time > years left* (Mosca's inequality; defaults 10 and 5 years, quantum computer in 2035) |
| Medium | Other quantum-breakable uses; classical key exchange offered next to a hybrid one |
| Low | Grover-weakened symmetric crypto under 192 bits; non-security uses (inside HMAC, PBKDF2, OAEP), self-signatures, trust-store roots |
| OK | Quantum-safe, or symmetric crypto at 192 bits or more |

Data lifetime per service can come from a CMDB spreadsheet (`keep secret (years)` column). Each finding also says *how it
was seen* (negotiated, offered, in code, configured, supported only) and the *effort* to fix it.

**Grades for live servers (A–F):**

| Grade | Meaning |
|---|---|
| A | Post-quantum key exchange only |
| B | Post-quantum offered, classical still accepted |
| C | Classical only: traffic recorded today can be decrypted later |
| F | Unreachable, no TLS, or a mail server without STARTTLS |

**Standards** (`--policy`, or deadlines in the console): `nist-ir-8547` (deprecated 2030, disallowed 2035), `cnsa-2.0`
(2027 new purchases, 2030 phase-out, 2031 mandatory; only pure ML-KEM-1024 counts for TLS), `india-dst` (2029 for critical
infrastructure; 2033 for enterprises via `india_deadline`). The console's deadline list covers the US, UK, EU, Canada and
India. `report` also maps findings to NIST CSF 2.0, DORA and NIS2 controls.

## Daily use: the console

`acxelin-qreadiness console` (port 8900; home folder `~/.acxelin-readiness`, or `ACXELIN_READINESS_HOME`). Four tabs:

- **Projects:** choose the repositories folder; add a folder or GitHub link (private repositories use a saved fine-grained
  token); import another tool's CBOM; scan or cancel. Each project shows things to fix now, a 30-scan trend, coverage (with a
  warning if it falls 10 points), what changed, search, and per finding: **assign an owner**, due date and status (To do,
  Planned, In progress, Fixed, Accepted risk with a reason and end date), the example fix and effort, and a CSV download.
  Owners can come from a CMDB export or `CODEOWNERS`. **Remove from QReadiness** deletes saved results, never the
  repository.
- **Overview:** all projects side by side, **Scan every project**, add every repository of a GitHub organisation, the
  services most at risk, third-party libraries, scheduled scans, **Deadlines that apply to you**, and a printable **Board
  summary** (marked provisional if coverage is under 80% or projects are unscanned).
- **Endpoints:** grade hosts; each keeps its own dated history; what changed; forget a host; CBOM and CSV export.
- **What it tracks:** the asset kinds, the algorithm catalogue and the sources it reads.

## Daily use: the command line

| Command | What it does | Key options |
|---|---|---|
| `scan [PATH]` | Scan a folder, GitHub link or image, plus live endpoints | `--tls`, `--ssh`, `--pcap`, `--aws` (repeatable), `--changed-since REF`, `--baseline CBOM`, `--fail-on {critical,high,medium,low}`, `--policy`, `--fail-on-policy`, `--owners CSV`, `--exclude`, `--test-path`, `-o` |
| `grade TARGETS…` | Grade TLS and SSH servers A–F | `--json`, `--html`, `--timeout 8` |
| `report` | Compliance evidence | `--certs DIR`, `--targets`, `--cbom` |
| `merge CBOM…` | One organisation inventory from many CBOMs (other tools' too) | `--name`, `--history`, `--fail-on` |
| `watch [PATH]` | Rescan on a schedule and record what changed | `--every 24` (hours), `--once`, `--on-change CMD` |
| `doctor` | Is OpenSSL 3.5 there, are the extra language parsers installed | |
| `console [link]` | The console; `link` prints a fresh sign-in link | `--port 8900`, `--home`, `--container`, `--no-browser` |

Exit codes: 0 finished, 1 bad usage or unreadable input, 2 a gate fired (`--fail-on`, a policy), 3 `grade` couldn't reach or
grade an endpoint.

Probing is gentle by default: 2 new connections a second per host, one at a time. `--workers` or `--aggressive` speed it up;
use them only on hosts you own. Pacing is not an authorisation to scan.

**In CI** (GitHub Action):

```
- uses: AcxelinQuantum/PQC/products/readiness@qreadiness-v1.4.0
  with:
    fail-on: high
    baseline: previous-cbom.json      # fail only on new findings
```

Inputs: `path`, `fail-on`, `baseline`, `args`, `output` (`readiness-out`), `upload-sarif` (needs `security-events:
write`). The job uploads the results as an artifact named `acxelin-qreadiness`.

**Settings file** `.acxelin-readiness.toml` at the root of the scanned folder (or `--config FILE`): `exclude`, `test_paths`,
`include_vendor`, `shelf_life`, `migration`, `crqc_year`, `threshold`, `fail_on`, `name`, `policy` (with `[policy]`
`profiles`, `as_of`, `cnsa_deadline`, `india_deadline`, `forbid`, `min_bits`, `require_hybrid`, `fail`), `rate`, `workers`,
`aggressive`. Unknown keys are an error. For safety, `tls`, `ssh` and `aws` in a scanned repository's own file are ignored
with a warning: a repository can't choose which hosts or AWS accounts get probed.

**Silencing a finding:** `acxelin:ignore <reason>` on the line or the line above. The finding stays in `findings.json` as
suppressed; the reason isn't verified.

## Limits, stated honestly

- No finding isn't proof of absence; algorithm names built at run time are missed.
- Configuration shows what is offered, not what is used.
- The labelled corpus score is a regression floor, not a claim about unseen code. On an independent benchmark (OWASP
  Benchmark Java, 482 tests, run once) precision was 0.890 and recall 0.846; don't quote that as general recall.
- An endpoint given by IP address gets no SNI, so it may show a different certificate; use the host name.
- Without OpenSSL 3.5, certificates of servers that only offer post-quantum key exchange are reported "not observed",
  never as passing.

## How it works inside

The pipeline (`src/acxelin_readiness/pipeline.py`): **detect** everything (each source has a detector in `detectors/`),
**verify** what the evidence supports (each kind of evidence has a confidence, from 0.35 for a string to 1.0 for a live
handshake; at or above 0.6 a detection is accepted), then **rank** (tiers, exposure, remedies) and add alerts (private keys
in the repository, expired certificates, certificates valid past 2030, library CVEs).

| Module | Role |
|---|---|
| `cli.py` | Commands |
| `detectors/` | One module per source (lexer, Python data flow, keystores, QUIC, IKE, live probes…) |
| `catalog.py` | Every known algorithm: family, primitive, threat (Shor, Grover, legacy, safe), bits, OID, replacement |
| `verify.py`, `rank.py` | Confidence and tiers |
| `compliance.py` | Standards, deadlines and the console's country roster |
| `cbom.py`, `report.py` | CBOM, SARIF, HTML and terminal output |
| `endpoints.py`, `starttls.py` | TLS grading, mail STARTTLS |
| `inventory.py`, `evidence.py` | `merge` and `report` |
| `remote.py`, `image.py` | GitHub downloads (bounded: 256 MB download, 50,000 files) and container images |
| `workspace.py`, `console.py`, `console.html` | The console |
| `crawler*.py` | Relationships (tree-sitter for JS/TS/Java/Go is the optional `crawler` extra) |

**The quality gate:** `bench/corpus/` holds about 84 files of deliberately weak code and a test key; `bench/truth.json` lists
the 179 expected (file, algorithm family) pairs. `tests/test_quality_gate.py` requires precision and recall of 1.0 and pins
the hash of `truth.json`. Labels change only in a commit titled `truth:` that the owner approves.

## Troubleshooting

| You see | Do |
|---|---|
| A non-security hash flagged | Add `acxelin:ignore <reason>` |
| Noise from vendored or generated code | Add it to `exclude` (`vendor/` and `node_modules` are skipped already) |
| "certificates … not observed" | Set `ACXELIN_OPENSSL`, or use the Docker image |
| Docker "Permission denied" | Add `--user "$(id -u):$(id -g)"` |
| "This computer couldn't verify the certificate (…)" | This machine's root store is out of date; the grade is unaffected. A proxy is only named when two or more hosts share an unknown issuer |
| CI fails on old findings | Use `--baseline` with the previous CBOM |
| A paced scan is slow | `--workers` or `--aggressive`, only on hosts you own |

## Where to change things

| Change | Files |
|---|---|
| Add a detector | A module in `detectors/` returning `Detection`s; call it from `pipeline.detect()`; add the source to `coverage.py` `SOURCES` and manual §8 (a test keeps them equal); add labelled corpus files and `truth.json` entries in a `truth:` commit |
| Add an algorithm | `catalog.py` `CATALOG` and `_ALIASES`; check `rank.assess`, `compliance.CNSA`, `remedy.py`, `examples.py`, `endpoints.py` group lists. It appears in "What it tracks" by itself |
| Add a standard or deadline | `compliance.py` (`PROFILES`, `evaluate()`, `KEYS`, `ROSTER` with source links); `evidence.py`; manual; `test_deadlines`, `test_cnsa2_faq_readiness` |
| Change ranking | `rank.assess` and `Horizon`; defaults in `cli.py` |
| Change a report | `report.py`, `brand.py`; CBOM and SARIF in `cbom.py` (a wire format: breaking changes go in the CHANGELOG) |
| Change the console | `console.html`, with data from `console.py` and `workspace.py`; keep terminal and console counts equal (`workspace.headline`, a test compares them) |

# Part 4: QGuard and QCertificate

## What it is and why a customer needs it

> Software you install in front of your websites, APIs and databases so that every connection to them is protected against
> future quantum computers, with your own certificate authority built in, and without changing the services themselves.

Most organisations can't rewrite every service in time: some were built years ago, some are vendor code, some can't be
restarted. QGuard sits in front of them and does the post-quantum TLS 1.3 itself. The service behind it keeps running
exactly as it is. A connection that can't meet the chosen protection ends; nothing falls back silently.

One command, `acxelin-qguard`, runs three things:

- **The guard** (called `edge` in commands and settings): sits in front of any TCP service and lets in only quantum-safe
  connections.
- **QCertificate**: the customer's own certificate authority. It issues, renews and revokes ML-DSA certificates, keeps the
  revocation list fresh, and enrols machines over EST (RFC 7030) and ACME (RFC 8555). Public certificate authorities don't
  issue ML-DSA certificates yet, so internal systems need their own to start now.
- **The console**: a local web page for the everyday work.

![The QGuard console](screens/qguard-console.png)
*The QGuard console: protected services, what connected, and what needs attention.*

## The key ideas

**A protected service** is one entry in the console: the name and port people use, and where the service runs now. In the
settings file it is a *route* (`[[edge]]`).

**What kind of service it is** decides the protection:

| Kind | Protection | Why |
|---|---|---|
| Public website | **Quantum-safe, browsers welcome** (`transition`), plus a public certificate | Browsers can't verify ML-DSA certificates yet, so browsers get an ordinary public certificate while quantum-safe key exchange is still used where the browser supports it (Chrome, Edge and Firefox support hybrid ML-KEM) |
| Internal app or API | **Quantum-safe only** (`strict`) | Clients you control can be given OpenSSL 3.5 and your CA |
| Partner API | **Quantum-safe only**, and partners need a client certificate from QCertificate | Only partners you issued a certificate to get in; revoke to cut one off |
| Database or other service | **Quantum-safe only** | Any TCP service: PostgreSQL, Redis, MQTT… |

| Protection (policy) | Key exchange allowed | Certificates |
|---|---|---|
| Quantum-safe only (`strict`, the default) | X25519MLKEM768, SecP384r1MLKEM1024, SecP256r1MLKEM768 | ML-DSA-87, -65, -44 |
| Quantum-safe, browsers welcome (`transition`) | The post-quantum groups plus X25519, P-256, P-384 | Any |
| CNSA 2.0 only (`cnsa2`) | ML-KEM-1024 only | ML-DSA-87; cipher AES-256-GCM only |

**Watch only, then enforce.** A service can start in *watch only* mode (`shadow`): everyone is served, and QGuard reports
who *would* be refused and why. When nobody it has seen would be refused, the console says the service is ready, and **Turn
on enforcement** switches it on. (A public website can't start in watch mode; it uses `transition`.)

**Forwarded headers.** Web apps behind a proxy need to know the visitor's address and that the visit was HTTPS; otherwise
WordPress-style apps redirect to `http://` and see every visitor as 127.0.0.1. With `forwarded_headers = true` (the console
sets it for every kind except databases), QGuard removes any `Forwarded`, `X-Forwarded-*` or `X-Real-IP` header the visitor
sent and adds its own `X-Forwarded-For`, `X-Forwarded-Proto: https` and `X-Forwarded-Host`. Ambiguous requests, the shapes
behind request smuggling, are refused with 400. HTTP/1.x only.

**Two modes.** `terminate` (the usual): quantum-safe clients → QGuard → the plain service. `originate`: a plain local client
→ QGuard → a remote QGuard over quantum-safe TLS, for programs that can't be changed on either side.

## First run

`acxelin-qguard console` opens the console (port 8900; home folder `~/.acxelin-tls`, or `ACXELIN_TLS_HOME`). First run is
two steps:

1. **Create your certificate authority**: a name and a passphrase. The passphrase stays in memory only; after a restart the
   console asks to unlock it.
2. **Protect your first service**: choose the kind, the address people use (for example `shop.acme.example`, port 443),
   and where the service runs now (for example `127.0.0.1:8080`). For a public website, give the public certificate's full
   chain and key files. The console issues the server certificate from QCertificate, writes the settings, and can start
   QGuard on this computer.

A one-minute tour without the console: `acxelin-qguard try` creates a CA, a web server and a guard in a temporary folder,
then shows a post-quantum client getting through and a classical one refused.

## Daily use: the console

Five tabs:

- **Overview**: every service with its kind, protection, mode and when it was last seen; **Needs attention** lists services
  with problems, QGuard not running, watched services that are ready to enforce, certificates expiring within 30 days, and
  a revocation list that is missing or has less than 2 days left.
- **Services**: protect a service; per service, "N of M connections quantum-safe", refused, would be refused once
  enforcing, did not trust the certificate, and why; **Watch only**, **Turn on enforcement** (both confirmed), edit,
  remove, check connection. **Start QGuard** / **Stop QGuard** for a guard started from the console. Routes written by hand
  in the settings file are shown but edited there.
- **QCertificate**:
  - **Certificates**: issue for a service or for a person, device or partner (1–3650 days, default 397), renew, revoke
    with a reason, **Renew what expires soon**, **Refresh the revocation list**.
  - **Downloads**: certificate and chain (zip), with the private key (zip, only on explicit request, never for a revoked
    certificate or an encrypted key), or one PEM file with the full chain and key. Every download is audited.
  - **Let a device enrol**: one-time EST tokens (1–720 hours), shown once with the exact command for the other machine.
  - **ACME account keys** (external account binding) for certbot, shown once with a certbot command line.
  - **The authority**: name, algorithm, fingerprint, validity, folder, lock state, download the CA certificate, **Lock
    now**, recent activity.
- **Check a connection**: any host or host:port; trust public authorities (as a browser does) or QCertificate; optionally
  present a client certificate. Gives a plain verdict ("Key exchange: quantum-safe (X25519MLKEM768). Certificate: …") with
  the details folded away.
- **Settings**: where the settings file, data and log are; this computer's health checks; other QGuard services to watch by
  their status address.

The console writes the same settings file the QGuard service reads (`~/.acxelin-tls/edge.toml` by default;
`/etc/acxelin-tls/edge.toml` on a Linux server, which the administrator must be able to write). A running guard applies
changes within seconds: unchanged routes keep their connections, a route that fails to start keeps its old settings, and
certificate files are re-read without a restart. Before saving, the console loads a trial copy, so it never writes a setting
the guard would reject.

## Daily use: the command line

| Command | What it does |
|---|---|
| `try` | The one-minute tour |
| `doctor [--ca DIR] [--config FILE] [--strict]` | Machine, CA and settings checks |
| `console [link]` | The console; `link` prints a fresh sign-in link |
| `edge --config edge.toml` | Run the guard (or flags: `--mode`, `--listen`, `--target`, `--policy`, `--cert`, `--key`, `--ca`, `--crl`, `--crl-url`, `--fallback-cert/-key`, `--shadow`, `--require-client-cert`, `--forwarded-headers`, `--proxy-protocol`, limits, `--workers`) |
| `status [--url http://127.0.0.1:9100]` | A running guard's status |
| `connect HOST:PORT` | Check a connection (`--ca`, `--cert/--key`, `--send`, `--json`) |
| `bundle nginx\|postgres\|pgvector\|mqtt --host H` | A ready Docker Compose project with the guard and certificates |
| `serve` | A TLS echo server for testing clients |
| `evidence create` / `verify` | A signed audit bundle: build, settings, doctor, certificates, CBOM, status |
| `ca init` | Create the CA (ML-DSA-87, 10 years, encrypted). Key in a file, AWS KMS (`--kms`), a signing command, or PKCS#11 (HSM); `--parent` for an intermediate under an offline root |
| `ca issue server\|client\|site CN` | Issue a certificate (ML-DSA-65, 397 days; `--hours` for short-lived) |
| `ca renew`, `ca revoke`, `ca crl`, `ca maintain`, `ca list` | Lifecycle; run `ca maintain` daily (the systemd timer does) |
| `ca sign-csr`, `ca csr` | Certify a key made elsewhere; make an ML-DSA key and CSR for certbot |
| `ca token`, `ca serve`, `ca enroll`, `ca oidc` | EST enrolment: one-time tokens, the EST service (port 9443), the client, company sign-in (OIDC) |
| `ca acme`, `ca eab` | The ACME service (loopback 14000) and account keys |
| `ca ocsp`, `ca publish` | OCSP answers for stapling; serve `/crl.pem` and `/ca.crt` over HTTP (port 8080) |

The CA passphrase comes from `ACXELIN_TLS_CA_PASSPHRASE` or a prompt, never from the command line.

## Running it in production

- **Linux (systemd)**: install as root into `/opt/acxelin-tls`
  (`ACXELIN_PREFIX=/opt/acxelin-tls ACXELIN_BIN=/opt/acxelin-tls/bin sh install.sh`), create a system user `acxelin`, put the
  settings in `/etc/acxelin-tls/edge.toml`, copy the units from `deploy/systemd/`:
  - `acxelin-tls-edge.service` runs the guard (sandboxed, `Restart=always`, reload with `systemctl reload`);
  - `acxelin-tls-maintain.service` and `.timer` run `ca maintain` daily, with the passphrase in `/etc/acxelin-tls/ca.env`
    (mode 600).
- **Docker**: the image (built yourself) runs as uid 10001 with `/data` as its volume; ports 8443 (guard) and 9100
  (metrics).
- **Windows**: there is no Windows service; run `acxelin-qguard edge --config …` as a scheduled task at start-up as SYSTEM
  (manual §8).

Status and metrics are served on `[metrics] listen` (the console uses `127.0.0.1:9100`): `/status` (JSON per route),
`/metrics` (Prometheus: `acxelin_tls_connections_active`, `acxelin_tls_events_total`, `acxelin_tls_group_total`).

## Ports

| Port | Use |
|---|---|
| 443 or 8443 | The guard (the console defaults to 443; the command line to 8443) |
| 9100 | Status and metrics (loopback) |
| 8900 | Console (loopback) |
| 9443 | EST enrolment |
| 8080 | Publishing the CRL and CA certificate |
| 14000 | ACME service (loopback); 80 for its http-01 checks |

## Limits, stated honestly

- Browsers can't verify ML-DSA certificates. A public website needs `transition` plus a public certificate; with `strict`
  browsers show "Your connection is not private", with `cnsa2` a cipher-mismatch error. Browsers can't present ML-DSA client
  certificates either: client certificates are for programs.
- HTTP/2 isn't served (`alpn` only chooses a route). Forwarded headers cover HTTP/1.x.
- Downloads are PEM only; there's no PFX for Windows tools.
- ACME issues ML-DSA certificates only through `certbot --csr`, which certbot doesn't renew by itself.
- A revoked partner keeps access until the guard has the new CRL: at once on the CA machine, within `crl_every` (60 s)
  elsewhere.
- KMS, HSM and signing-command keys are implemented but not tested against real HSMs or cloud accounts (PKCS#11 on SoftHSM2
  only). Validation was on Linux with OpenSSL 3.5.9.
- Not protected: the CA machine itself, and the service behind QGuard, which sees plain traffic on its private link.

## How it works inside

| Module (`src/acxelin_tls/`) | Role |
|---|---|
| `cli.py` | Commands, `doctor`, `status`, `try` |
| `edge.py` | Routes, the relay, shadow mode, PROXY protocol, OCSP stapling, settings file read/write, live reload, metrics |
| `edge_commands.py` | `edge`, `bundle`, `serve`, `connect` |
| `forwarded.py` | The forwarded-headers state machine |
| `shadow.py` | Reads a ClientHello to say why a client would be refused |
| `policies.py` | The three protections, on core's `tls.Policy` |
| `connection.py` | Key names, verdicts, why a connection failed (shared by `connect` and the console) |
| `checks.py` | `doctor` |
| `ca_commands.py`, `acme.py` | QCertificate's commands and the ACME service |
| `bundles.py`, `evidence_commands.py`, `common.py` | Compose projects, evidence, shared helpers |
| `console.py`, `console.html` | The console |

The certificate authority, EST, OCSP, OIDC, KMS/HSM signers, TLS contexts and the console's security all come from
`acxelin-core` (*Part 6*).

## Troubleshooting

| You see | Do |
|---|---|
| `this machine's OpenSSL … is too old` | Install OpenSSL 3.5, set `ACXELIN_OPENSSL` (and `LD_LIBRARY_PATH` on Linux), or use Docker |
| `no suitable key share` | The client needs OpenSSL 3.5+, or use `transition` |
| `peer did not return a certificate` | Give the client a certificate from QCertificate |
| The server closes right after the handshake | Client certificate refused, or the service behind is down: read the guard's log |
| Every client refused after a week | The revocation list expired: run `ca maintain` and schedule it daily |
| Browser: "Your connection is not private" | Public website: `transition` plus a public certificate |
| App redirects to `http://` or sees every visitor as 127.0.0.1 | `forwarded_headers = true` |
| `port 443 is already in use` | Stop the other program or choose another port |
| `The CA key is locked` | Unlock it with the passphrase |

## Where to change things

| Change | Files |
|---|---|
| A protection policy | `policies.py`; `shadow.py` reasons; `connection.PQ_GROUPS`; console labels (`console.html` `PROTECTION`); manual; `test_downgrade.py`, `test_shadow.py` |
| A console screen or action | Server: a method on `TLSConsole` (`@task`, raise `ValueError` for user errors, call `self.audit`) registered in `build()`; page: `console.html` (`TABS`, the view, `call(…)`); tests `test_console*.py`, `tests/browser/test_journeys.py` |
| A route setting | `edge.Route` and `validate()`; use it in `Edge`; `load_config` if it is a path; `checks.py`; CLI flag in `edge_commands`; console `save_service`; `config/example.toml`, manual; `test_settings_file.py`, `test_hardening.py` |
| A command | Its parser in `cli.parser`, `edge_commands.add` or `ca_commands.add`; errors raise `ValueError`/`CAError`/`TLSError` so the CLI prints one line |

# Part 5: QVPN

## What it is and why a customer needs it

> Software that links your offices to each other and your people to your network, with every tunnel's keys agreed over
> quantum-safe connections using your own certificates, so traffic recorded today stays private, and a revoked office or
> person is cut off within seconds.

VPN tunnels carry exactly the traffic an attacker would record today. QVPN keeps standard, trusted tunnel software
(strongSwan IPsec between sites, WireGuard for people) and adds what they lack: every tunnel's keys are agreed over TLS 1.3
with hybrid ML-KEM and ML-DSA certificates from the customer's own CA, rotated often, and cut off on revocation. A key
agreement that can't meet the policy fails; nothing falls back silently.

![The QVPN console](screens/qvpn-console.png)
*The QVPN console: people, their invitations and who is connected.*

![The QVPN desktop app](screens/qvpn-app.png)
*The desktop app a person uses to connect.*

## The key ideas

**Sites** (office to office): strongSwan IPsec between Linux gateways. Each pair of sites agrees keys over ML-DSA mutual TLS
(port 7443) and derives a 32-byte IKE pre-shared key and a 32-byte post-quantum PPK (RFC 8784) from it; IKE itself uses
hybrid ML-KEM. Keys are re-agreed every hour by default (`rotate_minutes`). Profiles:

| Profile | IKE key exchange |
|---|---|
| `standard` | X25519 + ML-KEM-768 |
| `high` | P-384 + ML-KEM-1024 |
| `cnsa2-rfc9370` | P-384 + ML-KEM-1024, PRF SHA-384 |
| `cnsa2` | ML-KEM-1024 alone |

**People** (remote access): a WireGuard gateway. Each person gets an **invitation file** (`NAME.acxinvite`, valid 24 hours by
default, single use). The desktop app enrols them (EST, port 9443), and their WireGuard pre-shared key is agreed over ML-DSA
mutual TLS with the gateway (port 7444) and **rotated every 2 minutes**, bound to both WireGuard keys.

**Revocation and failing closed:**

- Revocation is checked every 15 seconds. A gateway cuts a revoked site or person within 15 seconds of having the new
  revocation list (plus `crl_every`, 60 s, if it fetches it from a URL). Measured: 14 s for a person, within 20 s for a site.
- A person whose computer stops re-agreeing keys is removed after three missed rotations plus 30 s (6.5 minutes by
  default); a site tunnel after three rotations plus 2 minutes. An expired revocation list refuses everyone.
- `outage_grace_minutes` (default 0, at most 1440) can keep people and sites connected through an outage of the key
  service, but only while the revocation list is usable and doesn't list them.

**Keys for the firewalls you already have.** Many firewalls (Juniper SRX and MX, Fortinet FortiGate, Palo Alto) can ask a
key server for keys over ETSI GS QKD 014. `acxelin-qvpn kme` is such a key server: two sites' servers agree a shared secret
over post-quantum TLS and hand the gateways matching keys by ID. It is post-quantum key delivery through the QKD interface,
not QKD itself. QVPN can also mix in keys from a real QKD link.

**Access rules:** `[wireguard.access]` limits a person to some networks (Linux gateways enforce it with nftables).

**Classical fallback** (one peer at a time, by choice only): for a partner without QVPN, static keys with optional PPK.
Labelled **NOT QUANTUM SAFE** everywhere it shows (log, status, metrics, CBOM, console badge); not allowed with CNSA
profiles.

## First run

1. **The administrator** installs the command line (*Part 2*) and opens `acxelin-qvpn console` (port 8901). It creates the
   certificate authority (passphrase in memory only).
2. **A remote-access gateway** in one step: `acxelin-qvpn setup vpn.acme.example --route 192.168.10.0/24` creates the CA
   (or reuses it), the gateway certificate and a checked `gateway.toml`, and prints the commands to start enrolment
   (`ca serve`), the gateway and the first invitation.
3. **A person**: in the console's People tab, **Invite** downloads `alice.acxinvite`. Alice installs the desktop app, opens
   the invitation, chooses a passphrase (8 characters or more) and presses **Connect**. The tray shield turns green:
   **Protected**.
4. **Two sites**: write `site.toml` for each (examples in `config/`), run `acxelin-qvpn up --config site.toml` (or the
   systemd units), then add each site's status address in the console's Sites tab.

## Daily use: the console

- **Sites:** each site's tunnels: state, key exchange, encryption, whether the PPK is in use, quantum-safe or not, last key
  rotation, traffic, the peer's certificate. **Protected** means established with ML-KEM and the PPK. **Revoke site**
  (confirmed) revokes its certificates; **Remove** only stops showing it.
- **People:** enrolment and gateway settings; **Invite** (1 hour to 30 days; the file is never written to disk by the
  console); **pending invitations** with **Cancel**; who is connected (address, since, traffic, key age); **Revoke**;
  recent activity from the CA, enrolment and gateway logs.
- **Health:** the admin machine's checks, the CA, and whether each site and gateway answers.

## Daily use: the desktop app

- A tray shield: green **Protected**, amber **Connecting**, dark amber **Degraded**, red **Not protected**, grey
  disconnected.
- Menu: Open Acxelin QVPN, Disconnect, Start at login, Quit and disconnect. Closing the window leaves the VPN connected.
- The tray runs as the person; the part that changes the network (`acxelin-qvpn app`) runs with administrator rights
  (Windows UAC, Linux pkexec, macOS administrator prompt), and only from a copy ordinary users can't change. On a Mac, start
  it with `sudo acxelin-qvpn app` in Terminal (the tray can't, because any administrator can replace apps in
  /Applications).
- Optional full tunnel with a kill switch.

## Daily use: the command line

| Command | What it does |
|---|---|
| `doctor [--ca] [--config] [--strict]` | Checks fitted to the machine's role |
| `setup NAME …` | One-step remote-access gateway |
| `console [link]` | The administrator console (port 8901) |
| `invite NAME --enroll URL --gateway HOST:PORT` | Write an invitation |
| `join FILE` / `app` / `desktop` | Enrol and connect / the app window / the tray |
| `status [--details] [--json]` | Laptop: protected or not (exit 0 only if protected); site: tunnels |
| `up --config site.toml` | Run a site |
| `gateway --config gateway.toml` | Run the WireGuard gateway |
| `connect`, `install`, `uninstall`, `disconnect` | Low-level client, boot service, take the tunnel down |
| `access show\|rules` | Who is restricted; nftables rules to load yourself |
| `kme --config kme.toml` | The ETSI GS QKD 014 key server |
| `inventory --cbom FILE` | A CBOM of what the VPN uses (keys by type and size only) |
| `evidence create\|verify` | A signed audit bundle |
| `ca init\|issue\|revoke\|crl\|maintain\|list\|serve` | The VPN's certificate authority (`--dir pki`; `serve` is EST on 9443) |

## Running gateways in production

- **Docker:** build the image yourself (it builds strongSwan 6.1.0 with ML-KEM from pinned source) and run it with
  `--network host --cap-add NET_ADMIN -v /etc/acxelin-vpn:/etc/acxelin-vpn`.
- **systemd:** install into `/opt/acxelin-vpn`, settings in `/etc/acxelin-vpn/`, units from `deploy/systemd/`:

| Unit | Runs |
|---|---|
| `strongswan-pqc.service` | strongSwan's charon |
| `acxelin-vpn-ipsec.service` | `up --config /etc/acxelin-vpn/site.toml` (a site) |
| `acxelin-vpn-wireguard.service` | `gateway --config /etc/acxelin-vpn/gateway.toml` (remote access) |
| `acxelin-vpn-enroll.service` | `ca serve` (EST enrolment) |
| `acxelin-vpn-ca-maintain.service` + `.timer` | `ca maintain` daily; passphrase in `/etc/acxelin-vpn/ca.env` |

Each unit starts only if its settings file exists, so only the right ones run.

## Ports

| Port | Use |
|---|---|
| UDP 500, 4500 | IKE (sites) |
| UDP 51820 | WireGuard (people) |
| TCP 7443 | Site-to-site key agreement |
| TCP 7444 | Remote-access key agreement (by convention) |
| TCP 9443 | Enrolment (EST) |
| 9101, 9102 | Site and gateway status/metrics (loopback) |
| 8901 | Console (loopback) |
| 8443, 7445 | Key server (KME) API and its server-to-server agreement (example settings) |

## Limits, stated honestly

- WireGuard's own handshake is classical (X25519); the post-quantum part is the pre-shared key mixed into it.
- IKE authenticates with the PSK and PPK derived from ML-DSA mutual TLS, not with ML-DSA certificates, because strongSwan 6.1
  can't load them.
- No phones, and not the IKEv2 clients built into operating systems.
- The desktop installers aren't code-signed yet. On Windows the kill switch can lift for a moment while the tunnel is
  recreated.
- The person's app learns of a revocation at the next key renewal (within 2 minutes), so it can briefly still say
  Protected after the gateway has cut it off.
- Not tested yet: an upgrade over a running release, mixed-version gateways, the outage drill, the key server against real
  Juniper/Fortinet/Palo Alto gateways, QKD against real hardware. Tested in Linux network namespaces and on GitHub's Windows
  and macOS runners, not on customer networks.

## How it works inside

| Module (`src/acxelin_vpn/`) | Role |
|---|---|
| `__init__.py` | Site and peer settings, profiles, validation |
| `controller.py`, `charon.py` | The site controller; strongSwan over VICI |
| `agreement.py` | The TLS key agreement; its labels are pinned (a wire format) |
| `wireguard.py` | The WireGuard gateway and client |
| `join.py`, `setup.py` | Invitations; one-step gateway |
| `platforms.py` | Tunnels, kill switch, boot service and elevation checks per operating system |
| `app.py`/`app.html`, `desktop.py` | The app window; the tray, autostart and launcher |
| `console.py`/`console.html` | The console |
| `kme.py`, `qkd.py`, `access.py`, `grace.py` | Key server, QKD mixing, access rules, outage grace |
| `checks.py`, `inventory.py`, `evidence_commands.py`, `audit.py`, `ca_commands.py` | doctor, CBOM, evidence, audit log, CA commands |
| `packaging/` | Desktop installers (PyInstaller, Inno Setup, dmg, deb) |

## Troubleshooting

| You see | Do |
|---|---|
| `OpenSSL … is too old` | Install 3.5, or use the image or desktop installers |
| `cannot reach charon at unix:///var/run/charon.vici` | Start `strongswan-pqc` |
| `ML-KEM key exchanges: none` | Rebuild strongSwan as the Dockerfile does |
| A tunnel stuck in `CONNECTING` | Open the ports; the settings `name` must equal the certificate's name |
| The app shows `revoked` | Ask the administrator for a new invitation |
| Everyone refused after a week | The revocation list expired: run `ca maintain` daily |
| `would run code with administrator rights that an ordinary user can change` | Use the Setup, the .deb or an `/opt` install |

## Where to change things

| Change | Files |
|---|---|
| A command or option | `cli.py` `parser()` (CA in `ca_commands.add`, console in `console.add`); keep `test_docs` and `test_commands` in step with the docs |
| IKE proposals or profiles | `__init__.py` `PROFILES`; `charon.py`; `policies.py`; `inventory.py` |
| Site or gateway settings | `Site`/`Peer` and `validate` in `__init__.py`; `wireguard.py` `GatewayConfig`; `config/*.toml`; `setup.py` |
| Timings | `controller.py` and `wireguard.py` limits, `KEEP_MINUTES`, `grace.py` `MAX_MINUTES` |
| Key-derivation labels | `agreement.py`: don't change them (a wire format) |
| Console, app, tray | `console.py`/`.html`, `app.py`/`.html`, `desktop.py`; tests in `tests/browser/` |
| Installers, image, units | `packaging/`, `deploy/`; `test_deploy` checks them |

# Part 6: The shared foundation (acxelin-core)

`core/` holds mechanisms only: no product names, policies or commands. Every product builds on it, and it works with nothing
else installed (CI installs it alone to prove it).

| Module (`core/src/acxelin_core/`) | What it provides |
|---|---|
| `openssl.py` | The ctypes binding to OpenSSL 3.5+ (Python's `ssl` can't choose TLS 1.3 groups or report the one negotiated). Finds the library through `ACXELIN_OPENSSL`, then PATH (Windows) or the system loader; refuses anything below 3.5 with a fix for each operating system |
| `tls.py`, `server.py` | Policies, server and client contexts, public roots; a threaded TLS server with connection limits, CRL checks, certificate hot reload, and routing by SNI/ALPN on a shared port |
| `pki/` | The certificate authority (ML-DSA or SLH-DSA roots and intermediates, issue, renew, revoke, CRLs, short-lived certificates), signers (key file, AWS KMS, a signing command, PKCS#11), EST, OCSP, OIDC enrolment |
| `console.py`, `shell.py` | The console access contract (below) and the shared page shell (fonts, logo, styles, inlined so the page can forbid every external source) |
| `files.py` | Atomic writes; owner-only secrets (mode 600, and Windows ACLs set before the first byte is written); audit-log appends; "is this code somewhere only administrators can write?" |
| `http.py`, `https.py` | Guarded HTTP servers for metrics, status and CRLs (connection limits); plain-language socket errors; settings-file watching |
| `config.py` | Settings from TOML with clear errors and "did you mean" hints |
| `evidence.py` | Evidence bundles: a zip with a SHA-256 manifest, optionally ML-DSA-signed; private keys refused |
| `cli.py` | Shared command-line helpers |

**The console security contract** (CLAUDE.md rule 7, enforced by core and tested): consoles listen on loopback only
(`--container` in Docker, published on 127.0.0.1); the browser opens through a single-use launch ticket in the URL fragment,
exchanged for a session token kept in `sessionStorage` (no cookies); the Host header must be a loopback name (stops DNS
rebinding) and the Origin must match; 10 wrong attempts a minute lock an address out; the page's script is pinned by
content-security policy; no secrets in URLs or logs. To use a console on a remote server: `ssh -L 8900:127.0.0.1:8900
server`, then `… console link --port 8900`.

# Part 7: Working on the repository

## Layout

| Folder | What it holds |
|---|---|
| `core/` | acxelin-core: shared mechanisms only |
| `products/readiness/` | QReadiness: src, tests, docs, examples, bench (corpus), heldout, deploy, action.yml, installers |
| `products/tls/` | QGuard and QCertificate: src, tests, docs, config, deploy (Docker, systemd), installers |
| `products/vpn/` | QVPN: src, tests, docs, config, deploy (gateway image, systemd), packaging (desktop), installers |
| `website/` | the showcase site (home and one page per product), built by tools/build_site.py |
| `video/` | the three product films, one command each |
| `documents/` | verify-a-release (shipped as VERIFY.md), the film script, this guide |
| `review/` | the auditor pack: per-component reviews and evidence, the product-rework audit and results |
| `tools/` | site build, release gate, wheelhouse, SBOM, screenshots, browser test kit, repository checks |

## The rules every change follows (CLAUDE.md)

1. No product imports another; core works alone. Tests parse every import to enforce it.
2. Python only. Runtime cryptography is `cryptography` plus OpenSSL 3.5 through core's binding, never the `openssl`
   command.
3. Must work on Windows: pathlib, UTF-8, no POSIX-only code outside the VPN and signal handling.
4. Tests for intended behaviour first; every security behaviour has a test that shows the attack refused. Never weaken or
   delete a test to make something pass.
5. Wire and cryptographic formats don't change; breaking changes go in the product's CHANGELOG.
6. QReadiness's labelled corpus is a quality gate; `truth.json` changes only in `truth:` commits the owner approves.
7. The console security contract (*Part 6*).
8. Customer-facing pages use Acxelin's style; the licence line is "© 2026 Acxelin Quantum, all rights reserved".
9. Releases are per product by tag, core first; the owner decides when; nothing goes to PyPI.
10. The mentor's AcxelinPQC repository is a feature reference only; never copy its code.
11. A stage is done only on executed evidence; failures and skips are reported with their causes.

The owner prefers minimal code with few comments and limits stated honestly, without overclaiming.

## Developer setup

```
pip install -e ./core -e "./products/readiness[crawler,test]" -e "./products/tls[test]" -e "./products/vpn[vpn,desktop,test]" ruff==0.14.0 playwright==1.56.0
npm ci --prefix tools/browser
python -m playwright install chromium
```

Set OpenSSL 3.5 as in *Part 2* (on Linux both `ACXELIN_OPENSSL` and `LD_LIBRARY_PATH`). Then:

```
ruff check .
python -m pytest -q core/tests products/tls/tests tools/tests
python -m pytest -q products/readiness/tests website/tests
python -m pytest -q products/vpn/tests
```

Run each product's tests separately: same-named test files clash in one run. Useful switches:

| Variable | Effect |
|---|---|
| `ACXELIN_REQUIRE_OPENSSL=3.5` | Stop instead of skipping when OpenSSL 3.5 doesn't load |
| `ACXELIN_INSTALL_TEST=1` | Run the real installer and clean-wheel tests |
| `ACXELIN_INTEROP=1` | QGuard against real peers (Go, Node, curl, nginx) |
| `ACXELIN_STRONGSWAN=/opt/pqc`, `ACXELIN_VPN_DATAPLANE=1` | QVPN with real strongSwan and IPsec traffic (root, Linux) |
| `ACXELIN_REAL_WIREGUARD=1` | Bring a real WireGuard tunnel up (root or administrator) |
| `ACXELIN_REQUIRE_SOFTHSM=1`, `ACXELIN_SOFTHSM_MODULE` | PKCS#11 tests on SoftHSM2 |

## Continuous integration

| Workflow | Runs |
|---|---|
| `ci.yml` ("repository") | `tools/tests` (layout, wording, installers, release gate, supply chain, upgrade/rollback) and ruff |
| `acxelin-core.yml` | Core alone on Linux, Windows, macOS × Python 3.11 and 3.14; full suite on Debian 13 |
| `acxelin-readiness.yml` | Tests and browser journeys on three systems × two Pythons, the real installer, Docker image with a Trivy scan, real-world scans (pyjwt, paramiko, forge, go-jose) |
| `acxelin-tls.yml` | Same matrix; real nginx, Redis, mosquitto, PostgreSQL; Docker; interop with Go, Node and curl; PKCS#11 on SoftHSM2 |
| `acxelin-vpn.yml` | Same matrix; the desktop app on Windows and macOS; real WireGuard tunnels on Windows and macOS; strongSwan IPsec and WireGuard in Linux network namespaces; the three desktop installers built and installed; the gateway image |
| `website.yml`, `pages.yml` | Build and test the site; deploy it to GitHub Pages on push to main |
| `codeql.yml`, `dependency-audit.yml` | Code scanning; `pip-audit` per product weekly |
| `dependabot.yml` | Auto-merges single patch updates when every check passes |
| `soak.yml`, `performance.yml`, `signers-live.yml`, `upstream.yml` | Weekly soak (memory, files, threads flat); performance by hand; live AWS KMS by hand; weekly check for new OpenSSL and strongSwan releases |
| `release-products.yml` | Releases (below) |

## Releasing

1. Set the version in the package's `pyproject.toml` (and `__init__.__version__`) and turn its CHANGELOG's "Unreleased"
   into `## X.Y.Z`.
2. Push a tag: core first if it changed (`core-vX.Y.Z`), then `qguard-vX.Y.Z`, `qvpn-vX.Y.Z`, `qreadiness-vX.Y.Z`, one at a
   time, each after the previous release run is green.
3. `release-products.yml` then:
   - **gate**: `tools/release_check.py` checks the tag matches the version and the CHANGELOG, and that a released core is in
     the product's range;
   - **build**: runs the product's tests, builds the wheelhouse (`tools/wheelhouse.py`), checks an offline install, writes
     the SBOM (`tools/sbom.py`), `SHA256SUMS` over every file, signs build provenance (GitHub attestations), and publishes
     the GitHub release with the CHANGELOG section as notes;
   - **image**: builds, smoke-tests and pushes `ghcr.io/acxelinquantum/acxelin-<product>:<version>`;
   - **installers** (QVPN): builds and installs the Windows, macOS and Linux desktop installers and adds them;
   - **checksums**: adds the installers to `SHA256SUMS`.
4. If a run fails partway, fix it, move the tag (`git tag -f`, `git push -f origin <tag>`) and the release is rebuilt in
   place. If a hosted macOS runner is never assigned, re-run the failed job.

Tags before the rename (`tls-`, `vpn-`, `readiness-`) are history; the gate accepts only the new ones.

## The website

A static showcase at https://acxelinquantum.github.io/PQC/: a home page routing each question to its product, and one page
per product with its film (720p, captions), real console screenshots and "Talk to an Expert" (the company's contact form, or
info@acxelinquantum.com). No install or manual content: that ships in each release folder. Old addresses (`edge/`, `vpn/`,
`readiness/` and the removed set-up, manual and demo pages) redirect.

- Build: `python tools/build_site.py` (into `build/site`). Screenshots: `python tools/capture_screens.py` runs each real
  console and photographs it; the site tests fail when a screenshot is older than its console's source.
- Deploy: automatic on push to main (`pages.yml`).
- To serve it at `acxelinquantum.com/PQC/`: the main site is hosted on Gamma, which can't serve these pages, so a reverse
  proxy (such as a Cloudflare Worker) in front of the domain must forward `/PQC/*` to GitHub Pages; or use a subdomain such
  as `pqc.acxelinquantum.com` with one DNS record.

## The product films

`python video/build.py qreadiness|qguard|qvpn` records the real console doing real work (scripted cursor and typing),
composes it with title cards and diagrams (`video/stage/`), adds narration and score, renders 4K and 1080p plus a 15-second
cut and a thumbnail, and reviews every cut (text on screen long enough, nothing outside the safe area, captions in time, no
personal data). The script is `documents/video-script.md`; narration and score can come from ElevenLabs (`video/eleven.py`,
key in the ignored `.env`). `video/cut.py` makes the 3:00 versions; `python video/web.py` makes the website copies. Renders
stay out of git, in `~/AcxelinVideos/`. QVPN's film needs WSL for its Linux tunnel.

## Security reporting

Report vulnerabilities to info@acxelinquantum.com with "security" in the subject, never in a public issue. Start from each
product's `docs/threat-model.md`. `SECURITY.md` lists every place classical cryptography is used on purpose (WireGuard's
X25519 handshake, ACME account keys, SHA-1 only for key identifiers, the QReadiness corpus, the `transition` policy).

# Part 8: Open items

What still needs a decision or an action, as of this guide.

| Where | What |
|---|---|
| Releases | Core 1.4.0, QGuard 1.4.0, QVPN 1.4.0 and QReadiness 1.5.0 (the product rework) are versioned but not released. Customers on the current releases have the pre-rework consoles. Release by pushing `core-v1.4.0`, then `qguard-v1.4.0`, `qvpn-v1.4.0` and `qreadiness-v1.5.0`, one at a time |
| Distribution | **The repository `AcxelinQuantum/PQC` is public**: its source code, review documents and releases can be read and downloaded by anyone, while the licence says the software is proprietary and confidential and the website says access is by request. Decide which is intended; to restrict it, make the repository private (GitHub Pages on a private repository needs a paid plan) and distribute release files directly |
| Container images | The GHCR images can't be pulled anonymously (a package setting). Until they can, the manuals and QGuard's `bundle` tell customers to build the image themselves |
| Films | Before publishing them more widely, confirm the ElevenLabs plan used for the narration and score allows commercial use |
| QGuard console | `/api/edges/test` has no button in the page; the tests and automation use it, so it stays |
| Stale copies | `products/*/build/lib/` are old build outputs (ignored by git); never edit them |

Fixed while preparing this guide: QVPN `setup` now uses the remote-access ports (7444, status 9102); the QVPN gateway's
systemd state folder matches its settings again; QReadiness's upgrade guide covers the rename; QGuard's `doctor` names the
QCertificate tab and `bundle` says how to build the image; the pacing note, CLAUDE.md's install line, the pages workflow's
step name and the film README now match the code.

# Glossary

| Term | Meaning |
|---|---|
| **ACME** | The protocol certbot and Let's Encrypt use to get certificates (RFC 8555) |
| **CBOM** | Cryptography Bill of Materials: an inventory of cryptographic assets (CycloneDX 1.6) |
| **CNSA 2.0** | The US NSA's algorithm suite and deadlines for national security systems |
| **CRL** | Certificate revocation list: the signed list of revoked certificates |
| **CRQC** | A cryptographically relevant quantum computer, one able to break RSA and elliptic curves |
| **EST** | Enrolment over Secure Transport (RFC 7030): how machines get certificates from a CA |
| **Harvest now, decrypt later** | Recording encrypted traffic today to decrypt once a quantum computer exists |
| **Hybrid key exchange** | Combining a classical and a post-quantum key exchange (for example X25519MLKEM768), safe if either holds |
| **KME** | Key management entity: the key server firewalls ask for keys over ETSI GS QKD 014 |
| **ML-KEM** | The NIST post-quantum key-encapsulation standard (FIPS 203) |
| **ML-DSA** | The NIST post-quantum signature standard (FIPS 204); ML-DSA-44, -65 and -87 are its security levels |
| **mTLS** | Mutual TLS: both sides present certificates |
| **OCSP stapling** | The server attaches a fresh signed "not revoked" answer to its handshake |
| **PPK** | Post-quantum preshared key mixed into IKE (RFC 8784) |
| **PSK** | Pre-shared key |
| **SARIF** | The format code-scanning tools (GitHub) read |
| **Shadow mode / watch only** | QGuard serves everyone and reports who would be refused |
| **SLH-DSA** | The NIST hash-based signature standard (FIPS 205) |
| **SNI** | The host name a TLS client asks for; QGuard routes on it |
| **strongSwan** | The open-source IPsec implementation QVPN drives |
| **WireGuard** | The VPN protocol QVPN uses for remote access |
