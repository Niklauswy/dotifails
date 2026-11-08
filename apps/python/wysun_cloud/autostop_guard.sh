#!/bin/sh
# wysun-autostop: powers this VM off by the rules Wysun Cloud wrote.
#
# Installed by Wysun Cloud as /usr/local/libexec/wysun-autostop and run every minute by
# wysun-autostop.timer (as root). Rules live in /etc/wysun-autostop.conf (KEY=VALUE, written
# and validated by Wysun Cloud); what it saw last lives in /var/lib/wysun-autostop/state, which
# the Wysun Cloud probe reads every second to show the countdown.
#
# Rules (any combination; the soonest wins):
#   SCHEDULE_AT=HH:MM SCHEDULE_DAYS=1..7 (date +%u) SCHEDULE_TZ=Area/City
#       power off at that time on those days. Only times after SCHEDULE_FROM (when the rule
#       was saved) and after boot count, so starting the VM after the time never stops it.
#   MAX_HOURS=N         power off N hours after boot (or after MAX_FROM, when later).
#   IDLE_MINUTES=N      power off after N minutes in which every check was quiet: CPU below
#                       IDLE_CPU %, no interactive login when IDLE_SSH=1 (Wysun Cloud's own
#                       probe has no terminal, so it never counts), and none of IDLE_PROCS
#                       running (exact process names, e.g. "claude codex").
# A positive epoch in /var/lib/wysun-autostop/postpone delays any power-off until then.
# WARN_MINUTES before powering off, logged-in users get one wall message.
#
# Test hooks (never set in production): WYSUN_AUTOSTOP_CONF, WYSUN_AUTOSTOP_DIR,
# WYSUN_AUTOSTOP_STAT, WYSUN_AUTOSTOP_NOW, WYSUN_AUTOSTOP_UPTIME, WYSUN_AUTOSTOP_SESSIONS,
# WYSUN_AUTOSTOP_RUNNING (space-separated names that count as running) and
# WYSUN_AUTOSTOP_DRY (print "poweroff <reason>" / "warn <epoch>" instead of acting).
set -u

CONF=${WYSUN_AUTOSTOP_CONF:-/etc/wysun-autostop.conf}
DIR=${WYSUN_AUTOSTOP_DIR:-/var/lib/wysun-autostop}
STAT=${WYSUN_AUTOSTOP_STAT:-/proc/stat}

SCHEDULE_AT=
SCHEDULE_DAYS=1234567
SCHEDULE_TZ=UTC
SCHEDULE_FROM=0
MAX_HOURS=0
MAX_FROM=0
IDLE_MINUTES=0
IDLE_CPU=10
IDLE_SSH=1
IDLE_PROCS=
WARN_MINUTES=5
# shellcheck disable=SC1090
[ -r "$CONF" ] && . "$CONF"

mkdir -p "$DIR" 2>/dev/null

number() {          # $1 when it is a plain non-negative integer, else 0
    case "${1:-}" in
        ''|*[!0-9]*) echo 0 ;;
        *) echo "$1" ;;
    esac
}

field() {           # field KEY: its value in the previous state file
    awk -F= -v k="$1" '$1 == k {print substr($0, length(k) + 2); exit}' "$DIR/state" 2>/dev/null
}

now=$(number "${WYSUN_AUTOSTOP_NOW:-$(date +%s)}")
uptime_s=$(number "${WYSUN_AUTOSTOP_UPTIME:-$(cut -d. -f1 /proc/uptime)}")
boot=$((now - uptime_s))

prev_total=$(number "$(field CPU_TOTAL)")
prev_idle=$(number "$(field CPU_IDLE)")
prev_checked=$(number "$(field CHECKED)")
idle_since=$(number "$(field IDLE_SINCE)")
warned=$(number "$(field WARNED)")

# CPU busy share since the previous check (all cores together). Unknown counts as busy.
set -- $(awk '/^cpu / {t = 0; for (i = 2; i <= 9; i++) t += $i; print t, $5 + $6; exit}' "$STAT" 2>/dev/null)
total=$(number "${1:-0}")
idle=$(number "${2:-0}")
cpu=100
if [ "$prev_total" -gt 0 ] && [ "$total" -gt "$prev_total" ]; then
    delta=$((total - prev_total))
    cpu=$(( (delta - (idle - prev_idle)) * 100 / delta ))
    [ "$cpu" -lt 0 ] && cpu=0
fi

sessions=$(number "${WYSUN_AUTOSTOP_SESSIONS:-$(who 2>/dev/null | wc -l)}")

running=
for name in $IDLE_PROCS; do
    if [ -n "${WYSUN_AUTOSTOP_RUNNING+x}" ]; then
        case " $WYSUN_AUTOSTOP_RUNNING " in *" $name "*) running=$name; break ;; esac
    elif pgrep -x "$name" >/dev/null 2>&1; then
        running=$name
        break
    fi
done

busy=
IDLE_MINUTES=$(number "$IDLE_MINUTES")
if [ "$IDLE_MINUTES" -gt 0 ]; then
    if [ "$cpu" -ge "$(number "$IDLE_CPU")" ]; then
        busy=cpu
    elif [ "$IDLE_SSH" = 1 ] && [ "$sessions" -gt 0 ]; then
        busy=ssh
    elif [ -n "$running" ]; then
        busy="proc:$running"
    fi
    if [ -n "$busy" ]; then
        idle_since=0
    elif [ "$idle_since" -eq 0 ]; then
        # The whole window since the previous check was quiet.
        idle_since=$now
        [ "$prev_checked" -gt 0 ] && [ "$prev_checked" -lt "$now" ] && idle_since=$prev_checked
    fi
else
    idle_since=0
fi

# The first scheduled time strictly after $1, in SCHEDULE_TZ, on an allowed day (or 0).
next_schedule() {
    # Step from noon one day at a time: a daylight-saving hour can never change the date.
    base=$(TZ="$SCHEDULE_TZ" date -d "@$1" +%F 2>/dev/null) || { echo 0; return; }
    noon=$(TZ="$SCHEDULE_TZ" date -d "$base 12:00" +%s 2>/dev/null) || { echo 0; return; }
    i=0
    while [ "$i" -le 8 ]; do
        day=$(TZ="$SCHEDULE_TZ" date -d "@$((noon + i * 86400))" +%F 2>/dev/null) || break
        dow=$(TZ="$SCHEDULE_TZ" date -d "$day 12:00" +%u 2>/dev/null) || break
        case "$SCHEDULE_DAYS" in
            *"$dow"*)
                # A time that does not exist that night (daylight saving) skips the day.
                at=$(TZ="$SCHEDULE_TZ" date -d "$day $SCHEDULE_AT" +%s 2>/dev/null) || at=0
                if [ "$at" -gt "$1" ]; then
                    echo "$at"
                    return
                fi
                ;;
        esac
        i=$((i + 1))
    done
    echo 0
}

next=0
reason=
consider() {
    if [ "$1" -gt 0 ] && { [ "$next" -eq 0 ] || [ "$1" -lt "$next" ]; }; then
        next=$1
        reason=$2
    fi
}

if [ -n "$SCHEDULE_AT" ] && [ -n "$SCHEDULE_DAYS" ]; then
    ref=$boot
    from=$(number "$SCHEDULE_FROM")
    [ "$from" -gt "$ref" ] && ref=$from
    consider "$(next_schedule "$ref")" schedule
fi
MAX_HOURS=$(number "$MAX_HOURS")
if [ "$MAX_HOURS" -gt 0 ]; then
    ref=$boot
    from=$(number "$MAX_FROM")
    [ "$from" -gt "$ref" ] && ref=$from
    consider $((ref + MAX_HOURS * 3600)) max
fi
if [ "$IDLE_MINUTES" -gt 0 ] && [ "$idle_since" -gt 0 ]; then
    consider $((idle_since + IDLE_MINUTES * 60)) idle
fi

postpone=$(number "$(cat "$DIR/postpone" 2>/dev/null)")
if [ "$next" -gt 0 ] && [ "$postpone" -gt "$next" ]; then
    next=$postpone
fi

write_state() {
    {
        echo "CHECKED=$now"
        echo "NEXT_AT=$next"
        echo "NEXT_REASON=$reason"
        echo "IDLE_SINCE=$idle_since"
        echo "BUSY=$busy"
        echo "CPU=$cpu"
        echo "SESSIONS=$sessions"
        echo "CPU_TOTAL=$total"
        echo "CPU_IDLE=$idle"
        echo "WARNED=$warned"
    } > "$DIR/state.tmp" && chmod 0644 "$DIR/state.tmp" && mv -f "$DIR/state.tmp" "$DIR/state"
}

if [ "$next" -gt 0 ] && [ "$now" -ge "$next" ]; then
    write_state
    if [ -n "${WYSUN_AUTOSTOP_DRY:-}" ]; then
        echo "poweroff $reason"
        exit 0
    fi
    logger -t wysun-autostop "apagado automático: $reason" 2>/dev/null
    systemctl poweroff
    exit 0
fi

if [ "$next" -gt 0 ] && [ "$warned" -ne "$next" ] \
        && [ $((next - now)) -le $(( $(number "$WARN_MINUTES") * 60 )) ]; then
    warned=$next
    if [ -n "${WYSUN_AUTOSTOP_DRY:-}" ]; then
        echo "warn $next"
    else
        clock=$(TZ="$SCHEDULE_TZ" date -d "@$next" +%H:%M 2>/dev/null)
        wall "Wysun Cloud: esta VM se apagará a las $clock. Para evitarlo, pospón el apagado en Wysun Cloud." 2>/dev/null
    fi
fi

write_state
exit 0
