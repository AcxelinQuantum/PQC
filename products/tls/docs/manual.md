# Acxelin QGuard manual

Acxelin QGuard is software you install on your own servers. It sits in front of the websites, APIs and databases you already run and makes every connection to them quantum-safe, with your own certificate authority, QCertificate, built in. The services behind it do not change. It is not a cloud service: it runs on your machines, holds your keys, and never contacts Acxelin Quantum.

This manual covers installing it, protecting a first service in five minutes, the everyday work, running it in production, and what to do when something goes wrong. Acxelin QGuard installs and runs on its own; it needs no other Acxelin product.

## 1. What you get

One installation gives one command, `acxelin-qguard`, and three parts:

| Part | What it does |
|---|---|
| **The guard** (the `edge` in commands and settings) | Sits in front of a service you protect (a web app, PostgreSQL, MQTT, anything on TCP) and lets in only quantum-safe connections; or, as a tunnel, lets a plain local client reach a remote guard. |
| **QCertificate**, the certificate authority | Issues, renews and revokes the quantum-safe (ML-DSA) certificates, keeps the revocation list fresh, and enrols machines over EST and ACME. |
| **The console** | A local web page for the everyday work: protect a service, watch what it sees, turn on enforcement, run QCertificate, check any connection. |

A connection that cannot meet your policy ends. Nothing falls back silently to a key exchange a quantum computer could break.

## 2. Before you start

- **Python 3.11 to 3.14**, on Linux, macOS or Windows.
- **OpenSSL 3.5 or newer.** Debian 13 and Ubuntu 25.04 have it. On macOS run `brew install openssl@3`; on Windows, `choco install openssl`. The Docker image includes it.
- For the console: a web browser on the same machine, or an SSH connection to it.

## 3. Install

The release folder installs on Linux (x86-64 and ARM), Windows (x64) and Macs with Apple silicon, with Python 3.11 to 3.14. On an Intel Mac, use the Docker image.

Get two files from the [release page](https://github.com/AcxelinQuantum/PQC/releases/tag/qguard-v1.3.0) and save them in one folder:

- `acxelin-qguard-1.3.0-wheelhouse.tar.gz`: the program, with everything it needs, so it installs without internet access
- `SHA256SUMS`: a fingerprint of every file in the release

Then open a terminal in that folder. On Windows, use PowerShell.

**Step 1: check the download.** This confirms the file is exactly the one we published, not damaged or changed on the way. It only reads the file.

On Linux:

```
sha256sum -c SHA256SUMS --ignore-missing
```

You should see the file's name followed by `OK`.

On macOS:

```
shasum -a 256 acxelin-qguard-1.3.0-wheelhouse.tar.gz
```

On Windows:

```
Get-FileHash .\acxelin-qguard-1.3.0-wheelhouse.tar.gz
```

On macOS and Windows this prints the file's fingerprint, a long string of letters and numbers. It should match the one next to the file's name in `SHA256SUMS` (capital or small letters do not matter). If the check fails, delete the file and download it again. Do not install it.

Optional: if you use the GitHub command line, `gh attestation verify acxelin-qguard-1.3.0-wheelhouse.tar.gz --owner AcxelinQuantum` shows that our release workflow built the file. You should see `Verification succeeded`.

**Step 2: unpack it.** The same two lines work in PowerShell:

```
tar xzf acxelin-qguard-1.3.0-wheelhouse.tar.gz
cd acxelin-qguard-1.3.0-wheelhouse
```

**Step 3: install.** Still in that folder:

| System | Run |
|---|---|
| Linux, macOS | `sh install.sh` |
| Windows | `Unblock-File .\install.ps1`, then `powershell -ExecutionPolicy RemoteSigned -File .\install.ps1` |

On Windows, the first command tells Windows you trust this downloaded script, and the second runs it.

The installer checks your Python, finds OpenSSL 3.5, puts `acxelin-qguard` on your PATH and runs a health check. A ready machine prints:

```
acxelin-qguard 1.3.0, Python 3.11.15
ok    cryptography 50.0.2 issues ML-DSA certificates
ok    OpenSSL 3.5.4 30 Sep 2025 can do post-quantum TLS 1.3
```

If OpenSSL 3.5 is in a folder of its own, run `ACXELIN_OPENSSL=/path/to/openssl-3.5/lib sh install.sh`. On Windows, set `ACXELIN_OPENSSL` to the folder that holds its DLLs before running `install.ps1`.

To remove it, run `sh install.sh --uninstall` (or `install.ps1 -Uninstall`). Your certificates and settings stay where you put them.

**With Docker instead:** build the image, which includes OpenSSL 3.5, from the repository at the release's tag, and give it the short name the rest of this manual uses. (A published image is planned; it cannot be pulled yet.)

```
git clone --branch qguard-v1.3.0 https://github.com/AcxelinQuantum/PQC && cd PQC
docker build -f products/tls/deploy/Dockerfile -t acxelin-qguard .
docker run --rm acxelin-qguard doctor
```

On Windows, clone with `git -c core.autocrlf=false clone ...` so the image's start-up script keeps Linux line endings.

## 4. See it work in one minute

```
acxelin-qguard try
```

The tour sets up a CA, an ordinary web server and an edge in front of it, then shows a post-quantum client getting through and a classical client being refused. It needs nothing else and leaves nothing behind.

## 5. Protect your first service in five minutes

These steps put QGuard in front of a web app listening on `127.0.0.1:8080`.

### In the console

1. Run `acxelin-qguard console`. Your browser opens, signed in.
2. **Create your certificate authority**: give it a name and a passphrase. That is QCertificate.
3. **Protect your first service**: choose what it is (a public website, an internal app or API, a partner API, or a database), type the address people use (such as `shop.example.com`) and the port, and where the service runs now (`127.0.0.1:8080`). For a public website, also give its ordinary public certificate (section 6, "Public websites and browsers"). Choose **Protect service**: the console issues the certificate and writes QGuard's settings file.
4. Choose **Start QGuard on this computer**. QGuard is now in front of the app.
5. Choose **Check connection** on the service: it says whether the key exchange and the certificate are quantum-safe.

For a server, run QGuard as a system service instead of from the console (section 8). The console keeps editing the same settings file, and the running service applies every change within seconds.

### From the command line

The same, step by step, for scripts and servers without a browser.

### Step 1: create the certificate authority

Choose a passphrase for its key; you need it whenever you issue or revoke.

```
acxelin-qguard ca init --name "Example Root CA" --dir pki
```

It prints `created ML-DSA-87 root 'Example Root CA' in pki`. Keep the `pki` folder safe: `pki/ca.key` is the key every certificate depends on.

### Step 2: issue the edge's certificate

Use the name your clients will connect to:

```
acxelin-qguard ca issue server web.example.com --dir pki --out web
```

`web/chain.pem` is the certificate with the CA, and `web/key.pem` is its private key.

### Step 3: start the edge in front of the app

```
acxelin-qguard edge --listen 0.0.0.0:8443 --target 127.0.0.1:8080 --cert web/chain.pem --key web/key.pem --metrics 127.0.0.1:9100
```

For a web app, add `--forwarded-headers` so it sees each visitor's address and that the visit was https (section 6, "Web apps behind QGuard").

### Step 4: test it

From any machine that has `pki/ca.crt` (without `--ca`, `connect` trusts the public authorities this computer trusts, as a browser does):

```
acxelin-qguard connect web.example.com:8443 --ca pki/ca.crt --send "GET / HTTP/1.0\r\n\r\n"
```

You see what was negotiated, a one-line verdict, then the app's reply:

```
    version  TLSv1.3
      group  X25519MLKEM768
       peer  CN=web.example.com
   peer_key  ML-DSA-65
    verdict  quantum-safe key exchange, quantum-safe certificate (ML-DSA-65)
      reply  HTTP/1.0 200 OK
```

When a connection fails, `connect` says why in words, for example that a site offers a post-quantum key exchange but a classical certificate. `acxelin-qguard connect www.example.com:443 --policy transition` checks any public site the way a browser would.

### Step 5: check the edge's counters

`acxelin-qguard status --url http://127.0.0.1:9100` prints the policy, the open connections and the key exchanges clients negotiated.

A client that cannot do post-quantum key exchange is refused, and the edge's log says why: `the client offers none of the key exchanges this policy allows`.

## 6. Everyday tasks

| Task | Command |
|---|---|
| Open the console | `acxelin-qguard console` |
| Issue a server certificate | `acxelin-qguard ca issue server NAME --dir pki --out FOLDER` |
| Issue a client certificate (mutual TLS) | `acxelin-qguard ca issue client NAME --dir pki --out FOLDER` |
| List what the CA issued | `acxelin-qguard ca list --dir pki` |
| Renew a certificate | `acxelin-qguard ca renew SERIAL --dir pki` |
| Certify a key made elsewhere | `acxelin-qguard ca sign-csr request.csr --kind server --dir pki --out FOLDER` |
| Revoke a certificate | `acxelin-qguard ca revoke SERIAL --dir pki` |
| Renew what expires soon and refresh the CRL | `acxelin-qguard ca maintain --dir pki` (daily) |
| Check a CA folder or an edge configuration | `acxelin-qguard doctor --ca pki --config edge.toml` |
| nginx, PostgreSQL, pgvector or MQTT behind an edge | `acxelin-qguard bundle nginx --host web.example.com` |

Passphrases come from `ACXELIN_TLS_CA_PASSPHRASE` or a prompt, never from the command line.

### Require client certificates (mutual TLS)

Add three options to the edge. Then only machines holding a certificate from your CA, and not revoked, get through.

```
acxelin-qguard edge --listen 0.0.0.0:8443 --target 127.0.0.1:8080 --cert web/chain.pem --key web/key.pem \
  --require-client-cert --ca pki/ca.crt --crl pki/crl.pem
```

Give each client its own certificate (`acxelin-qguard ca issue client laptop-01 --dir pki --out laptop`). It connects with `--cert laptop/chain.pem --key laptop/key.pem`. A client without one is refused, and the edge logs `peer did not return a certificate`.

### Short-lived certificates

A certificate that lives for a day needs no revocation: it is gone by tomorrow. To use them, issue with hours and renew automatically:

```
acxelin-qguard ca issue server payments.internal --dir pki --hours 24 --out payments
acxelin-qguard ca maintain --dir pki
```

`ca maintain` renews a short-lived certificate in the last third of its life (a 24-hour certificate at 8 hours) into the same folder, and edges pick the new one up without a restart. A renewal keeps the lifetime. Anything up to 7 days counts as short-lived; longer certificates renew for 397 days, as before. Use `--renew-within-hours N` to choose the window yourself.

What you take on: **something must run `ca maintain` at least every third of the shortest lifetime** (every 8 hours for 24-hour certificates), on a machine that can reach the CA. If it stops, the services stop when their certificates expire. `acxelin-qguard doctor` tells you the interval, and warns when a certificate is due and has not been renewed. The CRL still matters for mutual TLS: a revoked client is refused at once, not at expiry, and the CRL (7 days by default) is re-signed every time `maintain` runs.

### Revoke a certificate

```
acxelin-qguard ca revoke 775089c0ad0f5832 --dir pki
```

The CA re-signs `pki/crl.pem`. An edge that reads that file refuses the certificate from its next connection, without a restart. An edge on another machine needs the new CRL: run `acxelin-qguard ca publish` next to the CA and set `crl_url` on the edge, which then fetches it every minute.

### Several routes in one edge

Write the routes in a file and start the edge with `acxelin-qguard edge --config edge.toml`. Each `[[edge]]` table is one route:

```
[metrics]
listen = "127.0.0.1:9100"

[[edge]]
name = "web"
mode = "terminate"                  # post-quantum TLS in front of a plain service
listen = "0.0.0.0:8443"
target = "127.0.0.1:8080"
policy = "strict"
cert = "web/chain.pem"
key = "web/key.pem"

[[edge]]
name = "to-datacenter"
mode = "originate"                  # a plain local client reaches a remote edge
listen = "127.0.0.1:5432"
target = "db.example.com:8443"
server_name = "db.example.com"
ca = "pki/ca.crt"
```

`config/example.toml` lists every setting. Saving the file reloads it without a restart, and certificates are re-read when their files change.

### Staple an OCSP answer to your certificate

Clients that ask can learn that the edge's own certificate is still good (or revoked) from an answer the CA signed, sent inside the handshake, so they do not have to contact the CA.

```
acxelin-qguard ca ocsp --dir pki --cert shop/chain.pem --out shop/staple.der --hours 24
```

then set `ocsp_staple = "shop/staple.der"` on the route. `acxelin-qguard connect` shows what the edge staples, and `acxelin-qguard doctor --config` warns when the answer is missing or ends within a day. The route's `cert` must be the `chain.pem` that includes the CA. Run `ca ocsp` again before the answer ends (daily from cron is enough for 24 hours); the edge picks up the new file without a restart.

What it does and does not do:

- A missing, unreadable, forged, stale or wrong-certificate file is not sent and does not break the handshake; the edge logs why when it starts. A client that insists on a staple (a "must-staple" policy) would then refuse the edge, so renew the file well before it ends.
- It is about the edge's own certificate. How the edge treats its clients' certificates is still the CRL (`crl`, `crl_url`); this does not replace it.
- The answer is signed with the CA's key file. CAs whose key is in a KMS or behind a signing command are not supported yet.
- There is no OCSP responder service: the answer is a file you refresh. Tested with ML-DSA-signed answers through OpenSSL 3.5 and with this product's own client; not with browsers or other TLS libraries.

### One port, several services (server name and protocol)

Routes that listen on the same address share the port. The edge reads which server name (SNI) and application protocol (ALPN) the client asks for, before the handshake, and hands the connection to the most specific route:

```
[[edge]]
name = "payments"
listen = "0.0.0.0:443"
target = "10.1.0.10:8080"
sni = ["payments.bank.example"]
cert = "pay/chain.pem"
key = "pay/key.pem"
ca = "pki/ca.crt"
require_client_cert = true

[[edge]]
name = "api"
listen = "0.0.0.0:443"
target = "10.1.0.20:8080"
sni = ["*.api.bank.example"]
alpn = ["h2"]
cert = "api/chain.pem"
key = "api/key.pem"

[[edge]]
name = "everything-else"
listen = "0.0.0.0:443"
target = "10.1.0.30:8080"
cert = "web/chain.pem"
key = "web/key.pem"
```

`alpn` only chooses the route: QGuard serves HTTP/1.1 and passes other protocols through as they are, but it does not negotiate HTTP/2 with clients (see Limits).

An exact name beats a wildcard, which beats no name; asking for a protocol adds to it. A route with neither is the default for the port, and there can be only one. Each route keeps its own certificate, policy, client-certificate rule, CRL and limits. A client that asks for a name no route serves, with no default to catch it, is closed and counted (`unrouted` in the status). A client that sends no readable hello within a few seconds is closed (`unreadable`).

Limits: a client that sends no server name reaches only routes without `sni`. Changing one route while running leaves the others on the port untouched. The routing decision reads only the name and protocol, never a certificate or any application data. Routes in `originate` mode have their own ports.

### Policies

| Policy | Allows |
|---|---|
| `strict` (default) | post-quantum key exchange and ML-DSA certificates only |
| `transition` | also classical clients while you migrate; use it with `fallback_cert` for browsers, which cannot verify ML-DSA yet |
| `cnsa2` | NSA CNSA 2.0: pure ML-KEM-1024 (no hybrid: NSA's CNSA 2.0 FAQ names none for TLS), ML-DSA-87 and AES-256 only |

### Web apps behind QGuard

QGuard passes bytes through unchanged unless you ask it to tell a web app about its visitors. Without that, the app sees every visitor as `127.0.0.1` and believes it is reached over plain `http`, so apps that build absolute links or redirects (WordPress, for one) send visitors to `http://...` and break.

Put `forwarded_headers = true` on the route (`--forwarded-headers` on the command line; the console sets it for websites, apps and partner APIs). For each HTTP/1.x request, QGuard then:

- removes any `Forwarded`, `X-Forwarded-For`, `X-Forwarded-Proto`, `X-Forwarded-Host` or `X-Real-IP` the visitor sent, so nobody can pose as someone else;
- adds `X-Forwarded-For` (the visitor's address), `X-Forwarded-Proto: https` and `X-Forwarded-Host` (the host asked for);
- passes request bodies unchanged, and refuses with `400` anything ambiguous: both `Content-Length` and `Transfer-Encoding`, conflicting lengths, folded headers, bare line feeds, `CONNECT`. These are the shapes behind request smuggling. Headers over 64 KB get `431`;
- relays a WebSocket unchanged once the app answers `101 Switching Protocols`. An upgrade must be the first request on its connection, as browsers send it.

Tell the app to trust these headers from `127.0.0.1` only: WordPress's official Docker image reads `X-Forwarded-Proto` by itself; Grafana needs `root_url`; most frameworks have a "trusted proxy" setting. Leave `forwarded_headers` off for databases and other protocols that are not HTTP.

Two more things web apps meet: QGuard closes a connection on which nothing is sent within 30 seconds of the handshake (`first_data_timeout`), and it does not serve HTTP/2 (browsers use HTTP/1.1 through it).

### Public websites and browsers

Browsers already use a quantum-safe key exchange (X25519MLKEM768), but they only trust certificates from public authorities, and those do not issue ML-DSA certificates yet. What a visitor sees depends on the route:

| Route | What Chrome and Edge show (tested with Chrome 158 and Edge 158) |
|---|---|
| `transition` with `fallback_cert` and `fallback_key`, an ordinary public certificate (Let's Encrypt, DigiCert) | The site, with a normal padlock. The key exchange is quantum-safe; the certificate is classical, as on every public site today (Google, Cloudflare, GitHub). |
| `transition` without a public certificate | "Your connection is not private" (NET::ERR_CERT_AUTHORITY_INVALID). |
| `strict` | "Your connection is not private", because the only certificate is ML-DSA. |
| `cnsa2` | "This site can't provide a secure connection" (ERR_SSL_VERSION_OR_CIPHER_MISMATCH): browsers do not offer ML-KEM-1024. |

So a public website uses `transition` with a public certificate. Keep `strict` and `cnsa2` for clients you control. The edge and `doctor` warn when a `transition` route has no public certificate, and the console says so on the service.

### Find out who `strict` would break, before you enforce it

Put `shadow = true` on a `strict` or `cnsa2` route (or `--shadow` on the command line). The route then serves every client as
`transition` would, and reports the ones its policy would have refused:

```
web: 203.0.113.9 would be refused under strict (no post-quantum key exchange offered); groups offered: x25519, secp256r1; signature schemes offered: ecdsa_secp256r1_sha256, rsa_pss_rsae_sha256
```

That line has the client's address, what it offered for key exchange and for signatures, and why. It is written once per address
every ten seconds. Nothing else of the client is read or kept: not the server name, the certificate, the key shares or any
application data. `/metrics` counts `shadow_ok` and `shadow_would_refuse` (and one counter per reason), and `/status` shows
`"shadow": true`. Watch for a few days, fix or exempt the clients that appear, then remove `shadow` to enforce. In the console, the service shows who would be refused and why, and **Turn on enforcement** makes the change; it also removes a `fallback_cert`, which a `strict` route cannot have (by hand, remove both lines, or the edge refuses to start with the new settings and keeps the old ones).

**Shadow mode does not enforce anything.** Classical clients are served, and they are as exposed to a recorded session as
before. A client that cannot verify ML-DSA certificates still fails the handshake unless the route has a `fallback_cert` (a
route in shadow mode may have one). The report is made from the client's first message, so it is correct whether or not the
handshake then succeeds. Clients that send their hello in several records, or something that is not TLS, are counted as
`shadow_unreadable`.

## 7. The console

```
acxelin-qguard console
```

Your browser opens, already signed in. The first time, it walks you through creating QCertificate and protecting your first service. The console asks for the authority's passphrase and keeps it in memory only, so it asks again after a restart.

| Place | What you do there |
|---|---|
| **Overview** | Every protected service at a glance: its kind, protection, how many connections were quantum-safe, who was refused, and what needs your attention (an expiring certificate, a public website without a public certificate, QGuard not running, a watched service ready for enforcement). |
| **Services** | Protect a service, edit or remove it, start by watching and turn on enforcement, check its connection. Start or stop QGuard on this computer. |
| **QCertificate** | Issue, renew, revoke and download certificates (a zip of the certificate, chain and CA, or one PEM file with the full chain and key); one-time tokens for devices that enrol themselves (EST); ACME account keys; the revocation list; the authority's details and its certificate. A private key reaches the browser only when you ask for it, and never for a revoked certificate or an encrypted key. |
| **Check a connection** | Connect to any address as a client would, trusting public authorities (like a browser) or QCertificate, and see whether the key exchange and certificate are quantum-safe, or why it failed. |
| **Settings** | Where the settings file, data and log are; whether this computer can run QGuard; other QGuard services to watch by their status address. |

The console writes the same settings file the QGuard service reads (by default `edge.toml` in its data folder; `--settings FILE` points it at another, such as `/etc/acxelin-tls/edge.toml`). Settings you wrote by hand are kept, but comments are not. Every action is written to an audit log that only you can read.

The console listens only on the machine it runs on. For a remote server, forward a port and ask the running console for a fresh link:

```
ssh -L 8900:127.0.0.1:8900 server
acxelin-qguard console link --port 8900
```

Run the second command in that SSH session, then open the address it prints on your laptop.

## 8. Running it in production

Run QGuard as a system service so it starts with the machine, and keep the console for the everyday work: point it at the service's settings file with `--settings`.

**Linux (systemd).** The release folder's `deploy/systemd` has `acxelin-tls-edge.service`, which runs `/opt/acxelin-tls/bin/acxelin-qguard edge --config /etc/acxelin-tls/edge.toml` as the user `acxelin`. As root:

```
ACXELIN_PREFIX=/opt/acxelin-tls ACXELIN_BIN=/opt/acxelin-tls/bin sh install.sh
useradd --system --home /var/lib/acxelin-tls --shell /usr/sbin/nologin acxelin
mkdir -p /etc/acxelin-tls /var/lib/acxelin-tls
cp deploy/systemd/acxelin-tls-edge.service /etc/systemd/system/
```

Put the settings file at `/etc/acxelin-tls/edge.toml` (the console writes it with `--settings /etc/acxelin-tls/edge.toml` when the admin running it can write there), make it and the certificates readable by `acxelin`, then `systemctl enable --now acxelin-tls-edge`. `systemctl reload acxelin-tls-edge` re-reads the settings; the service also applies changes on its own within seconds. Tested on Ubuntu 26.04 (systemd-analyze security rates the unit 1.6, "OK").

`acxelin-tls-maintain.service` and its daily timer run `ca maintain` for a CA in `/var/lib/acxelin-tls/pki`. It can only do that with the CA's passphrase, which it reads from `/etc/acxelin-tls/ca.env` (`ACXELIN_TLS_CA_PASSPHRASE=...`, mode 600). That puts the passphrase on the server. Choose one:
- run the timer only on the machine that holds the CA;
- give servers short-lived certificates they renew themselves over EST (section 9), so the CA's passphrase never leaves its machine;
- keep the CA key in an HSM or KMS (below).

**Windows.** Run QGuard at start-up with a scheduled task, in an administrator PowerShell:

```
$exe = "$env:LOCALAPPDATA\Acxelin\bin\acxelin-qguard.cmd"
$action = New-ScheduledTaskAction -Execute $exe -Argument "edge --config C:\ProgramData\Acxelin\edge.toml"
Register-ScheduledTask -TaskName "Acxelin QGuard" -Action $action -Trigger (New-ScheduledTaskTrigger -AtStartup) -User "SYSTEM" -RunLevel Highest
```

Install QGuard for an account the task can use (or copy the install to `C:\Program Files`), set `ACXELIN_OPENSSL` for that account, and start the console with `--settings C:\ProgramData\Acxelin\edge.toml`. Schedule `acxelin-qguard ca maintain` daily the same way on the machine that holds the CA.

**Docker.** Build the image (section 3); it includes OpenSSL 3.5, runs as user 10001 and keeps its files in `/data`:

```
docker run -d --name edge -v /etc/acxelin-tls:/data:ro -p 8443:8443 acxelin-qguard edge --config /data/edge.toml
docker run -d --name console -v acxelin-tls:/data -p 127.0.0.1:8900:8900 acxelin-qguard console --container
docker exec -it console acxelin-qguard console link
```

The files in `/etc/acxelin-tls` must be readable by user 10001. Publish the console's port on `127.0.0.1` only, as above.

**Before going live**, run `acxelin-qguard doctor --strict --ca pki --config edge.toml`. It exits 0 only when nothing needs attention.

### Keeping the CA safe

- The CA key is encrypted by default. Keep the passphrase in your password manager, not on the server.
- Keep the root offline and issue from an intermediate: `acxelin-qguard ca init --name "Example Issuing CA" --parent ROOT_DIR --dir issuing`. If the issuing CA is compromised, the root revokes it and makes a new one. A certificate is only checked against the CRL of the CA that issued it, so give an edge the intermediate's CRL; to let the root's revocation of the intermediate count too, put both in one file: `cat issuing/crl.pem pki/crl.pem > crls.pem`, and use `issuing/chain.pem` as `ca`.
- An `originate` edge listens on 127.0.0.1 unless you give `--listen`: anyone who can reach its port is tunnelled in with its client certificate, so keep it local or firewalled.
- The CA key can stay in a hardware security module: `--kms KEY_ID` keeps it in AWS KMS (install the `kms` extra), `--signer-command` hands each signature to your HSM's own tool, and `--pkcs11-module LIBRARY --pkcs11-token LABEL --pkcs11-key LABEL` signs inside any PKCS#11 token (add `--pkcs11-generate` to make the key there, sensitive and not extractable). The PIN is read from `ACXELIN_PKCS11_PIN`, never from a file or the command line. The token must offer `CKM_ML_DSA` (PKCS#11 3.2): SoftHSM2 does from its development branch, not in release 2.7.0 or the 2.6.1 that Ubuntu ships. This was run against SoftHSM2 only; none of the three has been run against a real HSM or a cloud account here, so test it with yours first.

### Monitoring

With `--metrics HOST:PORT`, an edge serves `/healthz`, `/metrics` (Prometheus) and `/status` (JSON).

| Metric | Meaning |
|---|---|
| `acxelin_tls_connections_active{edge}` | open connections |
| `acxelin_tls_events_total{edge,event}` | handshakes accepted and refused, by reason |
| `acxelin_tls_group_total{edge,group}` | connections by negotiated key-exchange group |

### Evidence for an audit or a pilot

`evidence create` puts what an edge is and does into one zip, signed with an ML-DSA key from your CA:

```
acxelin-qguard evidence create --config edge.toml --connect 127.0.0.1:8443 --ca pki/ca.crt --server-name web.corp.example --status http://127.0.0.1:9100 --sign-cert auditor/chain.pem --sign-key auditor/key.pem --out pilot.zip
acxelin-qguard evidence verify pilot.zip --ca pki/ca.crt
```

| File | What it holds |
|---|---|
| `build.json` | Versions of Acxelin QGuard, core and `cryptography`, and whether each installed file still matches its wheel; Python, platform and OpenSSL |
| `config.toml` | The configuration, byte for byte |
| `doctor.json` | What `doctor` finds about this machine and the configuration |
| `certificates.json` | Each route's certificates: subject, issuer, serial, algorithm, validity, SHA-256 fingerprint |
| `connect-N.json` | One handshake per `--connect`: group, cipher suite, the server's key, the stapled OCSP answer; or why it was refused |
| `status.json` | What the running edge reports at `--status` |

`manifest.json` lists every file with its SHA-256 and is signed (`manifest.sig`, with the signer's certificate in `signer.pem`).
`verify` reads the zip without unpacking it and fails if any file was changed, added or removed, if the signature does not match,
or if the signer's certificate does not chain to the CA you give. It does not check whether that certificate was revoked since.
Private keys, passphrases and the traffic itself never go in; a bundle that would hold a private key is refused. Issue the
signing certificate with `acxelin-qguard ca issue client auditor.acme --out auditor`.

## 9. Enrolling many machines

| Service | Command | For |
|---|---|---|
| EST (RFC 7030) | `acxelin-qguard ca serve` | Machines enroll with a one-time token from `ca token` over post-quantum TLS, and renew with `ca enroll`. The key never leaves the machine. |
| ACME (RFC 8555) | `acxelin-qguard ca acme` | Standard ACME clients, such as certbot with `--csr`. `ca eab` makes an external account binding key; `ca csr` makes a key and CSR. |
| CRL publishing | `acxelin-qguard ca publish` | Serves `ca.crt` and `crl.pem` over HTTP, so edges can follow revocations (`crl_url`). |

Every enrollment attempt is written to an owner-only audit log that never contains the token's secret.

### Names no web server answers for, and wildcards (ACME dns-01)

By default the ACME service proves a name by fetching a file over HTTP (http-01), which needs a web server on that name and cannot prove a wildcard. Give the service a command that looks up DNS TXT records and it also offers dns-01, which proves control by a record at `_acme-challenge.NAME` and is the only way to get a wildcard such as `*.corp.example`:

```
acxelin-qguard ca acme --dir pki --allow "*.corp.example" --dns-command dig +short TXT
```

The service appends the name (`_acme-challenge.corp.example`) to your command, which must print the TXT records it finds, one per line (quotes are fine). Any resolver your bank trusts will do; a script that asks your internal DNS is a normal choice. On Windows use `--dns-command powershell -NoProfile -File lookup.ps1`.

The client publishes the record, as certbot does with its manual or DNS hooks. Limits: the command runs without a shell, for at most 15 seconds, may print at most 64 KB, and receives only `PATH`, `HOME` and variables you start with `ACXELIN_DNS_`, never the CA passphrase. If it fails, the client is told to see the CA's log, not what the command said. Names are limited to ASCII letters, digits, hyphens and dots (write international names in punycode). Wildcards need `--allow` to list them. dns-01 is not offered for IP addresses.

### People, with their company sign-in (OIDC)

A person can get a client certificate in their own name with the ID token their identity provider issues, instead of a one-time token you hand out.

```
acxelin-qguard ca oidc --dir pki --issuer https://idp.corp.example --audience acxelin-enroll \
    --jwks-file idp-keys.json --domain corp.example --group pki-users
```

`--issuer` and `--audience` must match the `iss` and `aud` in the tokens. Give the provider's signing keys as a saved file (`--jwks-file`, which you refresh when the provider rotates its keys) or as an https address (`--jwks-url`, fetched at enrolment and kept for five minutes; if it cannot be reached, enrolment is refused). Without `--domain` or `--group`, any account at the provider can enrol, so set at least one.

The person runs, with the token in the environment so it is not on a command line:

```
acxelin-qguard ca enroll https://ca.corp.example:9443 --oidc --cn ana@corp.example --ca-fingerprint SHA256 --out ana
```

The certificate's name must be exactly the name the provider vouches for (the `email` claim, or the claim you chose with `--name-claim`). A token works once. The token must be RS256 or ES256 and signed by one of the provider's keys, for this issuer and audience, not expired, with a verified email; any other algorithm, including `none`, is refused. The CA keeps only a hash of each used token and never writes a token to its logs.

What this does not do: it does not open a browser or run the sign-in for the person; they get the ID token from your provider's own tools. It has been tested against tokens signed by a stand-in provider, not against a real Okta, Entra ID or Keycloak. The token and its signature are classical (RSA or ECDSA); they are checked on the CA, and the certificate it leads to is ML-DSA. Revoking an employee's access at the provider stops new enrolments, not certificates already issued: revoke those with `ca revoke`.

## 10. How a connection is decided

1. **Key exchange.** Under `strict`, the client must offer a post-quantum group: X25519MLKEM768, SecP384r1MLKEM1024 or SecP256r1MLKEM768. A client that offers only classical groups is refused.
2. **Certificates.** Under `strict`, certificates must use ML-DSA. A client that cannot verify ML-DSA is refused.
3. **Client certificate.** With `require_client_cert`, the client must present a certificate that chains to the CA and is not on the CRL. The CRL is valid for 7 days by default, and an edge whose CRL has expired refuses every client, so keep `ca maintain` running.

## 11. Watch it with Wireshark

You can see the post-quantum key exchange on the wire, and see a classical client being refused, with Wireshark (or its command-line `tshark`). This was checked with Wireshark 4.2.2 against the steps below.

**1. Start an edge and capture its port.** On the machine that runs the edge (or one on the same network path), capture the edge's port. For an edge on this machine at port 8443, capture on the loopback interface (`lo` on Linux, `Loopback` on macOS; on Windows install Npcap with loopback support and choose "Adapter for loopback traffic capture"):

```
tshark -i lo -f "tcp port 8443" -w edge.pcapng
```

**2. Connect a post-quantum client, then a classical one.**

```
acxelin-qguard connect 127.0.0.1:8443 --ca pki/ca.crt --server-name web.example.com
curl -k --curves X25519 https://127.0.0.1:8443/
```

The first succeeds and prints `group X25519MLKEM768`. The second is refused: curl reports `(35) ... alert handshake failure`. Stop the capture with Ctrl+C and open `edge.pcapng` in Wireshark.

**3. What you see.**

| Packet | What Wireshark shows | What it means |
|---|---|---|
| Client Hello (`SNI=web.example.com`) | Supported Groups and a Key Share for group 0x11EC, about 1,216 bytes long | The client offers X25519MLKEM768: an X25519 share (32 bytes) and an ML-KEM-768 encapsulation key (1,184 bytes) |
| Server Hello | Supported Version TLS 1.3, cipher suite TLS_AES_256_GCM_SHA384, a Key Share for group 0x11EC, about 1,120 bytes | The edge chose X25519MLKEM768 and answered with its share (32 bytes) and the ML-KEM ciphertext (1,088 bytes) |
| Application Data | Everything after the Server Hello | TLS 1.3 encrypts the rest of the handshake, so the edge's ML-DSA certificate is not visible on the wire |
| Client Hello offering only x25519 | One Key Share, group x25519 | The classical client |
| Alert (Level: Fatal, Description: Handshake Failure) | Sent by the edge | `strict` refused a client with no post-quantum key exchange; the edge logs the reason |

Wireshark 4.2 does not have names for most post-quantum code points, so it shows them as numbers ("Unknown (4588)" is 0x11EC), and it labels MLKEM1024 (0x0202) with an old experimental name, "frodo976aes". Newer Wireshark releases may print the right names. Go by the numbers:

| Number | Name |
|---|---|
| 0x11EC (4588) | X25519MLKEM768 |
| 0x11ED (4589) | SecP384r1MLKEM1024 |
| 0x11EB (4587) | SecP256r1MLKEM768 |
| 0x0202 (514) | MLKEM1024 (`cnsa2`; Wireshark 4.2 shows "frodo976aes") |
| 0x0904, 0x0905, 0x0906 | ML-DSA-44, ML-DSA-65, ML-DSA-87 signature schemes |

**4. Filters that pick out each part.** Type these into Wireshark's display filter bar (or `tshark -r edge.pcapng -Y "..."`):

| Filter | Shows |
|---|---|
| `tls.handshake.extensions_key_share_group == 0x11ec` | hellos that carry an X25519MLKEM768 key share |
| `tls.handshake.type == 2 && tls.handshake.extensions_key_share_group == 0x11ec` | server hellos where the edge chose it |
| `tls.handshake.sig_hash_alg == 0x0905` | clients that offer ML-DSA-65 signatures |
| `tls.alert_message.desc == 40` | handshake failures: clients the policy refused |
| `tls.handshake.extensions_server_name == "web.example.com"` | connections for one name, on a port several routes share |

What Wireshark cannot show you: the certificate, the HTTP inside, or the keys. The edge has no option to write session keys to a file for decryption, on purpose, so a capture taken anywhere on the network shows only what is above. To see the certificate the edge serves, use `acxelin-qguard connect`, which prints its subject, key algorithm, serial and expiry, and what the edge staples about it.

## 12. When something goes wrong

| You see | What it means | What to do |
|---|---|---|
| `this machine's OpenSSL ... is too old` | Post-quantum TLS needs OpenSSL 3.5 or newer. | Install it (section 2), or use the Docker image. If OpenSSL 3.5 is in a folder of its own, point `ACXELIN_OPENSSL` (Windows, macOS) or `LD_LIBRARY_PATH` (Linux) at it. |
| `no suitable key share` in the edge's log | The client offers no post-quantum key exchange. | Use a client built on OpenSSL 3.5 or newer, or the `transition` policy while you migrate. |
| `peer did not return a certificate` | Mutual TLS is on, and the client sent no certificate. | Give the client a certificate from your CA, and point it at its `chain.pem` and `key.pem`. |
| `the server closed the connection right after the handshake` | The edge refused the client certificate (missing, untrusted or revoked), or the service behind the edge is down. | Read the edge's log, which says which one. Check that the target is listening. |
| Every client is refused after a week | The CRL has expired, and mutual TLS fails closed. | Run `acxelin-qguard ca maintain --dir pki` now, and schedule it daily. |
| `The CA key is locked` in the console | The console restarted and forgot the passphrase. | Enter the passphrase again. |
| `port 443 is already in use` | Another program, perhaps a second copy of QGuard or a web server, listens on that port. | Stop it, or choose another port. |
| "Your connection is not private" in a browser | The route has no public certificate, or it is `strict`. | For a public website, use `transition` with `fallback_cert` and `fallback_key` (section 6, "Public websites and browsers"). |
| A web app redirects to `http://...` or sees every visitor as `127.0.0.1` | The route does not pass forwarded headers. | Set `forwarded_headers = true` (section 6, "Web apps behind QGuard"). |
| `... does not trust this server's certificate` in the edge's log | A client (often a browser) refused the certificate. It is counted as `client_distrusts_certificate`, apart from clients the edge refuses. | Give the client the CA certificate, or, for browsers, a public certificate. |
| `the certificate ... expired` when the edge starts | The certificate it serves has expired; every client refuses it. | Renew it (console: QCertificate, Renew; or `ca renew`). |
| `doctor` exits 2 | A check failed. | The line marked `FAIL` names the problem and the fix. |

### Exit codes

`doctor` exits 0 when everything passes, 1 on warnings with `--strict`, 2 when a check fails, and 3 when this machine cannot run Acxelin QGuard. Other commands exit 1 with one line on stderr when they fail.

## 13. Questions

**Is QGuard a product, a service or a package?** A product: software you install and run yourself, delivered as a package (one offline installer folder, or an image you build). It is not a service: nothing runs at Acxelin Quantum, and your keys and traffic never leave your machines.

**Do browsers work?** Yes, with the `transition` policy and an ordinary public certificate as `fallback_cert`: the key exchange is quantum-safe, the certificate classical. Browsers do not verify ML-DSA certificates yet (section 6, "Public websites and browsers"). Use `strict` for your own clients and services.

**Do I have to change my application?** No. The edge sits in front of it, and the application keeps speaking plain TCP on a local port.

**How fast does a revocation take effect?** At the next connection on an edge that reads the CRL file directly. Within `crl_every` seconds (60 by default) on an edge that fetches it with `crl_url`.

**Does it contact the internet?** Only the addresses you configure: targets, remote edges and a `crl_url`. It never contacts Acxelin Quantum.

**Does it need any other Acxelin product?** No. It installs and runs on its own, from its own release folder.

## 14. Limits

- Browsers cannot verify ML-DSA certificates yet (see Questions).
- QGuard does not serve HTTP/2; browsers use HTTP/1.1 through it.
- No PFX (PKCS#12) export: no tool can write an ML-DSA key into one yet, and Windows TLS cannot use ML-DSA certificates. Downloads are PEM.
- Browsers cannot present ML-DSA client certificates, so a partner API with client certificates is for programs (curl, OpenSSL 3.5, your partner's code), not browsers.
- ACME clients take ML-DSA certificates only through a request made beforehand (`certbot --csr`), and certbot does not renew those by itself: schedule the same command.
- Forwarded headers cover HTTP/1.x; other protocols pass through unchanged.
- A revoked client keeps access until its edge has the new CRL.
- KMS and HSM signing are implemented, but they have not been tested against real HSMs or cloud accounts here.
