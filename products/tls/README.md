# Acxelin QGuard

Put post-quantum TLS 1.3 and mutual TLS in front of the services you already run, and issue the ML-DSA certificates they need from your own certificate authority.

Acxelin QGuard has three parts:
- **The edge:** a proxy that accepts only post-quantum clients (X25519MLKEM768, SecP384r1MLKEM1024 or SecP256r1MLKEM768 key exchange, ML-DSA certificates) in front of any TCP service, or a tunnel from a plain local client to a remote edge. The service behind it doesn't change.
- **QCertificate, the certificate authority:** issues, renews and revokes ML-DSA certificates, keeps the CRL fresh, and offers enrollment over EST (RFC 7030) and ACME (RFC 8555).
- **The console:** a local web page for the routine work (create the CA; issue, download, renew and revoke certificates; check edges; test a connection, with a client certificate for mutual TLS), so none of it needs the command line. A private key reaches the browser only when you choose Download with key, never for a revoked certificate or an encrypted key, and every action is recorded in an owner-only audit log.

## Install

Python 3.11 to 3.14, and OpenSSL 3.5 or newer (Debian 13 and macOS with `brew install openssl@3` have it; on Windows, `choco install openssl`). It installs for your user only, without internet access, on Linux (x86-64, ARM), Windows (x64) and Apple-silicon Macs:

1. Download `acxelin-qguard-1.3.0-wheelhouse.tar.gz` and `SHA256SUMS` from the [release page](https://github.com/AcxelinQuantum/PQC/releases/tag/qguard-v1.3.0).
2. Check the download: `sha256sum -c SHA256SUMS --ignore-missing` should print `OK` (on macOS and Windows, compare the fingerprint by hand; the manual shows how).
3. Unpack it: `tar xzf acxelin-qguard-1.3.0-wheelhouse.tar.gz`, then `cd acxelin-qguard-1.3.0-wheelhouse`.
4. Install: `sh install.sh`, which puts `acxelin-qguard` on your PATH. On Windows, `Unblock-File .\install.ps1`, then `powershell -ExecutionPolicy RemoteSigned -File .\install.ps1`.

The installer checks your Python, finds OpenSSL 3.5, runs `acxelin-qguard doctor` and says what to do next. `sh install.sh --uninstall` (or `-Uninstall`) removes it.

For a virtual environment of your own: `pip install ./core ./products/tls`.

## See it work

```
acxelin-qguard try
```

A one-minute tour with nothing to set up: a CA, an ordinary web server, the edge in front of it, a post-quantum client that gets through and a classical client that is refused.

## Use

| Task | Command |
|---|---|
| Open the console | `acxelin-qguard console` |
| Create a CA | `acxelin-qguard ca init --name "Example Root CA" --dir pki` |
| Issue a server certificate | `acxelin-qguard ca issue server web.example.com --dir pki --out web` |
| Put the edge in front of a service | `acxelin-qguard edge --listen 0.0.0.0:8443 --target 127.0.0.1:8080 --cert web/chain.pem --key web/key.pem` |
| Require client certificates (mutual TLS) | add `--require-client-cert --ca pki/ca.crt --crl pki/crl.pem` |
| Configure several routes | `acxelin-qguard edge --config edge.toml` (see `config/example.toml`) |
| nginx, PostgreSQL, pgvector or MQTT behind an edge, ready to run | `acxelin-qguard bundle nginx --host web.example.com` |
| Revoke a certificate | `acxelin-qguard ca revoke SERIAL --dir pki` |
| Keep the CA fresh | `acxelin-qguard ca maintain --dir pki` (daily) |
| Check an edge or a CA folder | `acxelin-qguard doctor --config edge.toml --ca pki` |
| See what a running edge reports | `acxelin-qguard status --url http://127.0.0.1:9100` |
| Test a connection | `acxelin-qguard connect host:8443 --ca pki/ca.crt` |
| Staple an OCSP answer to an edge's certificate | `acxelin-qguard ca ocsp --dir pki --cert web/chain.pem --out web/staple.der`, then `ocsp_staple` on the route |
| Let people enrol with their company sign-in (OIDC) | `acxelin-qguard ca oidc --dir pki --issuer ... --audience ...` |

Enrollment services: `ca serve` (EST), `ca acme` (ACME), `ca publish` (the CA certificate and CRL over HTTP).

The manual (`docs/manual.md`) covers every task, including how to watch the post-quantum handshake in Wireshark (section 11).

### Policies

| Policy | Allows |
|---|---|
| `strict` (default) | post-quantum key exchange and ML-DSA certificates only |
| `transition` | also classical clients while you migrate; use it with `fallback_cert` for browsers, which cannot verify ML-DSA yet |
| `cnsa2` | NSA CNSA 2.0: pure ML-KEM-1024, ML-DSA-87 and AES-256 only |

## The console

`acxelin-qguard console` opens your browser already signed in. The first time, create the certificate authority (give its key a passphrase; the console keeps it in memory only, so it asks again after a restart). Then issue, download, renew and revoke certificates, add running edges to see their policy and negotiated key exchanges, test a connection, and read the health checks.

The console listens only on the machine it runs on. For a remote server:

```
ssh -L 8900:127.0.0.1:8900 server
acxelin-qguard console link --port 8900    # run in that SSH session; open the address it prints
```

In Docker, start the console with `--container` and publish its port to loopback only: `docker run -v acxelin-tls:/data -p 127.0.0.1:8900:8900 acxelin-qguard console --container`, then run `docker exec -it NAME acxelin-qguard console link`.

## Deploy

- **Docker:** `docker build -f products/tls/deploy/Dockerfile -t acxelin-qguard .`
- **systemd:** `deploy/systemd/acxelin-tls-edge.service`, and `acxelin-tls-maintain.service` with its timer for the CA.

## Limits

- Browsers cannot verify ML-DSA certificates yet. For them, use the `transition` policy with a classical fallback certificate.
- Revocation reaches an edge through its CRL, within `crl_every` seconds of the CA publishing one. A revoked client keeps access until then.
- Hardware and cloud signing (`--kms`, `--signer-command`) are implemented, but they have not been run against real HSMs or cloud accounts here.

More: `docs/manual.md` and `docs/threat-model.md`.

## Licence

Proprietary: © 2026 Acxelin Quantum, all rights reserved. See `LICENSE`.
