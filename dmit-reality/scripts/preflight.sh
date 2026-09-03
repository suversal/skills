#!/usr/bin/env bash
# Read-only, Linux/systemd baseline. Does not fetch private resources.
set -u
if [ "$(uname -s)" != Linux ]; then
  printf 'preflight=refused reason=requires_linux\n' >&2
  exit 2
fi
printf '[identity]\n'
hostname
uname -m
awk -F= '$1 == "PRETTY_NAME" {print}' /etc/os-release
printf '[resources]\n'
free -h
swapon --show
df -hT /
printf '[time]\n'
timedatectl show -p NTPSynchronized -p Timezone
printf '[listeners]\n'
ss -lntup
printf '[ssh_effective]\n'
if [ "$(id -u)" = 0 ]; then
  /usr/sbin/sshd -T 2>/dev/null | awk '$1 ~ /^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|maxauthtries)$/ {print}'
else
  printf 'ssh_effective=not_checked needs_root\n'
fi
printf '[firewall]\n'
if command -v ufw >/dev/null 2>&1; then ufw status verbose; fi
if command -v nft >/dev/null 2>&1; then nft list ruleset; fi
printf '[services]\n'
for service in ssh x-ui cloudflared fail2ban unattended-upgrades; do
  printf '%s=' "$service"
  systemctl is-active "$service" 2>/dev/null || true
done
systemctl --failed --no-legend || true
if command -v cloud-init >/dev/null 2>&1; then cloud-init status; fi
printf '[congestion]\n'
sysctl net.ipv4.tcp_congestion_control net.core.default_qdisc 2>/dev/null || true
printf '[route]\n'
ip route show
ip -6 route show
printf 'preflight=collected inspect_missing_or_failed_checks\n'
