# Product rework, Stage 2: the approved spec

Approved by the owner on 27 November 2026, together with `review/product-rework-audit.md`. Finding IDs (G1, R2, V3 …) refer to that audit.

## Rules for every change

- **CLAUDE.md applies.** No product imports another; Python only; must work on Windows; no `openssl` command; wire and cryptographic formats, data folders, settings-file formats and service names don't change; existing commands and options keep working.
- **Tests first.** For each change, write the test that shows today's problem (it fails), then make it pass. Every security behaviour keeps a test that shows the attack refused. Never weaken or delete a test to pass. When a UI label changes, update the journey to the new words but keep what it checks.
- **Console contract unchanged** (rule 7): loopback only, single-use launch ticket in the fragment, session token in sessionStorage, no cookies, Host and Origin checks, lockout, no secrets in URLs or logs. The page keeps one inline script allowed by its hash.
- **Stack unchanged:** core's console shell (`acxelin_core.console`, `shell.css`, `shell.js`), plain DOM, no framework.
- **Plain words first, the technical term on demand.** Every error says what happened and what to do next.
- **The console covers everyday tasks.** Rare, setup and automation tasks stay CLI-only (audit section 6).
- **Docs follow the code:** each product's README, `docs/manual.md` and CHANGELOG (under an "Unreleased" heading; no version bumps, tags or releases).

## Decisions (owner-approved recommendations)

1. **Forwarded headers:** an opt-in route setting for HTTP/1.1 services. The edge adds `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host` and removes any the client sent. On for "public website" and "internal app" services the console creates; off for databases and other TCP services. Security tests show spoofed headers removed.
2. **Service settings:** the console reads and writes the same TOML file the QGuard service reads. Default `<console home>/edge.toml`; can be pointed at another file (for example `/etc/acxelin-tls/edge.toml`). No format change. The running edge already applies changes live.
3. **Windows service:** a documented recipe (scheduled task at start-up), no new command.
4. **PFX export:** added, labelled "for moving keys between tools; Windows TLS can't use ML-DSA certificates yet".
5. **HTTP/2:** documented as a limit; the manual's `alpn = ["h2"]` example explains that `alpn` chooses a route and HTTP/2 isn't served.
6. **Website:** a short showcase (audit section 7). Tests for removed pages go; new tests for the showcase; CLAUDE.md's `website/` line updated.
7. **QReadiness score:** the 0–100 number is dropped. The result leads with "N things to fix now". Reports, CBOM and CSV formats keep their fields where other tools read them (state it in the CHANGELOG if a field changes meaning).
8. **QVPN CA default:** CLI defaults unchanged. When `./pki` doesn't exist and the console's CA does, the CLI says where the console's CA is and how to use it (`--dir`).
9. **Container images:** an owner action (make them public). Docs stop telling customers to pull them until then; build-it-yourself instructions stay.

## Work by product

- **QGuard and QCertificate:** G1–G19.
  - **Console:** Overview, Services ("Protect a service"), QCertificate (certificates, enrollment, revocation, authority), Check a connection. Naming per audit section 7.
  - **Edge and CLI:** forwarded headers; warnings for expired certificates and `transition` without a public certificate; distinct shadow counts; `connect` public trust; PFX; error messages; `try` ending at the console; Windows service recipe; systemd unit and install docs that work as written; the maintenance timer's passphrase honestly documented.
- **QReadiness:** R1–R13 (audit section 7, "QReadiness console").
- **QVPN:** V1–V11 (audit section 7, "QVPN console and desktop app"), plus a `.gitattributes` keeping shell scripts LF.
- **Website:** W1–W4 and the showcase.
