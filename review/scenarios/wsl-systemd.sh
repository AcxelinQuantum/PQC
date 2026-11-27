#!/bin/bash
# As root in WSL Ubuntu: run the QGuard edge as the shipped systemd service, following the manual's one sentence.
set -u
REPO=${REPO:?set REPO to the checkout, e.g. /mnt/c/.../PQC}
WH=${WH:?set WH to the unpacked acxelin-qguard wheelhouse folder}
step() { echo; echo "### $*"; }

step "1. the unit expects /opt/acxelin-tls/bin/acxelin-tls; install.sh installs per user. Try ACXELIN_PREFIX=/opt/acxelin-tls"
grep -n "ACXELIN_PREFIX\|ACXELIN_BIN" "$WH/install.sh" | head -5
(cd "$WH" && ACXELIN_PREFIX=/opt/acxelin-tls ACXELIN_BIN=/opt/acxelin-tls/bin sh install.sh 2>&1 | head -3)
ls -la /opt/acxelin-tls/bin/

step "2. the service user and folders the manual names"
id acxelin 2>/dev/null || useradd --system --home /var/lib/acxelin-tls --shell /usr/sbin/nologin acxelin
mkdir -p /etc/acxelin-tls /var/lib/acxelin-tls

step "3. a CA and a certificate, and the settings file"
cd /etc/acxelin-tls; rm -rf pki web
export ACXELIN_TLS_CA_PASSPHRASE=audit-root-pass
/opt/acxelin-tls/bin/acxelin-qguard ca init --name "WSL Audit Root" --dir /var/lib/acxelin-tls/pki 2>&1 | tail -2
/opt/acxelin-tls/bin/acxelin-qguard ca issue server wsl.audit.test --san localhost --san 127.0.0.1 --dir /var/lib/acxelin-tls/pki --out web 2>&1 | head -1
python3 -m http.server 18580 --bind 127.0.0.1 --directory /etc >/dev/null 2>&1 &
cat > edge.toml <<'EOF'
[metrics]
listen = "127.0.0.1:9580"

[[edge]]
name = "web"
mode = "terminate"
listen = "0.0.0.0:8543"
target = "127.0.0.1:18580"
cert = "/etc/acxelin-tls/web/chain.pem"
key = "/etc/acxelin-tls/web/key.pem"
EOF
chown -R acxelin: /etc/acxelin-tls/web /etc/acxelin-tls/edge.toml
ls -l /etc/acxelin-tls /etc/acxelin-tls/web

step "4. install and start the shipped unit"
cp "$REPO/products/tls/deploy/systemd/acxelin-tls-edge.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now acxelin-tls-edge 2>&1 | tail -2
sleep 3
systemctl is-active acxelin-tls-edge
journalctl -u acxelin-tls-edge --no-pager -n 8 | cut -c1-220

step "5. a post-quantum client through it"
/opt/acxelin-tls/bin/acxelin-qguard connect 127.0.0.1:8543 --ca /var/lib/acxelin-tls/pki/ca.crt --server-name wsl.audit.test --send $'GET / HTTP/1.0\r\n\r\n' 2>&1 | head -6
openssl s_client -connect 127.0.0.1:8543 -servername wsl.audit.test -CAfile /var/lib/acxelin-tls/pki/ca.crt -brief </dev/null 2>&1 | head -6

step "6. systemd-analyze security score for the unit"
systemd-analyze security acxelin-tls-edge 2>/dev/null | tail -1

step "7. the maintenance timer"
cp "$REPO/products/tls/deploy/systemd/acxelin-tls-maintain."* /etc/systemd/system/; echo ACXELIN_TLS_CA_PASSPHRASE=audit-root-pass > /etc/acxelin-tls/ca.env; chmod 600 /etc/acxelin-tls/ca.env; chown -R acxelin: /var/lib/acxelin-tls
grep -E "ExecStart|Environment|ConditionPath" /etc/systemd/system/acxelin-tls-maintain.service
systemctl daemon-reload; systemctl start acxelin-tls-maintain 2>&1 | tail -2; sleep 2
journalctl -u acxelin-tls-maintain --no-pager -n 5 | cut -c1-220

step "cleanup"
systemctl disable --now acxelin-tls-edge acxelin-tls-maintain.timer 2>/dev/null
kill %1 2>/dev/null
echo done
