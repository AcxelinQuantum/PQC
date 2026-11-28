# Product films: script

Three films, one per product, each **4:00**: **Acxelin QReadiness**, **Acxelin QGuard** (with QCertificate) and **Acxelin QVPN**. Each stands on its own. They share one structure, one opening line, one look and one piece of music, so together they read as a family.

## The shared frame

| Time | Part | What it does |
|---|---|---|
| 0:00–0:15 | Hook | The same opening line in all three films, then the risk: recorded today, opened later |
| 0:15–0:45 | Problem | The buyer's situation, in their own words, with a light touch |
| 0:45–1:05 | Meet the product | What it is and who it is for (the audit's one-sentence answers) |
| 1:05–3:20 | The product at work | Real console footage: four or five short scenes, each ending on a visible result, with music-only breathers between them |
| 3:20–3:45 | Trust | Runs on your machines, nothing sent to Acxelin Quantum, NIST standards, one honest limit |
| 3:45–4:00 | Close | Product name, a short signature line, the Acxelin Quantum logo, acxelinquantum.com |

## Voice and tone

- **Sound:** modern, warm and confident, like a good product keynote rather than an advert. Short sentences, a little wit, room to breathe.
- **Pace:** about 70–75 words a minute across each film (about 280–300 words in 4 minutes), so nothing feels crowded. The busiest single shot stays under 140 words a minute. The product scenes leave gaps where only the music and the screen play. These are marked "Breather" in the tables.
- **Words:** plain words only. Technical terms (ML-KEM, FIPS 203, CycloneDX) appear on screen, never in the voice.
- **Humour:** gentle, aimed at situations everyone recognises (the system nobody dares touch, the board's question). Never aimed at a real company, a real breach or the viewer.
- **Speaker:** one voice for all three films.
- **Signature lines:** each film closes with its own short line:
  - QReadiness: "Know where you stand."
  - QGuard: "Protect what you can't rewrite."
  - QVPN: "Private today. Private later."

## Visual language

From DESIGN.md and the website's assets.

- **Title frames:** dark, ink `#111c26`, with paper `#f4f6f7` type in Host Grotesk.
- **Accent:** amber `#ffbf00`, at most once per frame: the rule under a title, the cursor's ring, the outline round the detail that matters.
- **Data:** Roboto Mono for data and for the time markers.
- **Kinetic type:** short lines set in a word or two at a time, slowly (each word eases in over 400 ms). Nothing bounces, spins or wipes.
- **Product footage:** always the real console or app.
  - It sits in a window on the dark branded background, with a soft shadow and a slight, slow parallax.
  - It is never shown as full-screen browser chrome.
  - The cursor moves smoothly and typing happens at human speed.
- **Camera:** slow push-ins (1.0× to 1.4× over 1.5 s) onto the result of each scene, and back out before the next.
- **Cuts:** clean cuts, or 300 ms cross-dissolves between scenes.
- **Section cards:** a small amber index number and a two-word title ("01 · Scan"), shown for 1.5 s before each scene. They give the viewer a map without any narration.
- **Never:** wipes, spins, lens flares, stock hackers, glowing padlocks or circuit boards.

## Music

- **The track:** one licensed track for all three films, supplied by the owner and edited per film. It should be warm minimal electronic, around 100 BPM, with a soft pulse, light piano or plucks and no vocals.
- **Cue markers:**
  - **M1:** a single low note under the hook.
  - **M2:** the pulse enters with the problem.
  - **M3:** the full bed arrives with the product name.
  - **B:** a breather. The music comes forward and the voice rests.
  - **M4:** the music thins out under the trust section.
  - **M5:** it resolves on the logo.
- **Scratch build:** until the owner supplies the track, the build leaves silence and a marker at each cue.

## Demo data

Everything shown is a fictional company, **Acme**, on reserved `.example` names (RFC 2606):
- QGuard protects `shop.acme.example`, the internal `intranet.acme.example` and the partner API `partners.acme.example`.
- QReadiness scans the product's own example project, `payments-api`, and grades Acme's test hosts.
- QVPN joins the sites `Headquarters` and `Branch office` and invites `alice`.

No real customer, person, token or passphrase appears; passphrases show only as dots.

**Lower thirds** name the place on screen ("Console · Services") and stay up for at least 2 seconds. **On-screen lines** stay up for at least 1.5 seconds each.

---

## Film 1: Acxelin QReadiness

| Time | On screen | Motion and transition | Voice-over | On-screen text | Music |
|---|---|---|---|---|---|
| 0:00–0:07 | Dark frame. Kinetic type: "Encryption has a shelf life." | Fade up from black; words ease in. | Here's something nobody prints on the label. Encryption has a shelf life. | Encryption has a shelf life. | M1 |
| 0:07–0:15 | A second line joins: "Recorded today. Opened later." An amber rule draws under "later". | Hold; the rule draws left to right over 800 ms. | Traffic recorded today can be opened later, once a quantum computer is big enough. | Recorded today. Opened later. | M1 holds |
| 0:15–0:25 | Diagram on paper: a boardroom-style card reading "When do we switch?" | Slow drift; the card eases in. | So the board asks a fair question. When do we switch to quantum-safe cryptography? | "When do we switch?" | M2: pulse enters |
| 0:25–0:35 | The card flips to a quieter one: "We don't know where our cryptography is." | A 300 ms cross-dissolve. | And the honest answer begins with an awkward one. We don't actually know where it is. | "We don't know where our cryptography is." | M2 |
| 0:35–0:45 | Four tiles ease in: a line of code, a config line, a certificate, a server address. The last tile shows a dusty "last login: years ago" tag. | Tiles ease in 150 ms apart; a slow push onto the last one. | It's in code. In configuration. In certificates. In a server nobody has touched in years. | `code` · `config` · `certificates` · `servers` | M2 |
| 0:45–1:05 | Product title card, then the console's home screen in its window. | Clean cut to dark; the title sets in; the window rises in. | Meet Acxelin QReadiness. It finds the cryptography you depend on, tells you what a quantum computer, or an attacker today, could break, and ranks what to change first. For security and engineering teams alike. | Acxelin QReadiness · Find it. Grade it. Fix what matters first. | M3: full bed |
| 1:05–1:20 | Section card "01 · Scan". Projects: `payments-api` is chosen and **Scan** pressed; the progress line runs. | Card for 1.5 s, then a cut to the window; the cursor moves at human speed. | Start with a repository. Pick it, press scan, and it gets to work, right here on your own computer. | Lower third: Console · Projects | M3 |
| 1:20–1:40 | The result leads with "things to fix now"; one finding opens to show its file, line, why it matters and the fix. | Push in on the "things to fix now" count and hold for 2 s; pull back and open the finding. | Moments later, one number leads: the things to fix now. Open any of them, and you see where it is, why it matters, and exactly what to change. | The number, exactly as the screen shows it | M3 |
| 1:40–1:50 | **Breather.** The four parts of the result scroll by slowly: "What we found", "Why it matters", "What could happen if nothing changes", "What to do". | A slow vertical pan. | *(music only)* | The four headings, from the screen | B |
| 1:50–2:05 | Section card "02 · Grade". Endpoints: three Acme test hosts are typed in and **Check** pressed. | Cut; typing at human speed. | Next, the servers you actually run. Type their addresses, and each one gets a grade, A to F. | Lower third: Console · Endpoints | M3 |
| 2:05–2:20 | The graded table: an A, a B and a C, each with its plain reason underneath. | Push in on the C and its reason. | An A means quantum-safe key exchange only. A C means today's traffic could be read later. Good to know first. | A · B · C, from the screen | M3 |
| 2:20–2:40 | Section card "03 · Track". A finding gets an owner and a due date, and its status moves forward. | Cut; the form fills at human speed. | Now make it someone's job. Give each fix an owner and a date, and follow it through to done. | Lower third: Console · Projects | M3 |
| 2:40–2:50 | Overview: "Services most at risk". | A 300 ms cross-dissolve; a slow push in. | And the overview keeps the riskiest services right at the top. | Lower third: Console · Overview | M3 |
| 2:50–3:10 | Section card "04 · Share". **Download CBOM** on Endpoints; a terminal shows the first lines of the file; then the board summary. | Cut to the terminal window on the same background; cross-dissolve to the summary. | And when the auditors call, you're ready: a standard bill of materials for your cryptography, and a one-page summary for the board. | `CycloneDX 1.6 CBOM` · Board summary | M3 resolves |
| 3:10–3:20 | **Breather.** Coverage: "Every algorithm it knows" scrolls by. | A slow pan. | Curious what it looks for? It shows you that too. | Lower third: Console · Coverage | B |
| 3:20–3:35 | Dark frame; three lines appear one by one. | Type sets in, at least 1.5 s per line. | It runs on your own machines. Nothing is sent to Acxelin Quantum. And its advice follows NIST's post-quantum standards. | Runs on your machines · Nothing sent to Acxelin Quantum · NIST FIPS 203 (ML-KEM) · FIPS 204 (ML-DSA) | M4 |
| 3:35–3:45 | One more line on the same frame. | Hold. | One honest note: cryptography a program assembles while it runs can slip past. We'd rather tell you now. | It finds what it can read. | M4 |
| 3:45–4:00 | Close: "Acxelin QReadiness", the signature line, the Acxelin Quantum logo, acxelinquantum.com. | The logo fades up; the amber rule draws once; hold, then fade to black. | Acxelin QReadiness. Know where you stand. | Acxelin QReadiness · Know where you stand. · acxelinquantum.com | M5 |

---

## Film 2: Acxelin QGuard, with QCertificate

| Time | On screen | Motion and transition | Voice-over | On-screen text | Music |
|---|---|---|---|---|---|
| 0:00–0:07 | Dark frame. Kinetic type: "Encryption has a shelf life." | As in Film 1. | Here's something nobody prints on the label. Encryption has a shelf life. | Encryption has a shelf life. | M1 |
| 0:07–0:15 | "Recorded today. Opened later." with the amber rule. | The rule draws over 800 ms. | Connections recorded today can be opened later, once a quantum computer is big enough. | Recorded today. Opened later. | M1 holds |
| 0:15–0:25 | Diagram: a tidy migration plan on a slide, with three boxes: "website", "API", "database". | Slow drift; the boxes ease in. | You know your services need quantum-safe encryption. The plan looks great on a slide. | | M2: pulse enters |
| 0:25–0:35 | The boxes pick up small honest tags: "built 2014", "vendor's code", "can't restart". | Tags ease in 150 ms apart. | Then reality. The website, the APIs, the database: they can't be rewritten in time. | "Our services can't be rewritten in time." | M2 |
| 0:35–0:45 | One box dims, with a tag reading "please don't touch". | A slow push in. | And that one system nobody dares to touch? Nobody's touching it. | | M2 |
| 0:45–1:05 | Title card, then a diagram: QGuard slides in front of the three unchanged boxes, and the outside lines turn into a single quantum-safe line. | Cut; QGuard eases into place; the line colour shifts slowly. | Meet Acxelin QGuard. A product you install and run yourself, not a service. It sits in front of the services you already have, and makes the connections to them quantum-safe. The services stay exactly as they are. | Acxelin QGuard · A product you install and run yourself. Not a service. | M3: full bed |
| 1:05–1:20 | Section card "01 · Protect". Services: **Protect a service**, "Public website", `shop.acme.example`, port 443, where it runs now (`127.0.0.1:8080`), and its public certificate. | Card for 1.5 s; the window rises; typing at human speed. | Open the console and protect a service. Say what it is, its address, and where it runs today. | Lower third: Console · Services | M3 |
| 1:20–1:35 | **Protect service**, then **Start QGuard on this computer**: "QGuard is running". | Push in on the running state. | QGuard issues its certificate, writes its own settings, and starts in front of the app. | "QGuard is running" | M3 |
| 1:35–1:45 | **Breather.** Overview: "Protected services" fills in as the first connections arrive. | A slow push in. | *(music only)* | Lower third: Console · Overview | B |
| 1:45–2:05 | Section card "02 · Watch". The internal app in watch mode; under it, Services shows how many connections would be refused once enforcing, and why. | Push in on the reason line. | Not sure who's still on old software? Start in watch mode. Everyone is served as usual, and QGuard tells you how many would be refused, and why. | Watch mode | M3 |
| 2:05–2:20 | **Turn on enforcement**, then confirm; the badge reads "Enforcing". A terminal alongside: an old client is refused while a quantum-safe one still gets the page. | Split frame, the console on the left and the terminal on the right. | When that list is empty, turn on enforcement. Old clients are turned away. Quantum-safe ones carry on. | Enforcing · refused · 200 OK | M3 |
| 2:20–2:30 | Section card "03 · QCertificate", then the QCertificate tab: "The authority". | Card for 1.5 s, then a cut. | Every door needs a list of who's allowed in. That's QCertificate: your own certificate authority, built in. | QCertificate · your own certificate authority | M3 |
| 2:30–2:45 | "Issue a certificate" for "A person, device or partner": `acme-partner`. A terminal: with it the partner reaches `partners.acme.example`; without it the request is refused. | Typing at human speed; then a cut to the terminal. | Issue a certificate for a partner, and only that partner gets into your API. | `certificate required` (from the terminal) | M3 |
| 2:45–3:00 | **Revoke**, then confirm; the "Revocation list" updates; the partner's next call is refused. A small time marker shows the real elapsed time. | Push in on the refusal; the time marker sits in the corner in Roboto Mono. | Partnership over? Revoke it, and QGuard turns them away within a minute. | Revoked · refused · real elapsed time | M3 |
| 3:00–3:20 | Section card "04 · Check". Check a connection: an address typed, **Check** pressed, and the verdict in plain words. | Cut; push in on the verdict. | Want to know how a connection really behaves? Type an address, and get the answer in plain words. | Lower third: Console · Check a connection | M3 resolves |
| 3:20–3:35 | Dark frame; lines appear one by one. | Type sets in. | It runs on your servers, and nothing is sent to Acxelin Quantum. Key exchange and certificates both follow NIST's post-quantum standards. | Runs on your servers · Nothing sent to Acxelin Quantum · FIPS 203 (ML-KEM) · FIPS 204 (ML-DSA) | M4 |
| 3:35–3:45 | One more line. | Hold. | One honest limit: browsers can't yet check quantum-safe certificates, so public sites keep a regular one. The key exchange stays quantum-safe. | Public websites keep a public certificate. | M4 |
| 3:45–4:00 | Close: "Acxelin QGuard", the signature line, the logo, acxelinquantum.com. | As in Film 1. | Acxelin QGuard. Protect what you can't rewrite. | Acxelin QGuard · Protect what you can't rewrite. · acxelinquantum.com | M5 |

---

## Film 3: Acxelin QVPN

| Time | On screen | Motion and transition | Voice-over | On-screen text | Music |
|---|---|---|---|---|---|
| 0:00–0:07 | Dark frame. Kinetic type: "Encryption has a shelf life." | As in Film 1. | Here's something nobody prints on the label. Encryption has a shelf life. | Encryption has a shelf life. | M1 |
| 0:07–0:15 | "Recorded today. Opened later." with the amber rule. | The rule draws. | Your tunnels can be recorded today, and opened later, once a quantum computer is big enough. | Recorded today. Opened later. | M1 holds |
| 0:15–0:25 | Diagram: two offices and three laptops (one at a café table), joined by lines to a gateway. | Slow drift; the pieces ease in. | Offices. Laptops. People working from anywhere. All joined by tunnels. | | M2: pulse enters |
| 0:25–0:35 | The lines are quietly copied into a box labelled "recorded today". | The lines duplicate and slide into the box. | Most agree their keys with maths a big enough quantum computer will break. Some of that traffic must stay private for years. | "Our tunnels are recorded today." | M2 |
| 0:35–0:45 | One laptop picks up a tag: "last day". | A slow push in. | Oh, and when someone leaves, their access should leave with them. Quickly. | | M2 |
| 0:45–1:05 | Title card, then the diagram redrawn: every line's keys agreed over a quantum-safe connection, with a certificate at each end. | Cut; the lines redraw in sequence. | Meet Acxelin QVPN. It links your offices to each other and your people to your network. Every tunnel's keys are agreed over quantum-safe connections, using your own certificates. | Acxelin QVPN · Offices and people, joined quantum-safe. | M3: full bed |
| 1:05–1:25 | Section card "01 · Sites". Sites: `Headquarters` and `Branch office`, each with its status. | Card for 1.5 s; the window rises; a slow push on the status pills. | Start with the offices. The console shows every site, and whether its tunnel is protected, at a glance. | Lower third: Console · Sites | M3 |
| 1:25–1:45 | Section card "02 · People". **Invite someone**: the name `alice` is typed and the invitation downloaded. | Cut; typing at human speed. | Now, people. Invite someone by name, and they get a single file. It works once. | Lower third: Console · People | M3 |
| 1:45–1:55 | "Invitations not used yet": `alice`, with Cancel. | Push in on the row. | Until it's used, it waits right here. Changed your mind? Cancel it. | | M3 |
| 1:55–2:15 | Section card "03 · Join". Alice's laptop: the Acxelin QVPN app, **Set up this computer**, the invitation chosen, and a passphrase typed (shown as dots). | Cut to the app window on the branded background. | On their laptop, the Acxelin QVPN app opens the invitation. A passphrase locks this computer's key, and that key never leaves it. | Lower third: Acxelin QVPN app | M3 |
| 2:15–2:25 | **Breather.** **Connect**: the status turns to "Protected". | Push in on "Protected" and hold for 2 s. | Connect. Protected. | Protected | B: the music lifts |
| 2:25–2:40 | The admin console: Alice's row now shows "Connected". | Cut; a slow push in. | Back in the console, there they are. Connected. | Connected | M3 |
| 2:40–2:55 | Section card "04 · Revoke". **Revoke** `alice`, then confirm. | Cut; clicks at human speed. | And when they leave, revoke them. The gateway cuts them off within a minute. | Revoked | M3 |
| 2:55–3:10 | Alice's app: "Your access was revoked …". A small time marker shows the real time between revoking and this frame. | Cut; the time marker in Roboto Mono sits in a corner. | Their app tells them at its next key renewal, within two minutes, and says to ask for a new invitation. No guessing. | "Your access was revoked" · real elapsed time | M3 |
| 3:10–3:20 | Health: each check, a warning and its "What to do". | Cross-dissolve; push in on "What to do". | And if anything needs attention, Health says what's wrong and what to do next. | Lower third: Console · Health | M3 resolves |
| 3:20–3:35 | Dark frame; lines one by one. | Type sets in. | It runs on your own gateways and computers, and nothing is sent to Acxelin Quantum. Keys are agreed with NIST's post-quantum standards. | Runs on your gateways · Nothing sent to Acxelin Quantum · FIPS 203 (ML-KEM) · FIPS 204 (ML-DSA) | M4 |
| 3:35–3:45 | One more line. | Hold. | Two honest limits: there's no phone app yet, and gateways run on Linux. | Windows, macOS and Linux laptops · Linux gateways | M4 |
| 3:45–4:00 | Close: "Acxelin QVPN", the signature line, the logo, acxelinquantum.com. | As in Film 1. | Acxelin QVPN. Private today. Private later. | Acxelin QVPN · Private today. Private later. · acxelinquantum.com | M5 |

---

## Claim check

Every claim the films make, and where it holds in the product as built.

| Claim | Where it holds |
|---|---|
| Recorded today, opened later by a large enough quantum computer | The risk each product's README describes; QReadiness's endpoint reason ("harvest now, decrypt later") in `endpoints.py` |
| QReadiness reads code, configuration, certificates and servers, on your own computer | `products/readiness/README.md`; the console scans a local repository |
| The result leads with "things to fix now"; each finding shows place, why and fix; four parts: found, why, what could happen, what to do | `console.html` project result and `section(...)` headings |
| Grades A to F; A is post-quantum key exchange only; C means traffic recorded today can be decrypted later | `console.html` GRADES and `endpoints.py` |
| Owner, date and status for each finding | Console tracking (owner, due date, status, accepted risk) |
| The overview lists the services most at risk | `console.html` Overview, "Services most at risk" |
| A CycloneDX CBOM and a board summary | Endpoints, **Download CBOM** (CycloneDX 1.6); "Post-quantum readiness: board summary" |
| QReadiness shows what it looks for | Coverage tab: "Five kinds of asset", "Every algorithm it knows", "Where it looks" |
| Advice follows NIST's standards | Recommendations name ML-KEM (FIPS 203) and ML-DSA (FIPS 204); deadlines follow NIST IR 8547 |
| QReadiness limit: cryptography a program assembles while it runs can be missed | README Limits |
| QGuard is a product you install and run, not a service | README; manual "Questions" |
| QGuard issues the certificate, writes settings and starts in front of the app; the app doesn't change | Console Services and "QGuard on this computer"; `stage3_qguard.py` checks 1–3 |
| Watch mode serves everyone and says how many would be refused and why; enforcement turns old clients away | Console Services ("1 would be refused once enforcing" and its reason); `test_console_services.py::test_a_running_guard_reports_each_service_including_who_watch_mode_would_refuse`; `stage3_qguard.py` |
| QCertificate is a certificate authority built in; a partner certificate lets only that partner in; revoked partners are refused within a minute | Partner API kind (`require_client_cert` with QCertificate's revocation list); 3 s measured in Stage 1 on the CA's machine; `crl_every` 60 s elsewhere (manual) |
| Check a connection answers in plain words | Console "Check a connection"; `connection.py` verdicts; `test_console_services.py::test_check_a_connection_with_qcertificate_or_public_trust` |
| QGuard follows NIST's standards for key exchange and certificates | Policies (X25519MLKEM768 and others; ML-DSA certificates) |
| QGuard limit: browsers can't check ML-DSA certificates; public sites keep a public one, with a quantum-safe key exchange | Manual "Public websites and browsers"; the `transition` policy for websites |
| QVPN joins offices and people; keys agreed over quantum-safe connections with your own certificates | `products/vpn/README.md` |
| The console shows each site and its tunnel's state | Console Sites tab |
| An invitation is one file that works once; unused ones wait and can be cancelled | Console People, "Invitations not used yet" |
| A passphrase locks the computer's key, which never leaves it | `app.html` set-up text |
| The app shows "Protected"; the console shows "Connected" | `app.html` WORDS.protected; console People pill |
| The gateway cuts a revoked person off within a minute; the app says so within two minutes | QVPN manual timing (V8): gateway within 15 s, plus up to `crl_every` (60 s) when it fetches the list remotely; the app at its next key renewal, within 2 minutes |
| Health says what's wrong and what to do | Console Health tab ("Warning", "Problem", "What to do") |
| QVPN limits: no phone app; Linux gateways | `products/vpn/README.md` Limits |
| Nothing is sent to Acxelin Quantum | Each README; the manuals' "Questions" |

The films never use "unbreakable", "military-grade" or "100% secure", or any speed, customer count or other number the products did not show on screen. The illustrative tags in the problem diagrams ("built 2014", "last day") describe fictional situations, not product results.

## Production notes

- **QVPN "Protected":** this shot needs a real tunnel.
  - The recording laptop needs WireGuard for Windows (a system-wide install, so the owner's decision) or a Linux desktop with WireGuard joined to a gateway.
  - Without it, the app honestly shows "Keys agreed, not protected", and the shot at 2:15 can't be filmed as written.
- **Revocation shots (QGuard 2:45, QVPN 2:55):** these show the real elapsed time on screen rather than hiding the wait. The edit can shorten the wait, but the marker keeps the true time.
- **QGuard terminals:** these use curl with OpenSSL 3.5 in a container, because Windows' own curl can't do quantum-safe key exchange.
- **Breathers:** keep them. They are the gaps that stop the films feeling crowded.

## The 3:00 edit

The films were made at 4:00 from this script. The delivered versions are a 3:00 edit of those renders (`video/cut.py`): the minute comes only out of quiet holds after each line, the music-only breathers and the long hold on the close. Every scene, every spoken line, the section numbers and the real-time revocation markers stay. Joins are 0.3 s dissolves, the score crossfades at the same points, and the narration and captions are placed again on the new timeline. The 4:00 versions are kept beside them.
