# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- Security leaders at regulated enterprises, banks first (a CISO or head of security architecture), deciding which post-quantum vendor to pilot. They see the showcase and the product films, and need to trust the vendor before a meeting.
- The engineers who will install and run it (system, network and platform administrators). They read the release folder's README and manual, and judge the vendor by whether the commands are safe and work the first time.
- Compliance and risk teams who need evidence for auditors (NIST IR 8547, CNSA 2.0, a CycloneDX CBOM).

## Product Purpose

Acxelin Quantum sells post-quantum security products, each standalone, so a customer installs only the one that fits the problem:

- Acxelin QReadiness + CBOM: finds the cryptography an organisation depends on, shows what a quantum computer breaks, ranks what to migrate first, writes a CycloneDX 1.6 CBOM.
- Acxelin QGuard: post-quantum TLS 1.3 and mutual TLS in front of services that do not change, with QCertificate, its own ML-DSA certificate authority.
- Acxelin QVPN: post-quantum site-to-site IPsec and WireGuard remote access with a desktop app.

The website's job: a short showcase that lets a visitor see, within a minute, which product answers their problem and that it really works. Installation and the manual ship in each release folder, not on the site.

## Positioning

- It protects traffic and data against "harvest now, decrypt later" today, with standardised algorithms (ML-KEM, ML-DSA), not research prototypes.
- Everything shown is real: the screenshots are made from the consoles in this repository (`tools/capture_screens.py`), and the website tests fail when one no longer matches its source.
- Honest about limits: every product states what it does not claim (for example browsers cannot verify ML-DSA yet; HSM signing is not yet tested against real hardware).
- Runs on the customer's own machines, offline from a release folder; it never contacts Acxelin Quantum.

## Operating Context

Visitors evaluate it at work, often on a laptop between meetings, sometimes on a phone from a link; installers run it on Linux servers, Windows and macOS. Releases ship as an offline folder (wheels, installers, manual, licence) and as container images on GHCR.

## Capabilities and Constraints

- The site is static HTML built by `tools/build_site.py` from `website/`: a home page and one page per product, deployed to GitHub Pages; no external scripts or trackers.
- Each product's pages name only that product; the home page routes between products.
- Contact route: the company site, acxelinquantum.com.

## Brand Commitments

- Name and logo: Acxelin Quantum (`website/assets/acxelin-quantum.svg`); product names Acxelin QReadiness, Acxelin QGuard (with QCertificate), Acxelin QVPN.
- Amber is the brand colour; Host Grotesk is the display face (both kept by owner decision).
- Voice: plain, precise, honest; short sentences; no hype; British spelling.
- Copyright line: © 2026 Acxelin Quantum, all rights reserved.

## Evidence on Hand

- Real artifacts: console screenshots (`website/assets/screens/*.png`), and the product films scripted in `documents/video-script.md`.
- Standards the products implement: ML-KEM (FIPS 203), ML-DSA (FIPS 204), CycloneDX 1.6, EST (RFC 7030), ACME (RFC 8555), NIST IR 8547 and CNSA 2.0 checks, IKEv2 hybrid key exchange (RFC 9370), post-quantum PPK (RFC 8784).
- No public customers, testimonials, case studies, benchmarks or prices exist: none may be shown or implied.

## Product Principles

1. Show the mechanism working; never describe what could be demonstrated.
2. State limits next to claims.
3. One product per page; no product depends on another.
4. Safe by default for the installer: verifiable releases, nothing that weakens their machine.

## Accessibility & Inclusion

WCAG 2.2 AA; light and dark themes; usable at 390px wide; checked in CI with axe.
