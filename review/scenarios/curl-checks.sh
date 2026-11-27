#!/bin/sh
# Run inside curlimages/curl (OpenSSL 3.5) with this folder at /sc and the CA folder at /ca.
H=host.docker.internal
c() { name=$1; port=$2; shift 2; curl -sS --cacert /ca/ca.crt --connect-to "$name:$port:$H:$port" "$@"; }
echo "== 1 strict, verified, negotiated"
c static.audit.test 8443 -v -o /dev/null https://static.audit.test:8443/ 2>&1 | grep -E "SSL connection|ALPN|subject:|issuer:|HTTP/" | head -6
echo "== 2 HTTP/2 asked for"
c static.audit.test 8443 --http2 -o /dev/null -w "http_version=%{http_version}\n" https://static.audit.test:8443/
echo "== 3 download 200 MB"
c static.audit.test 8443 -o /tmp/big -w "code=%{http_code} size=%{size_download} speed=%{speed_download}B/s time=%{time_total}s\n" https://static.audit.test:8443/big.bin
echo "expected $(c static.audit.test 8443 https://static.audit.test:8443/big.sha256)"; echo "got      $(sha256sum /tmp/big | cut -d' ' -f1)"
echo "== 4 upload 200 MB"
head -c 209715200 /dev/urandom > /tmp/up; echo "sent sha $(sha256sum /tmp/up | cut -d' ' -f1)"
c static.audit.test 8443 -X POST --data-binary @/tmp/up -H "Content-Type: application/octet-stream" -w "\ncode=%{http_code} time=%{time_total}s\n" https://static.audit.test:8443/upload
echo "== 5 redirect built by the app"
c static.audit.test 8443 -o /dev/null -w "code=%{http_code} location=%{redirect_url}\n" https://static.audit.test:8443/redirect
echo "== 6 headers the app receives (static backend)"
c static.audit.test 8443 https://static.audit.test:8443/headers; echo
echo "== 7 headers the app receives (echo server, chosen by host name)"
c echo.audit.test 8443 https://echo.audit.test:8443/hello | head -20
echo "== 8 long request (90 s before the answer)"
c static.audit.test 8443 -w "\ncode=%{http_code} time=%{time_total}s\n" "https://static.audit.test:8443/slow?s=90"
echo "== 9 cnsa2: default curl, then ML-KEM-1024"
c static.audit.test 8445 -o /dev/null -w "code=%{http_code}\n" https://static.audit.test:8445/ 2>&1 | tail -1
c static.audit.test 8445 --curves MLKEM1024 -v -o /dev/null https://static.audit.test:8445/ 2>&1 | grep -E "SSL connection|HTTP/" | head -2
echo "== 10 grafana and wordpress through the edge"
c grafana.audit.test 8443 -o /dev/null -w "grafana / code=%{http_code} location=%{redirect_url}\n" https://grafana.audit.test:8443/
c wp.audit.test 8443 -o /dev/null -w "wordpress / code=%{http_code} location=%{redirect_url}\n" https://wp.audit.test:8443/
echo "== 11 unknown host name on the shared port"
c other.audit.test 8443 -k -o /dev/null -w "other.audit.test code=%{http_code}\n" https://other.audit.test:8443/
