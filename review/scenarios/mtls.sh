#!/bin/sh
# Partner API (mTLS) on :8446: with and without the client certificate, then poll every second after the revocation signal file appears.
H=host.docker.internal
CL=${1:-partner-c}
c() { curl -sS --cacert /ca/ca.crt --connect-to "static.audit.test:8446:$H:8446" -o /dev/null -w "%{http_code}" "$@" https://static.audit.test:8446/ 2>&1 | tr '\n' ' ' | tail -c 140; }
echo "no client cert: $(c)"
echo "$CL cert: $(c --cert /sc/$CL/chain.pem --key /sc/$CL/key.pem)"
echo "waiting for revocation..."
while [ ! -f /sc/revoked-at ]; do sleep 0.5; done
start=$(cat /sc/revoked-at)
i=0
while [ $i -lt 180 ]; do
  r=$(c --cert /sc/$CL/chain.pem --key /sc/$CL/key.pem)
  now=$(date +%s)
  case "$r" in 200) ;; *) echo "refused $((now - start)) s after revoking: $r"; exit 0;; esac
  i=$((i + 1)); sleep 1
done
echo "still accepted after 180 s"
