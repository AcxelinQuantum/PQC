# Voice-over: recording script

Everything the narrator says in the three product films, line by line, exactly as in the approved script (`documents/video-script.md`). Each line is one file. The pipeline places every file at its moment in the film and times the captions from it, so the words must match the script exactly.

## How to record

- **File format:** WAV, mono, 48 kHz, 24-bit (16-bit is fine). No music, no effects, no compression or limiting. The build sets the loudness to -14 LUFS.
- **Levels:** peaks around -6 dBFS, never clipping. Record in a quiet, soft-furnished room, about a hand's width from the microphone, with a pop filter.
- **Files:** one file per line, named exactly as in the tables (for example `qreadiness-01.wav`), with about half a second of silence at the start and the end. Trim breaths and mouth clicks, but not the pause inside a line.
- **Pace:** relaxed, about 130–150 words a minute, conversational, like explaining something to a colleague you respect. There is plenty of room. Each line must end before its **Max** time; the build warns about any line that runs over.
- **Voice:** one narrator for all three films. Keep the same distance, room and energy across every session, so the three films sound like a family.
- **Words:** say "Acxelin" and "Acxelin Quantum" the way the company says them; record a few takes of the product names and pick one pronunciation for every film. Say QReadiness, QGuard, QCertificate and QVPN as "Q" plus the word ("Q Readiness", "Q Guard", "Q Certificate", "Q V P N"). Say NIST as "nist", one word.
- **Retakes:** if a line comes out stiff, record it again and keep the best take under the same file name.

When the files are ready, put them all in one folder and give me its path. The build uses them instead of the scratch voice.

## Acxelin QReadiness

Tone: Curious and reassuring. The board's question is a fair one; the answer is a relief. 17 lines, 295 words, 4:00 film.

| File | In the film | Max | Line | Note |
|---|---|---|---|---|
| `qreadiness-01.wav` | 0:00 | 6.6 s | Here's something nobody prints on the label. Encryption has a shelf life. |  |
| `qreadiness-02.wav` | 0:07 | 7.6 s | Traffic recorded today can be opened later, once a quantum computer is big enough. |  |
| `qreadiness-03.wav` | 0:15 | 9.6 s | So the board asks a fair question. When do we switch to quantum-safe cryptography? |  |
| `qreadiness-04.wav` | 0:25 | 9.6 s | And the honest answer begins with an awkward one. We don't actually know where it is. |  |
| `qreadiness-05.wav` | 0:35 | 9.6 s | It's in code. In configuration. In certificates. In a server nobody has touched in years. |  |
| `qreadiness-06.wav` | 0:45 | 19.5 s | Meet Acxelin QReadiness. It finds the cryptography you depend on, tells you what a quantum computer, or an attacker today, could break, and ranks what to change first. For security and engineering teams alike. |  |
| `qreadiness-07.wav` | 1:05 | 14.6 s | Start with a repository. Pick it, press scan, and it gets to work, right here on your own computer. |  |
| `qreadiness-08.wav` | 1:20 | 19.5 s | Moments later, one number leads: the things to fix now. Open any of them, and you see where it is, why it matters, and exactly what to change. |  |
| `qreadiness-09.wav` | 1:50 | 14.6 s | Next, the servers you actually run. Type their addresses, and each one gets a grade, A to F. |  |
| `qreadiness-10.wav` | 2:05 | 14.6 s | An A means quantum-safe key exchange only. A C means today's traffic could be read later. Good to know first. |  |
| `qreadiness-11.wav` | 2:20 | 19.5 s | Now make it someone's job. Give each fix an owner and a date, and follow it through to done. |  |
| `qreadiness-12.wav` | 2:40 | 9.6 s | And the overview keeps the riskiest services right at the top. |  |
| `qreadiness-13.wav` | 2:50 | 19.5 s | And when the auditors call, you're ready: a standard bill of materials for your cryptography, and a one-page summary for the board. |  |
| `qreadiness-14.wav` | 3:10 | 9.6 s | Curious what it looks for? It shows you that too. | Light, almost an aside. |
| `qreadiness-15.wav` | 3:20 | 14.6 s | It runs on your own machines. Nothing is sent to Acxelin Quantum. And its advice follows NIST's post-quantum standards. |  |
| `qreadiness-16.wav` | 3:35 | 9.6 s | One honest note: cryptography a program assembles while it runs can slip past. We'd rather tell you now. |  |
| `qreadiness-17.wav` | 3:45 | 14.6 s | Acxelin QReadiness. Know where you stand. |  |

## Acxelin QGuard

Tone: Calm confidence with a dry smile. The 'nobody dares to touch it' line is the wink. 17 lines, 288 words, 4:00 film.

| File | In the film | Max | Line | Note |
|---|---|---|---|---|
| `qguard-01.wav` | 0:00 | 6.6 s | Here's something nobody prints on the label. Encryption has a shelf life. |  |
| `qguard-02.wav` | 0:07 | 7.6 s | Connections recorded today can be opened later, once a quantum computer is big enough. |  |
| `qguard-03.wav` | 0:15 | 9.6 s | You know your services need quantum-safe encryption. The plan looks great on a slide. |  |
| `qguard-04.wav` | 0:25 | 9.6 s | Then reality. The website, the APIs, the database: they can't be rewritten in time. |  |
| `qguard-05.wav` | 0:35 | 9.6 s | And that one system nobody dares to touch? Nobody's touching it. |  |
| `qguard-06.wav` | 0:45 | 19.5 s | Meet Acxelin QGuard. A product you install and run yourself, not a service. It sits in front of the services you already have, and makes the connections to them quantum-safe. The services stay exactly as they are. |  |
| `qguard-07.wav` | 1:05 | 14.6 s | Open the console and protect a service. Say what it is, its address, and where it runs today. |  |
| `qguard-08.wav` | 1:20 | 14.6 s | QGuard issues its certificate, writes its own settings, and starts in front of the app. |  |
| `qguard-09.wav` | 1:45 | 19.5 s | Not sure who's still on old software? Start in watch mode. Everyone is served as usual, and QGuard tells you how many would be refused, and why. |  |
| `qguard-10.wav` | 2:05 | 14.6 s | When that list is empty, turn on enforcement. Old clients are turned away. Quantum-safe ones carry on. |  |
| `qguard-11.wav` | 2:20 | 9.6 s | Every door needs a list of who's allowed in. That's QCertificate: your own certificate authority, built in. |  |
| `qguard-12.wav` | 2:30 | 14.6 s | Issue a certificate for a partner, and only that partner gets into your API. |  |
| `qguard-13.wav` | 2:45 | 14.6 s | Partnership over? Revoke it, and QGuard turns them away within a minute. |  |
| `qguard-14.wav` | 3:00 | 19.5 s | Want to know how a connection really behaves? Type an address, and get the answer in plain words. |  |
| `qguard-15.wav` | 3:20 | 14.6 s | It runs on your servers, and nothing is sent to Acxelin Quantum. Key exchange and certificates both follow NIST's post-quantum standards. |  |
| `qguard-16.wav` | 3:35 | 9.6 s | One honest limit: browsers can't yet check quantum-safe certificates, so public sites keep a regular one. The key exchange stays quantum-safe. |  |
| `qguard-17.wav` | 3:45 | 14.6 s | Acxelin QGuard. Protect what you can't rewrite. |  |

## Acxelin QVPN

Tone: Warm and steady. 'Connect. Protected.' is the moment: let it land. 18 lines, 268 words, 4:00 film.

| File | In the film | Max | Line | Note |
|---|---|---|---|---|
| `qvpn-01.wav` | 0:00 | 6.6 s | Here's something nobody prints on the label. Encryption has a shelf life. |  |
| `qvpn-02.wav` | 0:07 | 7.6 s | Your tunnels can be recorded today, and opened later, once a quantum computer is big enough. |  |
| `qvpn-03.wav` | 0:15 | 9.6 s | Offices. Laptops. People working from anywhere. All joined by tunnels. |  |
| `qvpn-04.wav` | 0:25 | 9.6 s | Most agree their keys with maths a big enough quantum computer will break. Some of that traffic must stay private for years. |  |
| `qvpn-05.wav` | 0:35 | 9.6 s | Oh, and when someone leaves, their access should leave with them. Quickly. |  |
| `qvpn-06.wav` | 0:45 | 19.5 s | Meet Acxelin QVPN. It links your offices to each other and your people to your network. Every tunnel's keys are agreed over quantum-safe connections, using your own certificates. |  |
| `qvpn-07.wav` | 1:05 | 19.5 s | Start with the offices. The console shows every site, and whether its tunnel is protected, at a glance. |  |
| `qvpn-08.wav` | 1:25 | 19.5 s | Now, people. Invite someone by name, and they get a single file. It works once. |  |
| `qvpn-09.wav` | 1:45 | 9.6 s | Until it's used, it waits right here. Changed your mind? Cancel it. |  |
| `qvpn-10.wav` | 1:55 | 19.5 s | On their laptop, the Acxelin QVPN app opens the invitation. A passphrase locks this computer's key, and that key never leaves it. |  |
| `qvpn-11.wav` | 2:15 | 9.6 s | Connect. Protected. | Two separate words. About a one-second pause between them. |
| `qvpn-12.wav` | 2:25 | 14.6 s | Back in the console, there they are. Connected. |  |
| `qvpn-13.wav` | 2:40 | 14.6 s | And when they leave, revoke them. The gateway cuts them off within a minute. |  |
| `qvpn-14.wav` | 2:55 | 14.6 s | Their app tells them at its next key renewal, within two minutes, and says to ask for a new invitation. No guessing. |  |
| `qvpn-15.wav` | 3:10 | 9.6 s | And if anything needs attention, Health says what's wrong and what to do next. |  |
| `qvpn-16.wav` | 3:20 | 14.6 s | It runs on your own gateways and computers, and nothing is sent to Acxelin Quantum. Keys are agreed with NIST's post-quantum standards. |  |
| `qvpn-17.wav` | 3:35 | 9.6 s | Two honest limits: there's no phone app yet, and gateways run on Linux. |  |
| `qvpn-18.wav` | 3:45 | 14.6 s | Acxelin QVPN. Private today. Private later. |  |

52 lines in all.
