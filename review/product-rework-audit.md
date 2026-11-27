# Product rework audit (Stage 1)

Branch `product-rework`, from `main` at `f3b6cbe`. Audited on 27 November 2026 on one Windows 11 machine. No product code was changed for this audit.

This is what a new customer meets today, measured on the released products: QGuard 1.3.0, QVPN 1.3.0 and QReadiness 1.4.0, each installed from its release wheelhouse with `install.ps1`, and the QVPN desktop app from its `Setup.exe`. Screenshots are in [`review/screenshots/stage1/`](screenshots/stage1/). The scripts that produced every result are in [`review/scenarios/`](scenarios/), so Stage 3 can run the same checks again.

## Contents

1. [The answer for the mentor](#1-the-answer-for-the-mentor)
2. [What each product is, in one sentence](#2-what-each-product-is-in-one-sentence)
3. [How the audit was run](#3-how-the-audit-was-run)
4. [QGuard and QCertificate: what happened in real use](#4-qguard-and-qcertificate-what-happened-in-real-use)
5. [Problems, ranked by how much they hurt a customer](#5-problems-ranked-by-how-much-they-hurt-a-customer)
6. [Tasks that still need the command line](#6-tasks-that-still-need-the-command-line)
7. [Proposed plan](#7-proposed-plan)
8. [Should QCertificate be a separate product?](#8-should-qcertificate-be-a-separate-product)
9. [AI-slop review](#9-ai-slop-review)
10. [What was not tested, and why](#10-what-was-not-tested-and-why)
11. [Decisions I need from you before Stage 2](#11-decisions-i-need-from-you-before-stage-2)

---

## 1. The answer for the mentor

**Is QGuard a product, a service or a package?** It is a **product**: software the customer downloads, installs on their own servers and runs themselves, the way they run nginx. It is **not a service**. Acxelin runs nothing for the customer, holds no keys and sees no traffic. It **ships as a package**: one offline installer folder (or a container image) that gives one command, `acxelin-qguard`. That command runs three things:

- **the guard (today called the "edge")**, which sits in front of a website, API or database and makes every connection to it quantum-safe without changing the service behind it;
- **QCertificate**, the customer's own certificate authority, which issues and revokes the quantum-safe certificates the guard and its clients need;
- **the console**, a local web page where the customer does all of this.

**Why is it so hard to understand and use today?** The audit found four reasons, all with evidence below:

1. **The console manages certificates, not the thing the customer bought.** A customer buys QGuard to protect a service, yet the console can't add, start, change or stop a protected service. It can only issue certificates, and then it hands over a command line ([finding G1](#g1)).
2. **The words are engineering words.** "Edge", "terminate/originate", "metrics address", "transition", "ML-DSA-65" and "CRL" are the first things a customer reads. The website opens with "an edge proxy with QCertificate" ([G9](#g9)).
3. **The most common real case, a public website, is the least guided.** Browsers can't verify ML-DSA certificates, so a public site needs the `transition` policy plus an ordinary public certificate. Nothing in the console or the doctor says so, and a browser shows "Your connection is not private" with no hint why ([G2](#g2), [G3](#g3)).
4. **Ordinary web apps break behind it without explanation.** WordPress redirects to `http://…:443` and fails, every visitor appears to come from `127.0.0.1`, and no document mentions it ([G4](#g4)).

## 2. What each product is, in one sentence

Written for a customer:

- **QGuard:** Software you install in front of your websites, APIs and databases so that every connection to them is protected against future quantum computers, with your own certificate authority (QCertificate) built in, and without changing the services themselves.
- **QReadiness:** Software that finds the cryptography in your code, configuration, certificates and live servers, tells you which of it a quantum computer (or an attacker today) can break, and gives your security and engineering teams a ranked list of what to change first, with evidence an auditor accepts.
- **QVPN:** Software that links your offices to each other and your people to your network, with every tunnel's keys agreed over quantum-safe connections using your own certificates, so traffic recorded today stays private, and a revoked office or person is cut off within seconds.

## 3. How the audit was run

### Setup and baseline

| Step | Result |
|---|---|
| venv (Python 3.14.6), editable installs from CLAUDE.md, Playwright and Chromium, `npm ci` in `tools/browser` | done |
| OpenSSL | `C:\Program Files\OpenSSL-Win64\bin` holds **both** 3.6.4 (`libssl-3`) and 4.1.0 (`libssl-4`); core's binding picks the highest, so everything here ran on **OpenSSL 4.1.0**. The OpenSSL installer also copied both into `C:\Windows\System32`. |
| Release installs | `install.ps1` from each release wheelhouse: fingerprints match; QGuard 41 s, QVPN 37 s, QReadiness 58 s, all offline |
| QVPN desktop app | `Acxelin-QVPN-1.3.0-Setup.exe`: SHA-256 matches `SHA256SUMS`; GitHub build attestation verified (built by `release-products.yml` from tag `qvpn-v1.3.0`) |

Baseline test run (each command on its own, as CLAUDE.md says; Windows, OpenSSL 4.1.0):

| Command | Passed | Failed | Skipped | Errors |
|---|---|---|---|---|
| `ruff check .` | all | 0 | – | – |
| `pytest core/tests products/tls/tests tools/tests` | 506 | 2 | 53 | 0 |
| `pytest products/readiness/tests website/tests` | 761 | 3 | 3 | 13 |
| `pytest products/vpn/tests` | 287 | 0 | 21 | 0 |

The failures and errors all come from this machine, not from the code:

- `test_evidence_cli` asserts the OpenSSL version starts with `"OpenSSL 3."`; this machine loads 4.1.0. It passes against 3.6.4 (checked earlier today). The test is stricter than the project's own "3.5 or newer" rule.
- `test_http_guard::test_one_network_gets_its_share_and_no_more` timed out while my scenario traffic was loading the machine; on its own it passes (2 passed).
- Three QReadiness tests need symlinks (`WinError 1314`); Windows Developer Mode is off here. Core's equivalent test skips in that case; these three fail instead.
- The 13 website errors are `FileExistsError: …\build\site\assets`. `tools/build_site.py` starts with `shutil.rmtree(OUT, ignore_errors=True)`; while a browser or OneDrive held a file in `build\site`, the delete failed silently and the copy then failed. It's a robustness bug in the build script, and it hides the real cause. Rerun with a clean `build\site` and nothing holding it open: **13 passed**.
- Skips are the expected ones on Windows: Linux root, network namespaces, strongSwan, real WireGuard, systemd, POSIX file modes, SoftHSM, live KMS/HSM, nginx/redis/PostgreSQL/MQTT/certbot on PATH, Go interop.

### What "real use" meant

For QGuard and QCertificate, everything was done the way a customer would: website page, README, `acxelin-qguard try`, then the console (17 screenshots), then the scenarios in section 4 against real software running on this machine:

- **Apps:** a static site and an upload/download backend (Python), WordPress with MariaDB, Grafana, and an HTTP/WebSocket echo server (all in Docker).
- **Clients:** curl with OpenSSL 3.5.9 (an independent post-quantum client that can verify ML-DSA), Windows' own `curl.exe` (Schannel, classical only), Chrome 158 and Edge 158 (installed browsers, driven by Playwright), certbot, and QGuard's own `connect`.
- **Names:** `*.audit.test` mapped to 127.0.0.1 inside each client (Chrome's host-resolver rule, curl's `--connect-to`), not the Windows hosts file, which needs administrator rights. The server-name routing the edge sees is the same.

QReadiness and QVPN were walked through the same way by a second agent; its findings are in section 5.

## 4. QGuard and QCertificate: what happened in real use

| Scenario | What happened | Verdict |
|---|---|---|
| `acxelin-qguard try` | 3 s; clear story: a post-quantum client gets in, a classical one is refused. Raw log lines print before the story (red `NativeCommandError` in PowerShell); it ends with `Next: acxelin-qguard edge --help` and never mentions the console. | works, rough |
| Console first run | Create the CA (name and passphrase), 0.4 s. Placeholder "Example Root CA" looks like a filled-in value. | works |
| Issue, download, renew, revoke in the console | All work. Download is a zip of `cert.pem`, `chain.pem`, `ca.crt` (+ `key.pem` with "With key"). No PFX or other formats. Long paths overflow the result box (`08-after-revoke.png`). A renewed certificate stays listed as a separate row with only a Revoke button and no word on whether it's still trusted. | works, rough |
| Static site behind the edge (`strict`), curl with OpenSSL 3.5 | `TLSv1.3 / X25519MLKEM768 / id-ml-dsa-65`, verified against QCertificate | works |
| Four services on one port, chosen by host name | `static`, `echo`, `grafana`, `wordpress` on :8443 by SNI; unknown names go to the default route. Only possible by writing a TOML file by hand. | works (CLI/file only) |
| HTTP/2 | Never negotiated. Without `alpn`, the edge offers no ALPN; with `alpn = ["h2"]` (the manual's example) the list only chooses the route, and curl still ends on HTTP/1.1. | not supported, not documented |
| WebSockets | Echo server: frames both ways. Grafana Live: two `wss://…/api/live/ws` connections stay open. | works |
| 200 MB download and upload | Byte-identical (SHA-256 checked both ways). On this machine: 56–89 MB/s through the edge vs 263–281 MB/s plain HTTP (the full test suite was running at the same time). | works |
| Long-lived request (90 s) | 200 after 90 s | works |
| Connection idle before the first request | Idle 25 s then a request: fine. Idle 40 s: closed by the edge (`first_data_timeout = 30`). Browsers open sockets ahead of time; mostly they retry. | note |
| X-Forwarded-* and client address | The app receives **no `X-Forwarded-For`, `-Proto` or `-Host`**, and every visitor's address is `127.0.0.1`. Only the PROXY protocol is available, which ordinary apps don't speak. | **gap** |
| Redirects and absolute URLs | An app that builds absolute URLs makes `http://static.audit.test:8443/landing` (wrong scheme). | **breaks apps** |
| WordPress | First visit redirects to `http://wp.audit.test:8443/wp-admin/install.php`; Chrome shows **ERR_CONNECTION_RESET** (`apps/wordpress-first-visit.png`). | **broken** |
| Grafana | Login, Explore, live WebSockets all work (`apps/grafana-after-login.png`). | works |
| Chrome / Edge vs `strict` | "Your connection is not private", ERR_CERT_AUTHORITY_INVALID (`browsers/chrome-strict.png`). With certificate checks skipped: page loads over X25519MLKEM768. | expected, unexplained |
| Chrome / Edge vs `transition` + fallback | With the fallback certificate trusted (Chrome trusting only that key): **page loads, secure context, key exchange X25519MLKEM768**. Exactly what Google, Cloudflare, GitHub and acxelinquantum.com do today. | **works: the right public-website setup** |
| Chrome / Edge vs `transition` without fallback | Same "not private" warning: `transition` alone doesn't help browsers. | trap |
| Chrome / Edge vs `cnsa2` | "This site can't provide a secure connection … uses an unsupported protocol" (ERR_SSL_VERSION_OR_CIPHER_MISMATCH). Browsers don't offer ML-KEM-1024. | expected, unexplained |
| Windows' own TLS (Schannel) | Works only on the fallback port; elsewhere `SEC_E_ILLEGAL_MESSAGE`. | expected, unexplained |
| Firefox | Not tested: Firefox isn't installed, and Windows refused to start Playwright's unsigned Firefox build (`spawn UNKNOWN`). | not tested |
| mTLS partner API | No client certificate: refused with "certificate required". Valid certificate: 200. **Revoked: refused 3 s after `ca revoke`** (local CRL file). The partner then sees only `Empty reply from server`. | works, unclear to the partner |
| Client certificate in a browser | No PFX export, and browsers can't present ML-DSA client certificates today. | not possible, not explained |
| Shadow mode | A classical client is served; `/status` records "would refuse: no post-quantum key exchange offered; cannot verify ML-DSA certificates", and the log names what the client offered. Clear on the edge. | works |
| Shadow in the console | The console shows **"0 of 1 handshakes quantum-safe · 1 refused"** while shadow mode refused nobody, and shows none of the "would refuse" detail (`qguard/17-edges-shadow-mode.png`). | **misleading** |
| Switching shadow off | With the fallback certificate still set, removing `--shadow` makes the edge **refuse to start**: "a fallback certificate is for terminate routes with policy = "transition" (or shadow = true)". Turning enforcement on can take the service down. | **trap** |
| Live settings change | The edge applies a changed settings file in 2 s; an in-flight 15 s request on an unchanged route finishes; a broken change rolls back to the old settings. | works (basis for the plan) |
| EST enrollment | Token, enroll, renew all work; reusing a token is refused with a clear message. Hints say "renew it daily from cron" (nothing on Windows). | works |
| ACME with certbot | Works with certbot's `--csr` mode, a CSR from `acxelin-qguard ca csr`, and the ACME service on a classical certificate. certbot itself says such certificates **won't renew automatically**. | works, manual |
| OCSP staple, CRL publishing | Both work from the CLI. Not in the console. | works (CLI) |
| Restart and unlock | After a console restart: unlock screen; wrong passphrase gives "cannot open the CA key: wrong passphrase". | works |
| Port already in use | "error: Only one usage of each socket address … is normally permitted" (raw Windows text; doesn't say what to do) | unclear |
| Missing certificate file | "cannot load certificate nope/chain.pem: **No such process**" | misleading |
| Encrypted key, no passphrase given | "wrong passphrase; pkcs12 cipherfinal error (if it is encrypted, give its passphrase)" | jargon |
| Expired certificate | The edge **starts silently** with a certificate that expired yesterday; no warning. | **silent** |
| No OpenSSL 3.5 | Clean stop, but on Windows it says "tried nothing on PATH" and suggests Debian/Ubuntu; it doesn't mention `choco install openssl`, or that ACXELIN_OPENSSL pointed at an empty folder. | unclear on Windows |
| Public sites, read-only | `connect` needs `--ca`; with a public root bundle and `transition`: google.com, cloudflare.com, github.com and acxelinquantum.com all use X25519MLKEM768 with an ECDSA certificate. CLI shows the key as `1.2.840.10045.2.1`. Under `strict`: "tls alert handshake failure" with no explanation. The console's test can't check public sites at all (trusts only QCertificate). | works, unclear |
| Docker image on the website | `docker run --rm ghcr.io/acxelinquantum/acxelin-qguard:1.3.0`: an anonymous pull fails with "unauthorized". (I couldn't list the packages: the GitHub token lacks `read:packages`.) | **broken for a customer** |

## 5. Problems, ranked by how much they hurt a customer

Severity: **blocker**, the customer can't finish the job without help; **major**, they finish but with a wrong result, a risk, or by leaving the console; **minor**, friction or polish.

**The ten that hurt most, across all products:**

1. **QGuard** can't protect a service from its console ([G1](#g1)).
2. **Browsers** show "Your connection is not private" with no path to the setup that works ([G2](#g2)).
3. **QGuard:** turning enforcement on can take the service down ([G3](#g3)).
4. **QGuard:** web apps like WordPress break behind it, and apps see every visitor as 127.0.0.1 ([G4](#g4)).
5. **All three container images** can't be pulled, and a Windows checkout builds a broken QVPN image (G8, R13, V1, V2).
6. **QGuard on Linux:** following the manual, the systemd service doesn't start (G18).
7. **QReadiness** tells a customer a healthy site may be behind a TLS-inspecting proxy ([R1](#r1)).
8. **QReadiness's** headline numbers contradict each other, and its score rewards harmless cryptography (R2, R3).
9. **QGuard's** console misreports shadow mode, so you can't see who enforcement would cut off ([G5](#g5)).
10. **QVPN's** console suggests the wrong gateway port, and the app silently ignores a wrong invitation (V3, V4).

### QGuard and QCertificate

<a id="g1"></a>**G1. Blocker: the console can't protect a service.** The product's purpose is "put quantum-safe TLS in front of a service", but the console has no way to add, start, change, pause or remove one. After issuing a certificate it prints a one-off `acxelin-qguard edge --listen 0.0.0.0:8443 --target 127.0.0.1:8080 --cert … --key …` command (`qguard/04-issued-server.png`). That command has no `--metrics`, so the edge it starts can never be added to the console's own Edges tab. Several services on one port, the public-website setup, mTLS for a partner and shadow mode all need a hand-written TOML file. Evidence: section 4; `console.html` has no route or service screens.

<a id="g2"></a>**G2. Blocker: public websites show "Your connection is not private" with no explanation.** Chrome 158 and Edge 158 show ERR_CERT_AUTHORITY_INVALID for every `strict` route and for `transition` without a fallback certificate (`browsers/chrome-strict.png`, `browsers/msedge-transition-no-fallback.png`). The working setup, `transition` plus an ordinary public certificate as `fallback_cert`, was verified (`browsers/chrome-fallback-trusted-8444.png`: secure context over X25519MLKEM768). But it only appears in the "How it works" guide; the console, `doctor` and the README never steer a customer there. `doctor` even calls `transition` "fine for browsers", which is only true with a fallback certificate.

<a id="g3"></a>**G3. Blocker: turning enforcement on can stop the service.** After shadow mode with a fallback certificate, dropping `--shadow` makes the edge refuse to start ("a fallback certificate is for terminate routes with policy = "transition" (or shadow = true)"). The safe switch takes two coordinated edits, and the manual doesn't say so.

<a id="g4"></a>**G4. Major: ordinary web apps break behind the edge.** The edge forwards raw TCP. Apps receive no `X-Forwarded-For/Proto/Host`, and see every visitor as `127.0.0.1` (curl check 6). Apps that build absolute URLs pick the wrong scheme (check 5); WordPress fails at its first redirect with ERR_CONNECTION_RESET (`apps/wordpress-first-visit.png`). Grafana happens to work. No document mentions forwarded headers, client addresses or which apps need settings changed.

<a id="g5"></a>**G5. Major: the console misreports shadow mode.** It counts shadow handshakes as "refused" and hides the "would refuse" reasons the edge records (`qguard/17-edges-shadow-mode.png`). The customer can't see who would be cut off, which is the whole point of shadow mode. Relatedly, a browser rejecting *our* certificate is counted as "handshake failed" on the edge, which the console shows as QGuard refusing the browser.

<a id="g6"></a>**G6. Major: the connection test can't check what customers ask about.** It trusts only QCertificate, so testing any public site (or our own fallback setup) fails with "handshake failed: tls alert handshake failure" plus "If that looks right, it trusts or uses a different certificate authority" (`qguard/11-test-public-site.png`). Google actually uses X25519MLKEM768; the test can't say so. The CLI's `connect` needs `--ca` and prints the key type as `1.2.840.10045.2.1`.

<a id="g7"></a>**G7. Major: the edge starts with an expired certificate and says nothing.** It starts and logs only "listening". Every client then fails, and nothing points at the certificate.

<a id="g8"></a>**G8. Major: the Docker image the website tells customers to run can't be pulled** ("unauthorized" for an anonymous pull).

<a id="g9"></a>**G9. Major: jargon first.**
- **Website:** opens with "an edge proxy with QCertificate … post-quantum key exchange".
- **Console:** tabs read "Edges"; the edge form asks for an "Edge metrics address" and a "Client policy"; the CA header is a monospace line "ML-DSA-87 2 valid 1 revoked".
- **Certificates:** forms ask for "Kind: Server/Client" without saying when to use which.
- **Naming:** the product calls the running part "edge" in some places and "proxy" or "guard" in others.

**G10. Major: no export formats.** A download is a zip of PEM files. There's no PFX/PKCS#12, no single "full chain + key" file, and nothing that says which file a given server wants. (Honest limit: Windows and IIS can't use ML-DSA certificates for TLS yet, so a PFX helps mainly to move keys between machines and tools.)

**G11. Major: mTLS failures are opaque to the partner.** A revoked client sees `Empty reply from server`, and a browser can't present ML-DSA client certificates at all. Neither is explained anywhere a customer looks.

**G12. Minor: error messages that don't say what to do.**
- Port in use: raw Windows text.
- Missing file: "No such process".
- Encrypted key without passphrase: "pkcs12 cipherfinal error".
- No OpenSSL on Windows: points at Debian/Ubuntu, not `choco install openssl`.
- Hints say "from cron" on Windows.

**G13. Minor: HTTP/2 is never served**, and the manual's `alpn = ["h2"]` example suggests it is.

**G14. Minor: console polish.**
- Long paths overflow the result box (`08-after-revoke.png`), and table actions are clipped at 1280 px (also on the website's screenshot).
- Renewed rows are confusing.
- Times show only in UTC.
- A dead edge stays listed in red forever and delays the whole list by 3 s.
- The "Example Root CA" placeholder looks like a filled-in value.

**G15. Minor: the website's console screenshot is stale.** It shows the old name "Acxelin TLS" and a clipped "Re…" button (`website/assets/tls-console.png`), against CLAUDE.md's "demo content is real product output".

**G16. Minor: `try` ends at `edge --help`**, not at the console, and prints raw log lines before its story.

**G18. Major: following the manual, the Linux service doesn't start.** Tested in WSL Ubuntu 26.04 (systemd, OpenSSL 3.5.5) with `review/scenarios/wsl-systemd.sh`.
- The unit runs `/opt/acxelin-tls/bin/acxelin-tls`, but the manual's only instruction is "`deploy/systemd` has `acxelin-tls-edge.service`". `install.sh` installs per user; with `ACXELIN_PREFIX=/opt/acxelin-tls` alone, the command still lands in `~/.local/bin`. Result: `status=203/EXEC … Unable to locate executable`.
- It works once you know to also set `ACXELIN_BIN=/opt/acxelin-tls/bin`, create the `acxelin` user, and put the CA in `/var/lib/acxelin-tls/pki`. Then: service active, X25519MLKEM768 with ML-DSA-65 for both QGuard's client and the system `openssl s_client`, maintenance timer renews and re-signs. `systemd-analyze security` scores the unit 1.6 ("OK").
- The unit still calls the old command name, so every start logs "acxelin-tls is now acxelin-qguard".

**G19. Major: the maintenance timer needs the CA passphrase in a file on the server.** `acxelin-tls-maintain.service` reads `ACXELIN_TLS_CA_PASSPHRASE` from `/etc/acxelin-tls/ca.env`. That's undocumented, and it contradicts the manual's own advice, "Keep the passphrase in your password manager, not on the server". The honest options: renewal from the machine that holds the CA, short-lived certificates via EST from the edge's side, or an HSM/KMS signer. The manual and console should say which.

**G17. Minor: ACME renewal is manual.** certbot's `--csr` mode, the only one that works with ML-DSA, never renews automatically. The console doesn't show ACME or EST at all.

### QReadiness

Walked through as a customer:
- **Scanned** paramiko (a shallow clone), pyjwt from GitHub, and this repository.
- **Graded** five public endpoints read-only.
- **Used** finding detail, owner/due/status, accepted risk, filters, CSV/CBOM export, the Board summary, deadlines by country and sector, and cancelling a scan.
- **Screenshots:** `qreadiness/01–43`. Console scans took 8 s (paramiko), 9 s (pyjwt) and 58 s (this repo).

What works well: scanning, the ranked findings with file and line, owner tracking, cancelling ("Scan cancelled; the previous completed assessment is preserved"), network errors that say what to check ("no answer (timed out; is a firewall dropping it?)").

<a id="r1"></a>**R1. Major: a wrong, alarming verdict on a healthy public site.**
- For `acxelinquantum.com:443` the console says "Certificate not trusted by this computer: a private CA, or a TLS-inspecting proxy answered instead, and then these grades describe the proxy" (`qreadiness/28-endpoints-graded.png`, `41-cli-grade-html.png`).
- The site serves a valid Let's Encrypt chain; nothing in it has expired (checked). Windows and browsers accept it. Python's check on this machine fails with "certificate has expired", from the path *this machine's* trust store built.
- The product turns "this computer couldn't verify it" into "a proxy may be lying to you". Any customer whose machine has an odd trust store gets a frightening, wrong report.

**R2. Major: the headline numbers contradict each other.**
- For paramiko it shows, side by side: "12 of 38 findings need action now (2 critical, 10 high)", "15 breakable by a quantum computer / 3 broken today, 4 weakened", "22 findings without an owner", "0 of 22 findings that need work are done", "38 cryptographic assets found, and 8 only in tests (not listed)" (`09-scan-result-paramiko.png`).
- The parts don't add up to the wholes. "Findings" and "assets" name the same thing.
- This repo shows "35 of 100 findings need action now" next to "65 of 100 readiness score" (`34-scan-result-pqc-repo.png`). That's a dashboard with no clear decision.

**R3. Major: the score rises when you add harmless cryptography.** It's the average of per-finding priorities ("ok 100 … critical 0"), so a repository with two criticals and many SHA-256 uses scores 64, and adding more SHA-256 raises it.

**R4. Major: the console and the CLI disagree about the same scan.** CLI `scan` lists 46 assets, including test-only RSA-1024; the console lists 38. MD5 is "critical" with 13 places, 9 of them in tests, despite "8 only in tests (not listed)". Critical is defined as "exposed: deployed, configured or reachable", yet the same row says "Static evidence; runtime use is not established" (`10-finding-detail-md5.png`).

**R5. Major: things you add can never be removed or changed.**
- A GitHub repository that doesn't exist still becomes a permanent project ("— 0 0 not scanned never"). It keeps the Board summary "Provisional: 2 of 3 projects scanned" (`21`, `24`, `25`).
- The repositories folder can't be changed after the first choice.

**R6. Major: errors appear out of view, in words that don't match the form.** Saving an accepted risk without a reason, deep in the table, shows "An exception needs a rationale and a current or future expiry date" in a banner at the page top. The form says "Why it is accepted" and "Accepted until" (`13-accepted-risk-no-reason.png`).

**R7. Major: each endpoint check replaces the last.** Checking three unreachable hosts wiped the earlier grades ("Nothing to score yet. Coverage 0%"), so "what changed" compares against whatever was checked last.

**R8. Minor: the CLI misleads scripts.** `grade no-such-host.invalid:443` prints an F and exits 0; a missing input file prints `[Errno 2] No such file or directory: 'missing-file.txt'`.

**R9. Minor: wrong advice in the supplier list.** It says "bcrypt … not yet [post-quantum]" and asks the customer to chase suppliers; bcrypt is a password hash with nothing to migrate. The Board summary repeats it.

**R10. Minor: jargon first.**
- **CLI:** its first line is `detectors 689 raw -> verify 480 verified, 55 held, 72 rejected ... -> rank 161 promoted, 99 trails -> 46 assets`.
- **Report:** says "raw detections, noisy by design", "CRQC" and "Mosca".
- **Help:** `scan --help` says "send the pipeline over a repository".

**R11. Minor: layout.** At 390 px, Projects and the result page scroll sideways (page 555 px wide; `30`, `31-mobile-*.png`). Long folder paths overflow at 1280.

**R12. Minor: polish.**
- "Scan every project" shows no progress for about 15 s.
- One click of "Print or save as PDF" calls `window.print` twice.
- The CSV says `in_progress` where the UI says "In progress".
- "See the change" shows a generic snippet, not the repository's code.
- Times are UTC only.
- "Readiness" vs "QReadiness".
- PowerShell 5.1 shows the CLI's bars as boxes.
- The website's report image says "Acxelin Readiness 1.0.0" (old name, old version).

**R13. Major: the published Docker image can't be pulled** (`unauthorized`, like QGuard's).

### QVPN

Walked through as an administrator and as a person:
- **Admin console:** created the CA, saved invitation addresses, invited, enrolled, revoked.
- **Windows:** `join --no-apply` and the app (`--no-apply`).
- **Linux, built from the repo in containers:** a WireGuard gateway, two IPsec sites ESTABLISHED with "CURVE_25519 + ML_KEM_768, PPK yes" and ESP traffic flowing, and a Linux laptop that joined with a real WireGuard tunnel ("Protected … X25519MLKEM768, gateway certificate ML-DSA-65").
- **Revocation:** revoking a person cut them off at the gateway in 14 s; revoking a site closed its tunnel within 20 s.
- **Screenshots:** `qvpn/01–31`.

**V1. Blocker: the published gateway image can't be pulled.** `docker pull ghcr.io/acxelinquantum/acxelin-qvpn:1.3.0`: "unauthorized".

**V2. Blocker: building the gateway image from a Windows checkout gives a broken image.** Every container exits with `exec /usr/local/bin/acxelin-vpn-entrypoint: no such file or directory`. The cause is that `entrypoint.sh` is LF in git but CRLF in a Windows working tree (`git ls-files --eol`: `i/lf w/crlf`, checked), with `core.autocrlf=true` and no `.gitattributes`.

**V3. Major: the console suggests the wrong port for invitations.** The gateway field's placeholder is `vpn.example.com:7443`; the person gateway listens on 7444, and 7443 is the site port (checked in `console.html`; `05-people-first-time.png`).

**V4. Major: the app silently ignores a wrong invitation file.** The server answers 400; the window shows nothing and stays "Not set up" (`12-app-wrong-file.png`).

**V5. Major: Health gives advice that's wrong for the machine it runs on.**
- The admin console permanently warns "The desktop app (tray icon) is not installed … pip install "acxelin-qvpn[desktop]"", although Setup.exe installed it.
- It also tells the admin to `pip install "acxelin-qvpn[vpn]"` and install WireGuard.
- A "Problem" row has an empty "What to do" (`06-health.png`, `27-health-with-sites.png`).
- `doctor --config` prints "0 problem(s), 1 warning(s)" after four WARN lines.

**V6. Major: the console and the CLI use different certificate authorities by default.** The console's is `~/.acxelin-vpn/console/ca`; every CLI `ca`/`invite` command defaults to `./pki`. Site and gateway certificates can only be issued from the CLI, so the admin must find the console's folder and pass `--dir`.

**V7. Major: sites can't be revoked or certified from the console, and a revoked site never shows as revoked.** After `ca revoke`, Sites says "No tunnel / Peer certificate not seen yet" (`26`). Removing a site has no confirmation.

**V8. Major: revocation timing claims disagree.**
- The README and website say "within 15 seconds"; `ca revoke` says "within a minute".
- Observed: 14 s for a person at the gateway, 20 s for a site.
- The person's app said "Your access was revoked" about 68 s later.
- A Linux laptop's `status` still said "Protected." about 20 s after the gateway had removed it.

**V9. Major: the desktop app opens a visible Edge window and uses old names.**
- It opens `msedge --app=…console-launch.html` in its own Edge profile.
- Its install folder is "Acxelin VPN", its exe `acxelin-vpn.exe`, and its header says only "VPN".
- Opened without a launch link, it still shows the whole set-up screen, with a small red note (`25-desktop-app-page-without-link.png`).

**V10. Major: pending invitations are invisible, and the device passphrase has no minimum.** After inviting someone, People still says "Nobody yet" until they enrol; pending invitations can't be seen or cancelled (`08`). The app accepted a 5-character passphrase and used up the one-time invitation.

**V11. Minor: polish.**
- A `join` failure says "connection refused" without naming the address.
- `status` says "No VPN client is running" while `app --no-apply` runs.
- A revoked laptop retries forever, and says "full-tunnel traffic stays blocked" on a split tunnel.
- The tour says "STEP 1 OF 6" then "Five short steps".
- "Confirm revoke" silently reverts after about 6 s.
- The systemd units call the old `/opt/acxelin-vpn/bin/acxelin-vpn`.
- `ca issue --help` describes `server` as the WireGuard gateway, while the guide uses it for the enrollment service.

### Website (all three products)

**W1. Major: stale demos.** QGuard's console screenshot says "Acxelin TLS"; QReadiness's report image says "Acxelin Readiness 1.0.0". This breaks CLAUDE.md's "demo content is real product output".

**W2. Major: written for engineers, not buyers.**
- Terminal-style demos full of hex ids and proposal strings ("agreement 52dd8162a9d7", "aes256gcm16-prfsha384-x25519-ke1_mlkem768"), CRQC and Mosca, policy tables.
- Install and Docker commands, including images that can't be pulled (G8, R13, V1).
- With your direction (a short showcase), most of this goes; see section 7.

**W3. Minor: the "Fig. n" captions and the standards chip cloud** read as a paper, not a product page.

**W4. Minor: `tools/build_site.py` hides why a rebuild failed** (`rmtree(..., ignore_errors=True)` then `FileExistsError`). It caused the 13 baseline errors.

## 6. Tasks that still need the command line

Your direction: the console covers the important everyday tasks, not every command. Each task is marked by how often a customer does it. **Console** means it should be there after the rework; **CLI** means it stays command-line only, on purpose.

### QGuard and QCertificate

| Task | How often | Today | After the rework |
|---|---|---|---|
| See whether every protected service is up and quantum-safe, and who was refused | daily | console, partly (only edges added by metrics address; shadow misreported) | **Console**: Overview |
| Put a new service behind QGuard | weekly | hand-written TOML or a one-off command | **Console**: "Protect a service" |
| Change a service: names, port, policy, watch mode, turn enforcement on | weekly | TOML by hand | **Console** |
| Issue a server or client certificate | weekly | console | Console (kept) |
| See what expires soon; renew | weekly | console | Console, plus automatic renewal status |
| Revoke a client or partner | as needed | console | Console (kept) |
| Download a certificate in the format a server or tool needs | weekly | console, PEM zip only | **Console**: named formats incl. PFX |
| Check a connection: our own service, or any public site | weekly | console, own CA only | **Console**: both, with a plain verdict |
| Give a public website its ordinary public certificate (fallback) | occasional | TOML by hand | **Console**, inside "Protect a service" |
| Let a device enrol (EST one-time token) | occasional | CLI | **Console**: create a token, show the command for the device |
| ACME: see whether it's on, create an account key (EAB) | occasional | CLI | **Console**: status and EAB keys; running the ACME service stays a service |
| Revocation list: when it was signed, where it's published | occasional | console shows expiry; publishing is CLI | **Console** shows both; publishing stays a service |
| Evidence bundle for an audit or pilot | occasional | CLI | **Console** button (one click, same output) |
| Download the CA certificate on its own | occasional | only inside a certificate's zip | **Console** |
| Install, first `doctor` | once | CLI | CLI (console shows health) |
| Run the guard as a system service (systemd; Windows) | once | systemd unit only; **nothing for Windows** | CLI, plus a Windows way to do it (decision 3) |
| Intermediate CA, KMS/HSM signing, OIDC enrollment setup | rare | CLI | CLI |
| `bundle` (nginx, PostgreSQL, MQTT compose files), `serve`, `status`, `--log-json`, workers | rare or automation | CLI | CLI |
| Sign a CSR from another tool, `ca csr` for certbot | rare | CLI | CLI (console says where to find it) |
| OCSP staple refresh | automation | CLI | CLI from a scheduled task; console shows its age |

### QReadiness

| Task | How often | Today | After the rework |
|---|---|---|---|
| Rescan; see what changed | daily | console and CLI | Console (kept) |
| Read ranked findings and their fixes | daily | console and CLI report | Console (kept) |
| Owner, due date, status, accepted risk | daily | console | Console; errors next to the field |
| Grade endpoints | weekly | console and CLI | Console, keeping each host's history |
| Export CSV, PDF, CBOM; Board summary | occasional | console | Console (kept) |
| Add a repository (folder, GitHub, organisation) | occasional | console | Console (kept) |
| **Remove a project; change the repositories folder** | occasional | **neither** | **Console** |
| Compliance report | occasional | CLI `report` | CLI (fine) |
| Policy gate in CI, baseline, GitHub Action | automation | CLI | CLI |
| `watch`, pcap, AWS, container images, tuning, `doctor` | rare or setup | CLI | CLI |

### QVPN

| Task | How often | Today | After the rework |
|---|---|---|---|
| Invite a person; revoke a person | weekly | console | Console (kept) |
| Who is connected, traffic, key age; site tunnels | daily | console | Console; show "revoked" |
| Health | daily | console | Console; advice fitted to the admin machine |
| **See or cancel pending invitations** | weekly | **neither** | **Console** |
| **Revoke a site** | occasional | CLI | **Console** |
| Person: connect, disconnect, check protection | daily | app | App (kept) |
| Issue site and gateway certificates, `setup`, `up`, configs | setup | CLI | CLI; the console points at the same CA folder |
| `ca maintain` | automated (timer) | CLI | CLI |
| Access lists, profiles, inventory, evidence, kme | rare | CLI | CLI |

## 7. Proposed plan

### Principles for all three consoles

- **One question per screen.** The home screen answers "is everything all right, and what needs me?". Every other screen is one job.
- **Plain words first, technical term on demand.** For example, "Quantum-safe only" with `strict` in a details line; "Watch only, refuse nobody" with `shadow`.
- **Every error says what happened and what to do next**, in the console and in the CLI.
- **First run ends with something working**, not with an empty table.
- **Kept unchanged:** core's console shell and security contract (rule 7), the vanilla stack (no framework), every command and option, settings and data formats, folders and service names.

### QGuard console

**Naming.** One word per concept, used everywhere (console, CLI help text, README, manual, website):

| Today | Proposed for customers | Technical term kept |
|---|---|---|
| edge, route, proxy | **protected service** (one entry); **QGuard service** (the running program) | `edge`, `[[edge]]` in the settings file and CLI |
| Edges tab, metrics address | Services; the address is filled in from the settings | `--metrics` |
| strict / transition / cnsa2 | **Quantum-safe only** / **Quantum-safe, browsers welcome** (needs a public certificate) / **CNSA 2.0** (US national security systems) | the policy names, shown under each choice |
| shadow | **Watch only**: serve everyone, report who would be refused | `shadow` |
| fallback certificate | **public certificate for browsers** | `fallback_cert` |
| Kind: Server / Client | **For a service** / **For a person, device or partner** | server / client |
| CRL | **revocation list** | CRL |

**Navigation** (four places):

1. **Overview**
   - First run: a two-step setup. Create QCertificate (name and passphrase), then "Protect your first service", which ends with the service running and a passing connection check.
   - Afterwards, a list of protected services. Each row shows: running, watching or stopped; quantum-safe share; refused and would-refuse counts with reasons.
   - Below that, **Needs attention**: certificates expiring or expired, revocation list due, a service not running, a public certificate expiring, a watched service with no would-refuse clients for 7 days ("ready to turn on").
2. **Services**
   - **Protect a service**, a short form that starts with *what kind of service*:
     - **Public website for browsers:** Quantum-safe, browsers welcome, plus a public certificate (path or upload), with one line on why.
     - **Internal app or API:** Quantum-safe only.
     - **Partner API:** Quantum-safe only, partners need a client certificate.
     - **Database or other service:** Quantum-safe only.
   - Then: the name people use, the port, where the service runs, and "start by watching". The server certificate is issued automatically from QCertificate.
   - **Saving** writes the same settings file the QGuard service already reads. The running service applies it live (verified: 2 s, in-flight connections kept, a bad change rolls back).
   - **Service page:** status; who connected and with what; who would be refused and why; **Turn on enforcement** (one button that makes every needed change, checks the result, and refuses to save a setting the service would reject); **Check connection**; edit; pause; remove.
3. **QCertificate**, its own place with its own name:
   - **Certificates:** two lists, *services* and *people, devices and partners*. Issue, renew, revoke. Download with named formats: "For QGuard, nginx or Apache (full chain + key, PEM)", "PFX for Windows tools", "Certificate only", "CA certificate".
   - **Enrollment:** EST one-time tokens (create, see used or unused), ACME status and account keys (EAB), each with the exact command for the other machine.
   - **Revocation:** when the list was signed, when it's due, where it's published, OCSP staple age.
   - **Authority:** name, algorithm, fingerprint, expiry, lock and unlock, download the CA certificate, backup guidance.
4. **Check a connection** (also reachable from each service): any `host:port`, trusting QCertificate or public authorities. It gives a plain verdict ("Key exchange: quantum-safe (X25519MLKEM768). Certificate: classical (ECDSA), as on every public site today.") with the raw details folded away.

**Health** moves into Overview ("Needs attention") and a "System check" in a small Settings page, which also says where the settings file and data live.

**Remove or fold away:**
- the "Edge metrics address" field;
- "Client policy" in the test;
- the monospace "ML-DSA-87 2 valid 1 revoked" line;
- the top-level "Run maintenance" and "Refresh revocation list" buttons (renewal and revocation-list refresh show as status, with the action next to it);
- renewed certificates as separate active rows (they fold under the current one as history).

**Product fixes behind the console** (needed for the console to be honest; each has a test that shows the failure first):
- **Doctor and startup:** warn on an expired or soon-expiring certificate, and on `transition` without a public certificate.
- **Shadow mode:** make shadow counts distinct from refusals in `/status`, and show both. The console's "turn on enforcement" handles the fallback certificate.
- **`connect` and the console check:** a public-trust option, and key types by name.
- **Exports:** PFX.
- **Error messages:** rewrite G12's messages; Windows-specific OpenSSL advice.
- **`try`:** end at the console.
- **Forwarded headers:** for web apps, if you approve (decision 1).

### QReadiness console

Navigation stays close to today (Overview, Projects, Endpoints, What it tracks), with these changes:

- **One set of numbers, one decision.**
  - The result page leads with one line: "N things to fix now", then critical and high counts.
  - "Assets" and "findings" become one word, *findings*. Test-only findings are counted and shown under their own heading, never mixed in.
  - The 0–100 score is replaced, or recomputed so that adding harmless cryptography can't raise it. A **decision for you** (decision 7).
- **The console and the CLI report the same scan the same way** (same filtering of test-only code, same counts), with a test that compares them.
- **Endpoint history per host:** a check adds a dated result to that host; "what changed" compares a host with its own last result.
- **A verdict that tells "this computer couldn't verify the certificate" apart from "something is intercepting"**, naming the verification error instead of guessing a proxy.
- **Remove a project, change the repositories folder**, with confirmation.
- **Errors next to the field**, using the field's own label.
- **390 px without sideways scrolling.**
- **Plain words:** no "detectors raw → verify → rank" line by default, no CRQC or Mosca without an explanation, `grade` exits non-zero when a host can't be reached.

### QVPN console and desktop app

- **People:** pending invitations listed ("invited 2 days ago, not enrolled yet") with **Cancel**; a correct gateway placeholder (`:7444`) with a one-line hint; a passphrase minimum in the app.
- **Sites:** a "revoked" state, **Revoke site** with confirmation, and a confirmed **Remove**.
- **Health:** advice that fits the machine. On the admin machine, no WireGuard or desktop-app warnings. Every "Problem" has a "What to do". `doctor`'s summary counts match its lines.
- **One CA folder:** the console and the CLI point at the same CA by default, or the CLI prints where the console's CA is when `./pki` doesn't exist. A **decision for you** (decision 8: whether changing a CLI default is acceptable under "the existing commands must keep working").
- **App:** an error for a wrong file; the header says "Acxelin QVPN"; without a launch link, a short "Open Acxelin QVPN from its tray icon" page instead of a set-up screen that can't work. The Edge app window stays; it's how the app shows its window.
- **Revocation timing:** measure each path in Stage 3 and state one honest number per path in the README, the console and the CLI.
- **Packaging:** a `.gitattributes` that keeps shell scripts LF, so a Windows checkout builds a working image. The unit files call the new command name; unit *names* stay unchanged.

### Website: a short product showcase

Your direction: the website exists to sell, so it says as little as possible about how the products work and nothing about installing them.

**What stays:**
- **Home:** one line on the problem, then one row per product: its name, the question it answers for the buyer ("Where does our cryptography break?", "How do we protect traffic that must stay secret for years?", "How do we connect sites and people safely?"), and a link.
- **One page per product:**
  - a one-sentence answer to "what is it, who is it for, why do they need it" (section 2);
  - three short outcomes in customer words;
  - one or two **real** console screenshots, captured from the product when the site is built, so CLAUDE.md's "demo content is real product output" still holds;
  - "It runs on your own machines; nothing is sent to Acxelin Quantum" (this answers "is it a service?" up front);
  - **Talk to Acxelin Quantum**.

**What goes:**
- the Set up, Manual, How it works, Security and "What it tracks" pages;
- the PDF guides, the sample report and CBOM;
- install commands and Docker commands;
- policy tables, protocol details and terminal-style demos;
- the standards chip cloud and the "Fig. n" captions;
- the "What it does not claim" lists. With so few claims left, there's nothing for them to qualify. The limits stay in each product's README and manual, which ship in the release folder the customer receives.

**Addresses people may have linked to** (the removed pages and the old `edge/`, `vpn/`, `readiness/` addresses) redirect to the product's page, so no link breaks.

**Where install and usage docs live after this:** the README and manual inside each release folder (unchanged files, updated content), and the "How it works" guides in `documents/`, handed to customers directly.

**Tests:** the website tests are rewritten to the new spec, not weakened. Tests for removed pages go away with the pages. New tests check the home → product → contact journey and that screenshots are current product output. The checks that still apply stay as they are: accessibility (axe) at both widths and schemes, no sideways scroll, every link resolves, the skip link, no browser errors, each page naming only its product, old addresses redirecting.

## 8. Should QCertificate be a separate product?

**My recommendation: keep it inside QGuard, as you decided, and give it its own named place in the console and its own page section on the website.**

Arguments for keeping it in QGuard:
- In every scenario I ran, certificates were a means to an end: a service behind the guard, or a partner allowed through it.
- A separate product would mean a fourth install, a fourth console and a fourth release line for something nearly every QGuard customer needs on day one.
- QVPN already carries its own small CA for the VPN. A standalone QCertificate would raise "which CA do I use?" without solving anything.

When to revisit: if customers start asking for QCertificate *without* QGuard, for example for code signing, document signing, or an organisation-wide PKI for many products. Then it could become its own product with QGuard depending on it. Nothing in this audit shows that demand yet.

## 9. AI-slop review

### QGuard console and QGuard's website page

The console is calm and mostly free of generic AI patterns: no gradients, no emoji, no decorative icons, no marketing copy. Its problems are a different kind of "unfinished":

| Pattern | Where | Evidence |
|---|---|---|
| Controls that look like they do something they don't | "Edges": an "Add edge" form that only watches an edge started elsewhere; a "Test connection" that can't test public sites | G1, G6 |
| Numbers that mislead | "1 refused" in shadow mode; browser certificate rejections counted as refusals | G5 |
| Dead end | after issuing a certificate, a CLI command whose edge the console can't see | G1 |
| Inconsistent words for one thing | edge / route / proxy / guard; Kind / Type; "With key" vs "Download with key" | G9 |
| Developer-facing data shown as decoration | monospace facts line "ML-DSA-87 2 valid 1 revoked"; raw paths in the result box | G9, G14 |
| Stale demo | website console screenshot says "Acxelin TLS" | G15 |
| Badge cloud | home page "Built on published standards" chips (FIPS 203, RFC 7030 …): true, but means nothing to a buyer | website home |
| Figure numbering ("Fig. 1/2/3") on marketing pages | home and product pages | academic register, not a product page |

### QReadiness and QVPN consoles

No fluff words, no emoji and no invented numbers in either. The patterns found:

| Pattern | Where |
|---|---|
| Decoration that carries no meaning | QReadiness: hatched amber "barber-pole" fill on the "breakable" card and the high bar segment |
| Card grids for everything | QReadiness: four stat cards plus four navigation cards that only scroll the page down |
| A dashboard with no decision | QReadiness: the result header's five overlapping counts plus a score (R2); the empty Overview is a dashboard of zeros with an active "Scan every project" |
| Inconsistent words for one thing | findings/assets, exception/accepted risk, Readiness/QReadiness; QVPN/VPN/Acxelin VPN/acxelin-vpn |
| Controls that look present but do nothing visible | QVPN app: wrong file selected, nothing happens (V4); "Confirm revoke" silently reverting |
| Settings syntax in the UI | QVPN: 'metrics = "HOST:PORT" in its [site]', "Keys agreed, no handshake", "Post-quantum PPK" |
| Placeholder-looking text | QVPN app: "This computer" in monospace under the shield |
| Dead ends | QReadiness: a project that can't be removed; QVPN: an invitation that can't be seen until used |

## 10. What was not tested, and why

| Not tested | Why |
|---|---|
| Firefox | Not installed; Windows refused to start Playwright's unsigned Firefox build (`spawn UNKNOWN`). I didn't work around that security control. |
| The Windows hosts file | Editing it needs administrator rights. Names were mapped inside each client instead; the edge sees the same server names. |
| A real public certificate (Let's Encrypt) as fallback | Needs a public domain pointing at this machine. A classical test root stood in, trusted by Chrome for that key only. |
| Nextcloud | WordPress, Grafana and the echo server covered the same behaviour (redirects, forwarded headers, WebSockets, uploads). |
| win-acme | certbot (the other client you named) was used. |
| Client certificate inside a browser | No PFX export exists, and browsers can't present ML-DSA client certificates today. |
| The guard as a Windows service | The product ships no Windows service definition. |
| Hardware or cloud CA keys (KMS, HSM) | Needs accounts and hardware; the README already says this has not been run. |
| OpenSSL 3.5 vs 4.1 differences | Everything on Windows ran on 4.1.0 (the binding picks it); the evidence test proves at least one place assumes 3.x. The WSL runs used OpenSSL 3.5.5. |
| A real QVPN tunnel on Windows | Needs WireGuard for Windows (a system-wide install, not done). The Windows side ran with `--no-apply`. Docker wouldn't publish UDP 51820 on Windows loopback, so the Windows-to-gateway data path is untested. |
| QVPN tray menu, Windows VPN service, kill switch, sleep/wake | Not testable headless. |
| QVPN systemd units | Only `systemd-analyze verify` in WSL; not installed or run. Left to CI. |
| QReadiness: GitHub Action, private-token flow, organisation import, CBOM/CMDB upload, `watch`, pcap, AWS | Not exercised in this pass. |

## 11. Decisions I need from you before Stage 2

1. **Forwarded headers for web apps (G4).** To make WordPress-style apps work, a route could optionally read the HTTP/1.1 request and add `X-Forwarded-For/Proto/Host`, removing any the client sent so they can't be spoofed. That's new edge behaviour on the plain-text side; TLS and wire formats don't change. It also means QGuard parses HTTP for routes that ask for it. Options: (a) add it as an opt-in route setting, with security tests; (b) don't add it, and document per-app settings (WordPress `WP_HOME` and `$_SERVER['HTTPS']`, Grafana `root_url`) plus the PROXY protocol for apps that support it. **I recommend (a)** for "public website" and "internal app" services, off for databases.
2. **Where the console writes service settings.** The console would edit the same TOML file the QGuard service reads. Default: `<console home>/edge.toml`; on Linux servers the console is pointed at `/etc/acxelin-tls/edge.toml`, which the admin must be able to write. No format change. OK?
3. **Running the guard as a Windows service.** Today there is nothing for Windows. Options: a documented scheduled task or `sc.exe` recipe (no code), or a new `acxelin-qguard service install` command. **I recommend the documented recipe for now**; a new command is more to maintain and test.
4. **PFX export.** cryptography can write PKCS#12 with ML-DSA keys, but Windows TLS (Schannel/IIS) can't use ML-DSA certificates yet. Add it, clearly labelled "for moving keys between tools; Windows TLS can't use it yet", or leave it out?
5. **HTTP/2.** Not supported today. Document it as a limit (my recommendation), or add real ALPN negotiation? That would only help backends that speak cleartext HTTP/2, which few do.
6. **Website as a showcase.** Removing the Set up, Manual, How it works, Security and "What it tracks" pages, the PDFs and the samples means removing the website tests written for them (the install-command journey, the "What it tracks" page, the terminal demos) and writing new ones for the showcase. That's a requirement change, not a weakened test, but CLAUDE.md rule 4 is strict, so I want your explicit OK. Also: CLAUDE.md describes `website/` as "one section per product … demo content is real product output"; I'd update that line to describe the showcase.
7. **QReadiness's 0–100 score (R3).** Today it's the average of per-finding priorities, so harmless findings raise it. Options: (a) drop the number and lead with "N things to fix now"; (b) keep a score computed only from what needs work, so adding SHA-256 can't move it. Changing the score changes reports customers may already compare over time. **I recommend (a).**
8. **QVPN's CA folder default (V6).** Making `acxelin-qvpn ca …` default to the console's CA instead of `./pki` changes an existing command's default. The alternative that changes nothing: when `./pki` doesn't exist, the CLI says where the console's CA is and how to point at it. **I recommend the alternative.**
9. **Container images (G8, R13, V1).** All three images on GHCR refuse an anonymous pull. Making them public is a GitHub setting only you can change (I won't, and can't without `read:packages`/`write:packages`). Until then, the docs shouldn't tell customers to pull them. The showcase website won't show Docker commands either way.
