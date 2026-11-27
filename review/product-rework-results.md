# Product rework results (Stage 3)

Branch `product-rework`. This compares the reworked products with the audit (`review/product-rework-audit.md`). Each finding is marked fixed, partly fixed or not fixed, with the test or scenario that shows it. Every Stage 1 scenario was run again on the reworked code:
- **QGuard:** `review/scenarios/stage3_qguard.py`.
- **Screens of the other consoles:** `review/scenarios/stage3_consoles.py`.
- **Linux service:** `review/scenarios/wsl-systemd.sh`.

Screenshots of the result are in `review/screenshots/stage3/`.

## Answer for the mentor, now built into the product

**QGuard is a product**: software customers install and run on their own servers, delivered as a package (one offline installer folder, or an image they build). It is not a service: nothing runs at Acxelin Quantum, and keys and traffic never leave the customer's machines. The README's first lines, the manual's Questions section and the website say exactly this.

It's no longer hard to use: the console starts at "create your certificate authority", then "protect your first service", and ends with QGuard running in front of it and a connection check that says "quantum-safe".

## QGuard real-world scenarios, again

All 13 Stage 3 checks pass. They're done through the console, as a customer would, against the same apps as Stage 1.

| Scenario | Stage 1 | Stage 3 |
|---|---|---|
| First run | create a CA, then a CLI command | CA → **Protect your first service** → **Start QGuard on this computer** (`stage3/qguard/01-04`) |
| WordPress behind QGuard | redirect to `http://…`, Chrome **ERR_CONNECTION_RESET** | `302 https://wp.audit.test/wp-admin/install.php`; opens in Chrome as "WordPress › Installation" (`05-wordpress-through-qguard.png`) |
| Headers the app receives | none; every visitor `127.0.0.1` | `X-Forwarded-For`, `X-Forwarded-Proto: https`, `X-Forwarded-Host`; a spoofed `X-Forwarded-For` from the client is removed |
| A request-smuggling shape | passed through | `400` |
| Watch mode in the console | "1 refused" (wrong), no reasons | "1 would be refused once enforcing · Why: no post-quantum key exchange offered (1)" (`06-watching-reports.png`) |
| Turn enforcement on | the edge refused to start if a fallback was set | one console action; the classical client is refused, the service stays up (post-quantum request still 200) |
| Check a public site | impossible from the console; CLI needed `--ca` | "Connected: quantum-safe key exchange, classical certificate (ECDSA)" for www.google.com (`07-check-public-site.png`); `connect` without `--ca` does the same |
| `strict` against a public site | "tls alert handshake failure" | "www.google.com offers a post-quantum key exchange (X25519MLKEM768) but a classical certificate (ECDSA); policy strict needs an ML-DSA certificate …" |
| `try` | log lines first; ends at `edge --help` | no log lines; ends at `acxelin-qguard console` |
| A website without a public certificate | nothing said | the service, Overview and `doctor` say visitors will see "Your connection is not private" and what to add |
| Linux service, following the manual (WSL Ubuntu 26.04) | `status=203/EXEC`, service failed | active; X25519MLKEM768; maintenance timer renews; unit runs `acxelin-qguard` (no old-name notice); `systemd-analyze security` 1.6 "OK" |

Unchanged on purpose, as Stage 1 measured them:
- Browsers against each policy: what Chrome and Edge show is now in the manual's "Public websites and browsers" table.
- Live settings reload.
- mTLS revocation in 3 s.
- EST, ACME with certbot, OCSP.

## Findings: before and after

### QGuard and QCertificate

| # | Finding | Result | Evidence |
|---|---|---|---|
| G1 | The console could not protect a service | **Fixed.** Services: protect by kind, edit, remove, watch/enforce, start QGuard here; the console writes the settings file the service reads (live reload) | `test_console_services.py` (22 tests), journeys `test_journeys::test_protect_a_website_start_qguard_and_check_it_end_to_end` and others; Stage 3 |
| G2 | Browsers: "not private" unexplained | **Fixed.** Said on the service, in Overview, by `doctor` and the edge at start; the form asks for the public certificate | `test_warnings.py`, journey above |
| G3 | Turning enforcement on could stop the service | **Fixed.** Turn on enforcement does every needed change and validates it with the service's own loader before saving | `test_console_services::test_watch_then_turn_on_enforcement`, Stage 3 |
| G4 | Web apps break; no forwarded headers | **Fixed.** `forwarded_headers` (decision 1): headers added, spoofed ones removed, smuggling refused, WebSockets after 101 | `test_forwarded.py` (16 tests + 12 smuggling cases), Stage 3 WordPress |
| G5 | Shadow misreported | **Fixed.** Would-refuse counts and reasons shown; browsers rejecting our certificate counted apart (`client_distrusts_certificate`) | `test_a_running_guard_reports_each_service…`, `test_tls.py` distrust test |
| G6 | Connection test could not check public sites | **Fixed.** Console and `connect`: public trust, named keys, verdict, explained failures | `test_messages.py`, `test_check_a_connection…`, Stage 3 |
| G7 | Expired certificate: silent start | **Fixed.** The edge warns at start; `doctor` fails it | `test_warnings.py` |
| G8 | Docker image cannot be pulled | **Not fixable in code** (decision 9: owner's GitHub setting). Docs now say to build it | manual section 3 |
| G9 | Jargon first | **Fixed.** Plain names (protected service, Quantum-safe only, Watching, public certificate for browsers), technical terms under "Technical details" | screenshots `stage3/qguard` |
| G10 | Export formats | **Partly.** One PEM file with full chain and key added; **PFX not possible** (`cryptography` refuses ML-DSA keys in PKCS#12; corrected in the Stage 2 spec) | `test_console_services::test_download_full_chain_and_key_as_one_pem_file` |
| G11 | mTLS failures opaque to partners | **Partly.** The manual and console explain it; what a partner's client prints is up to that client | manual Limits |
| G12 | Errors without a next step | **Fixed.** Port in use, missing files, encrypted key, missing OpenSSL (Windows advice), scheduling advice | `test_messages.py` |
| G13 | HTTP/2 | **Documented** as a limit (decision 5) | manual |
| G14 | Console polish | **Fixed.** Paths wrap, renewed certificates fold away as "Replaced", local times, no dead edges in the main view | journeys |
| G15 | Stale website screenshot | **Fixed.** Screenshots are made from the checkout and checked against it | `test_screenshots_are_current_output…` |
| G16 | `try` | **Fixed** | `test_the_tour_tells_its_story…` |
| G17 | ACME renewal manual | **Documented**; certbot `--csr` cannot renew by itself (its limit) | manual Limits |
| G18 | Linux service did not start following the manual | **Fixed.** Manual steps work; units run `acxelin-qguard` | WSL run above |
| G19 | Maintenance timer needs the CA passphrase on the server | **Documented honestly**, with the three alternatives | manual section 8 |

### QReadiness

| # | Finding | Result | Evidence |
|---|---|---|---|
| R1 | Wrong "proxy" verdict on acxelinquantum.com | **Fixed.** Live, read-only: "This computer couldn't verify the certificate (certificate has expired) … an expired root or intermediate in the path this computer built is the likely cause … Browsers and other computers may accept it." A proxy is named only on evidence | `test_verification.py`, journey |
| R2/R3 | Contradictory numbers; a score raised by harmless crypto | **Fixed** (decision 7): leads with "N things to fix now"; no 0–100 score shown (field kept for tools) | `test_headline.py`, `stage3/qreadiness/01-02` |
| R4 | Console and CLI disagree | **Fixed** | `test_headline::test_the_console_and_the_command_line_report_the_same_scan_the_same_way` |
| R5 | Projects could never be removed | **Fixed.** Remove, change folder, dead links not kept | `test_projects.py` |
| R6 | Errors off-screen in other words | **Fixed.** Next to the field, in its label | `test_field_errors.py`, journey |
| R7 | Each check replaced the last | **Fixed.** History per host | `test_endpoint_hosts.py` |
| R8 | `grade` exited 0 for an unreachable host | **Fixed.** Exit 3 (F means unreachable or no TLS); checked live | `test_commands.py` |
| R9 | bcrypt on the supplier list | **Fixed** | `test_headline::test_a_password_hash_library_is_not_on_the_supplier_list` |
| R10 | Jargon | **Fixed.** Plain by default, `--verbose` for pipeline counts; CRQC/Mosca explained once | `test_headline.py` |
| R11 | Sideways scroll at 390 px | **Fixed** (measured 1056 → 390 px) | journey |
| R12 | Polish | **Fixed.** Progress, print once, CSV words, naming, local times | journeys |
| R13 | Docker image | **Not fixable in code** (decision 9); docs say build it | manual |

### QVPN

| # | Finding | Result | Evidence |
|---|---|---|---|
| V1 | Gateway image cannot be pulled | **Not fixable in code** (decision 9); docs say build it | manual |
| V2 | Windows checkout builds a broken image | **Fixed.** `.gitattributes` keeps scripts LF; a repository test checks it | `test_line_endings.py` |
| V3 | Wrong gateway port | **Fixed** (7444, with a hint) | console journey |
| V4 | Wrong invitation file: silence | **Fixed.** The error stays and says what to do | `test_v4_…`, journey |
| V5 | Wrong advice in Health/doctor | **Fixed.** Advice fitted to the machine; every problem has a "What to do" | `test_health_on_the_administrators_machine…`, `stage3/qvpn/03-health.png` |
| V6 | Console and CLI use different CAs | **Fixed** (decision 8: CLI says where the console's CA is; defaults unchanged) | `test_v6_…` |
| V7 | Sites could not be revoked; never shown revoked | **Fixed** | `test_console::test_a_revoked_site_shows_as_revoked_and_the_console_revokes_sites` |
| V8 | Revocation timing claims disagree | **Fixed.** One statement everywhere, with the measured table. The laptop's own `status` learns at the next key agreement (a protocol limit, stated) | manual |
| V9 | App: visible window and old names | **Fixed** (header, tray-only page without a link); the Edge app window stays: it is how the app shows its window | journey |
| V10 | Pending invitations invisible; no passphrase minimum | **Fixed.** Pending list with Cancel (cancelled invitations refused); 8-character minimum | `test_console::test_an_enrollment_with_a_cancelled_invitation_is_refused`, `test_v10_…` |
| V11 | Polish | **Fixed** | see the QVPN commit |

Also found and fixed during Stage 2: a QVPN test deleted the real Windows "start at login" registry entry on every run. It now restores whatever was there.

### Website

| # | Finding | Result |
|---|---|---|
| W1 | Stale demos | **Fixed.** Four real screenshots, made from this checkout by `tools/capture_screens.py` and checked against the source by a test |
| W2 | Written for engineers | **Fixed.** A short showcase (decision 6): what it is, three outcomes, a screenshot, "Nothing is sent to Acxelin Quantum", Talk to Acxelin Quantum. No install, manual, demo or policy detail; every earlier address redirects |
| W3 | Figure captions, standards chips | **Removed** |
| W4 | The build hid why it failed | **Fixed.** It retries, then builds over a folder a sync tool holds |

## Second AI-slop review (finished consoles and website)

- **Overall:** no decorative gradients, no emoji, no invented numbers, no dead ends found.
- **Every screen leads with a decision:** "N things to fix now", "1 would be refused once enforcing · why", "Nothing needs your attention".
- **Words:** one per concept (protected service, Watching, Enforcing, findings); technical terms are folded under "Technical details".
- **Fixed in this review:** QVPN Health's "Check again" sat against the text above it; health lines in QGuard and QVPN started in lower case.
- **Kept on purpose:** QReadiness's hatched amber marks "breakable by a quantum computer" (it is the colour law in core's shell, and carries meaning).

## Tests

Final runs on the branch, each product's suite on its own as CLAUDE.md says.

| Where | Suite | Result |
|---|---|---|
| Windows 11, Python 3.14, OpenSSL 4.1 | `ruff check .` | clean |
| Windows 11 | core, QGuard, tools | 571 passed, 53 skipped, 1 failed: `test_evidence_cli.py::test_a_pilot_bundle_holds_the_build_config_certificates_handshake_and_counters`, which passes when run alone (timing under the full run, not a product fault) |
| Windows 11 | QReadiness, website | 822 passed, 3 skipped, 3 failed: the symlink tests, because Windows Developer Mode is off on this machine (creating a symlink needs it) |
| Windows 11 | QVPN | 306 passed, 21 skipped (tunnels need root or Linux) |
| WSL Ubuntu 26.04 as root, OpenSSL 3.5.5 | core, QGuard, tools | 608 passed, 16 skipped, 0 failed |
| GitHub Actions (Ubuntu, Windows, macOS; Python 3.11 and 3.14) | every workflow | 49 of 50 jobs passed; Windows 3.11 failed `test_http_guard.py::GuardTest::test_one_network_gets_its_share_and_no_more` because Windows reported the server's refusal as "aborted" (WinError 10053) rather than "reset". The test now counts both as refused; a connection left open still fails it |

## What was not tested, and why

- **Firefox:** not installed; Windows blocked Playwright's unsigned Firefox build.
- **A real public certificate as fallback:** needs a public domain pointing at this machine; a classical certificate stood in (Chrome trusting only its key).
- **A real QVPN tunnel from Windows:** needs WireGuard for Windows, a system-wide install. The Linux side ran in WSL and Docker (the QVPN agent's runs).
- **HSM, KMS and SoftHSM:** need hardware, accounts, or SoftHSM's development branch.

## Owner actions

1. Make the three GHCR images public, or keep the docs' "build it yourself" (decision 9).
2. Turn on Windows Developer Mode to run the three QReadiness symlink tests locally, or leave them to CI.
3. If you want the QVPN app to start at login again, turn on **Start at login** in its tray menu (an old test had removed the entry).
4. `test_evidence_cli` expects an OpenSSL 3.x version string; this machine loads 4.1.0, so it fails here and passes against 3.6.4. It assumes more than the project's own "3.5 or newer" rule.
