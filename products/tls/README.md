# Acxelin QGuard

Software you install in front of your websites, APIs and databases, so every connection to them is protected against future quantum computers. Your own certificate authority, QCertificate, is built in. The services behind it do not change.

**What it is:** a product you install and run yourself, delivered as one offline installer folder. It is not a cloud service: it runs on your machines, holds your keys, and never contacts Acxelin Quantum.

It gives one command, `acxelin-qguard`, and three parts:

- **The guard** (called the `edge` in commands and settings) sits in front of a service and lets in only quantum-safe connections (key exchange X25519MLKEM768, SecP384r1MLKEM1024 or SecP256r1MLKEM768; ML-DSA certificates). The service keeps running as it is.
- **QCertificate**, the certificate authority, issues, renews and revokes the quantum-safe certificates, and lets devices enrol themselves (EST, RFC 7030; ACME, RFC 8555).
- **The console** is a local web page for the everyday work: protect a service, see what it sees, turn on enforcement, run QCertificate, and check any connection.

## Install

You need Python 3.11 to 3.14 and OpenSSL 3.5 or newer. Debian 13 and macOS with `brew install openssl@3` have it; on Windows, run `choco install openssl -y`. QGuard installs for your user only, without internet access, on Linux (x86-64, ARM), Windows (x64) and Apple-silicon Macs:

1. Download `acxelin-qguard-1.3.0-wheelhouse.tar.gz` and `SHA256SUMS` from the [release page](https://github.com/AcxelinQuantum/PQC/releases/tag/qguard-v1.3.0).
2. Check the download: `sha256sum -c SHA256SUMS --ignore-missing` should print `OK` (on Windows, compare `Get-FileHash` with the file; the manual shows how).
3. Unpack it, `tar xzf acxelin-qguard-1.3.0-wheelhouse.tar.gz`, and open a terminal in the folder.
4. Install: `sh install.sh`. On Windows: `Unblock-File .\install.ps1`, then `powershell -ExecutionPolicy RemoteSigned -File .\install.ps1`.

The installer checks your Python and OpenSSL, puts `acxelin-qguard` on your PATH and runs `acxelin-qguard doctor`. `sh install.sh --uninstall` (or `-Uninstall`) removes it.

## Use it

```
acxelin-qguard console
```

Your browser opens, signed in. The first time, it walks you through two steps: create QCertificate, then protect your first service. Choose what kind of service it is (a public website, an internal app or API, a partner API, or a database), type the address people use and where the service runs now, and start QGuard. Then **Check connection** shows that the connection is quantum-safe.

`acxelin-qguard try` shows the whole idea in one minute, with nothing to set up.

## Public websites

Browsers already use a quantum-safe key exchange, but they only trust certificates from public authorities, and those do not issue quantum-safe certificates yet. Give a public website its ordinary public certificate (such as Let's Encrypt) as well: browsers then connect normally, with a quantum-safe key exchange, the same way Google, Cloudflare and GitHub do today. Without one, visitors see "Your connection is not private". The console asks for it, and says so when it is missing.

## Where it runs

On your own servers, in front of each service, the way nginx or a load balancer would: as a system service on Linux (systemd), as a scheduled task on Windows, or in a container you build. The manual's "Running it in production" section has the steps. The console keeps editing the same settings file the service reads, and the service applies every change within seconds.

## The command line

Everything the console does also works from the command line, for scripts, servers without a browser, and the rare tasks the console leaves out:

| Task | Command |
|---|---|
| Check any connection, such as a public site | `acxelin-qguard connect www.example.com:443 --policy transition` |
| Run QGuard from a settings file | `acxelin-qguard edge --config edge.toml` |
| Check this machine, a CA folder or a settings file | `acxelin-qguard doctor --ca pki --config edge.toml` |
| Renew what expires soon and refresh the revocation list | `acxelin-qguard ca maintain --dir pki` (daily) |
| Enrolment services | `ca serve` (EST), `ca acme` (ACME), `ca publish` (the CA certificate and revocation list over HTTP) |
| Intermediate CAs, keys in an HSM or KMS, company sign-in (OIDC) | `ca init --parent`, `ca init --kms` / `--pkcs11-module`, `ca oidc` |
| nginx, PostgreSQL, pgvector or MQTT behind QGuard, ready to run | `acxelin-qguard bundle nginx --host web.example.com` |
| A signed bundle of the setup, for an audit or a pilot | `acxelin-qguard evidence create` |

The manual (`docs/manual.md`) covers every task, including how to watch the quantum-safe handshake in Wireshark.

## Limits

- Browsers cannot verify quantum-safe (ML-DSA) certificates yet, so a public website uses an ordinary public certificate as well, as above.
- QGuard does not serve HTTP/2. There is no PFX export (no tool can write an ML-DSA key into one yet).
- A revoked partner keeps access until the guard has the new revocation list: at once on the machine that holds the CA, within `crl_every` seconds (60 by default) elsewhere.
- Keys in an HSM or a cloud KMS (`--kms`, `--pkcs11-module`, `--signer-command`) are implemented, but they have not been run against real HSMs or cloud accounts here.

More: `docs/manual.md` and `docs/threat-model.md`.

## Licence

Proprietary: © 2026 Acxelin Quantum, all rights reserved. See `LICENSE`.
