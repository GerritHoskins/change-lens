#!/bin/sh
# Host monitor (I-8 S7 §3.8), run by root's cron every 10 minutes (README step D3). Checks the public endpoints,
# the containers, the backup job's last successes, the disk, and the global spend cap event. Mails ALERT_TO
# through IONOS SMTP when something is wrong: again when the problem list changes, otherwise every 6 hours.
# It can't see the server being down: keep an outside uptime check too (README step D3).
set -u
. /etc/changelens/monitor.env
cd "$(dirname "$0")"
STATE_DIR=/var/lib/changelens-monitor
mkdir -p "$STATE_DIR"
problems=""
add() { problems="${problems}- $1
"; }

code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://api.pixeltronic.dev/projects)
[ "$code" = "401" ] || add "api: GET /projects without a token returned $code, expected 401"
code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 https://auth.pixeltronic.dev/oidc/.well-known/openid-configuration)
[ "$code" = "200" ] || add "logto: OpenID configuration returned $code, expected 200"

for svc in caddy postgres logto api worker retention egress backup; do
  state=$(docker compose ps --format '{{.State}} {{.Health}}' "$svc" 2>/dev/null)
  case "$state" in
    "running healthy"|"running ") ;;
    *) add "container $svc: ${state:-missing}" ;;
  esac
done

now=$(date +%s)
check_mark() {  # name, max age in seconds
  ts=$(docker compose exec -T backup cat "/work/state/$1" 2>/dev/null || echo 0)
  [ $((now - ${ts:-0})) -le "$2" ] || add "backup: $1 older than $(($2 / 3600)) h"
}
check_mark last-wal-ok 1800
check_mark last-base-ok 93600
check_mark last-audit-prune-ok 93600
# Postgres itself must be archiving: a failed archive_command leaves the WAL directory empty but "ok".
failing=$(docker compose exec -T postgres psql -U postgres -tAX -c "select coalesce(last_failed_time > coalesce(last_archived_time, 'epoch'), false) from pg_stat_archiver" 2>/dev/null)
[ "$failing" = "f" ] || add "postgres: WAL archiving is failing (pg_stat_archiver)"

disk=$(df --output=pcent / | tail -n 1 | tr -dc 0-9)
[ "$disk" -lt 80 ] || add "disk: / is ${disk}% full"

if docker compose logs --since 11m api worker 2>/dev/null | grep -q global_spend_cap_reached; then
  add "spend: the global monthly spend cap was reached; new comparisons are stopped until next month or a higher cap"
fi

last="$STATE_DIR/last"
if [ -z "$problems" ]; then
  rm -f "$last"
  exit 0
fi
digest=$(printf '%s' "$problems" | sha256sum | cut -c1-16)
if [ -f "$last" ] && [ "$(cut -d' ' -f1 "$last")" = "$digest" ] && [ $((now - $(cut -d' ' -f2 "$last"))) -lt 21600 ]; then
  exit 0
fi
printf 'From: %s\nTo: %s\nSubject: ChangeLens alert\n\n%s' "$SMTP_USER" "$ALERT_TO" "$problems" \
  | curl -s --ssl-reqd --url "$SMTP_URL" --user "$SMTP_USER:$SMTP_PASS" \
         --mail-from "$SMTP_USER" --mail-rcpt "$ALERT_TO" -T - \
  && echo "$digest $now" > "$last"
