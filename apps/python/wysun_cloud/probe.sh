#!/bin/sh
# Wysun Cloud probe: one metrics line per sample on stdout, forever.
#
# It is fed to `sh -s` over SSH, so nothing is installed on the VM. The caller
# sets the interval by prefixing the script with `INTERVAL=<seconds>` (the
# remote environment cannot be set any other way).
#
# Line format (rates are computed on the client from two consecutive lines):
#   S <uptime seconds> cpu=<user nice system idle iowait irq softirq steal>
#     cores=<total,idle;total,idle;…> load=<1 5 15>
#     mem=<MemTotal MemAvailable Cached SwapTotal SwapFree kB>
#     net=<rx_bytes tx_bytes> disk=<read_sectors write_sectors>
#     df=<mount:used_kB:size_kB,…> up=<seconds>
#     auto=<installed next_at reason idle_since busy once_at>
#     top=<pid:pcpu:rss_kB:comm|…>
#
# `auto` is the automatic power-off (wysun_cloud/autostop.py): whether the guard is
# installed, what its last check decided (epochs, `-` for empty) and the one-off
# `shutdown -h +N`, if any. It only reads small world-readable files.
#
# The stamp is /proc/uptime (monotonic, with hundredths): only deltas between two
# lines are used, so it never needs to be wall-clock time. A failing write is
# what ends the loop when the parent ssh dies (stdout becomes a broken pipe);
# a failing reader (missing file, odd distro) only empties its field.
set -u

INTERVAL=${INTERVAL:-1}

# /proc/stat: the aggregate line and every per-core line (total,idle+iowait), the
# same idle definition the client uses for the aggregate.
cpu_line() {
    awk '/^cpu / {
             printf "%d %d %d %d %d %d %d %d\n", $2+0, $3+0, $4+0, $5+0, $6+0, $7+0, $8+0, $9+0
             exit
         }' /proc/stat
}

cores_line() {
    awk '/^cpu[0-9]+ / {
             total = 0
             for (i = 2; i <= 9; i++) total += $i + 0
             n++
             if (n > 1) printf ";"
             printf "%d,%d", total, $5 + $6
         }
         END { if (n) printf "\n" }' /proc/stat
}

mem_line() {
    awk '/^MemTotal:/ {t = $2}
         /^MemAvailable:/ {a = $2}
         /^Cached:/ {c = $2}
         /^SwapTotal:/ {st = $2}
         /^SwapFree:/ {sf = $2}
         END {printf "%d %d %d %d %d\n", t + 0, a + 0, c + 0, st + 0, sf + 0}' /proc/meminfo
}

# rx_bytes and tx_bytes summed over every interface except loopback.
net_line() {
    # Split at the colon: long names (docker0, enp0s31f6) have no leading padding.
    awk 'NR > 2 {
             i = index($0, ":")
             if (i == 0) next
             name = substr($0, 1, i - 1)
             gsub(/[ \t]/, "", name)
             if (name == "lo") next
             n = split(substr($0, i + 1), f, " ")
             if (n >= 9) { rx += f[1]; tx += f[9] }
         }
         END {printf "%d %d\n", rx + 0, tx + 0}' /proc/net/dev
}

# Sectors read/written over whole block devices (partitions excluded).
disk_line() {
    ls /sys/block 2>/dev/null | awk '
        FILENAME == "-" {device[$0] = 1; next}
        ($3 in device) {read_sectors += $6; write_sectors += $10}
        END {printf "%d %d\n", read_sectors + 0, write_sectors + 0}' - /proc/diskstats
}

# Real filesystems only; the UI prefers the "/" mount anyway.
df_line() {
    df -P -k 2>/dev/null | awk '
        NR > 1 && $1 !~ /^(tmpfs|devtmpfs|overlay|squashfs|proc|sysfs|cgroup2?|devpts|efivarfs|ramfs|mqueue|hugetlbfs|pstore|securityfs|debugfs|tracefs|configfs|fusectl|autofs|binfmt_misc)$/ {
            printf "%s%s:%d:%d", sep, $6, $3, $2
            sep = ","
        }'
}

auto_line() {
    installed=0
    [ -r /etc/wysun-autostop.conf ] && installed=1
    cat /var/lib/wysun-autostop/state /run/systemd/shutdown/scheduled 2>/dev/null | awk -F= -v installed="$installed" '
        {v[$1] = substr($0, length($1) + 2)}
        END {
            once = 0
            if (("USEC" in v) && (!("MODE" in v) || v["MODE"] == "poweroff" || v["MODE"] == "halt"))
                once = sprintf("%d", v["USEC"] / 1000000)
            n = ("NEXT_AT" in v && v["NEXT_AT"] != "") ? v["NEXT_AT"] : 0
            r = ("NEXT_REASON" in v && v["NEXT_REASON"] != "") ? v["NEXT_REASON"] : "-"
            i = ("IDLE_SINCE" in v && v["IDLE_SINCE"] != "") ? v["IDLE_SINCE"] : 0
            b = ("BUSY" in v && v["BUSY"] != "") ? v["BUSY"] : "-"
            printf "%s %s %s %s %s %s\n", installed, n, r, i, b, once
        }'
}

up_line() {
    cut -d. -f1 /proc/uptime
}

top_line() {
    ps -eo pid=,pcpu=,rss=,comm= --sort=-pcpu 2>/dev/null | head -8 | awk '
        {
            pid = $1; cpu = $2; rss = $3
            $1 = ""; $2 = ""; $3 = ""
            comm = $0
            sub(/^ +/, "", comm)
            printf "%s%s:%s:%s:%s", sep, pid, cpu, rss, comm
            sep = "|"
        }'
}

while :; do
    cpu=$(cpu_line)
    cores=$(cores_line)
    load1=0 load5=0 load15=0
    read -r load1 load5 load15 _rest < /proc/loadavg || :
    mem=$(mem_line)
    net=$(net_line)
    disk=$(disk_line)
    df=$(df_line)
    up=$(up_line)
    auto=$(auto_line)
    top=$(top_line)
    read -r stamp _idle < /proc/uptime

    # A broken stdout pipe makes this write fail: the probe ends with its ssh.
    printf 'S %s cpu=%s cores=%s load=%s mem=%s net=%s disk=%s df=%s up=%s auto=%s top=%s\n' \
        "$stamp" "$cpu" "$cores" "$load1 $load5 $load15" "$mem" "$net" \
        "$disk" "$df" "$up" "$auto" "$top" || exit 0
    sleep "$INTERVAL" || exit 0
done
