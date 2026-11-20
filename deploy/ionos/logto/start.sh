#!/bin/sh
# Starts Logto with its output passing through log-filter.awk (compose.yaml, LR-12).
# The shell stays the container's first process: it hands a stop signal on to Logto, and it ends only after
# the filter has written Logto's last lines, so the message of a crash is not lost. If the filter cannot run,
# Logto's first write fails and the container stops: Logto never runs unfiltered.
set -eu
here=$(dirname "$0")

npm run cli db seed -- --swe

pipe=/tmp/logto-output
rm -f "$pipe"
mkfifo -m 600 "$pipe"
awk -f "$here/log-filter.awk" < "$pipe" &
filter=$!
npm start > "$pipe" 2>&1 &
logto=$!
trap 'kill -TERM "$logto" 2>/dev/null' TERM INT

code=0
wait "$logto" || code=$?
# A signal ends the first wait early; the second one collects Logto's own exit code.
if kill -0 "$logto" 2>/dev/null; then
    code=0
    wait "$logto" || code=$?
fi
wait "$filter" || true
exit "$code"
