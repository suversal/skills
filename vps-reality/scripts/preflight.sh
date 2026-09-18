#!/usr/bin/env bash
# Read-only Linux inventory. It does not inspect the provider control plane.
set -u

if [ "$(uname -s)" != Linux ]; then
  printf 'preflight=refused reason=requires_linux\n' >&2
  exit 2
fi

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

printf '[platform_profile]\n'
if command -v python3 >/dev/null 2>&1; then
  python3 "$script_dir/platform_profile.py" || true
else
  printf 'profile_status=not_checked reason=python3_missing\n'
fi

printf '[identity]\n'
printf 'hostname=%s\n' "$(hostname 2>/dev/null || printf unknown)"
printf 'kernel=%s\n' "$(uname -r)"
printf 'architecture=%s\n' "$(uname -m)"
if command -v systemd-detect-virt >/dev/null 2>&1; then
  printf 'virtualization=%s\n' "$(systemd-detect-virt 2>/dev/null || printf none)"
fi
if command -v cloud-id >/dev/null 2>&1; then
  printf 'cloud_id=%s\n' "$(cloud-id 2>/dev/null || printf unknown)"
else
  printf 'cloud_id=not_detected verify_in_provider_console\n'
fi

printf '[resources]\n'
free -h 2>/dev/null || true
swapon --show 2>/dev/null || true
df -hT / 2>/dev/null || true

printf '[time]\n'
timedatectl show -p NTPSynchronized -p Timezone 2>/dev/null || printf 'time_status=not_checked\n'

printf '[addresses_routes]\n'
ip -brief address show 2>/dev/null || true
ip route show 2>/dev/null || true
ip -6 route show 2>/dev/null || true
printf 'public_address=not_inferred verify_provider_assignment_and_external_view\n'

printf '[listeners]\n'
ss -lntup 2>/dev/null || true
if ss -lnt 2>/dev/null | awk 'NR > 1 {split($4,a,":"); if (a[length(a)] == "443") found=1} END {exit !found}'; then
  printf 'tcp_443=occupied inspect_owner_before_deploy\n'
else
  printf 'tcp_443=not_observed_local cloud_reachability_not_checked\n'
fi

printf '[ssh_effective]\n'
sshd_bin=$(command -v sshd 2>/dev/null || true)
if [ "$(id -u)" = 0 ] && [ -n "$sshd_bin" ]; then
  "$sshd_bin" -T 2>/dev/null | awk '$1 ~ /^(port|permitrootlogin|passwordauthentication|pubkeyauthentication|kbdinteractiveauthentication|maxauthtries)$/ {print}'
else
  printf 'ssh_effective=not_checked needs_root_or_sshd\n'
fi

printf '[firewall]\n'
if command -v ufw >/dev/null 2>&1; then ufw status verbose 2>/dev/null || true; else printf 'ufw=absent\n'; fi
if command -v firewall-cmd >/dev/null 2>&1; then
  printf 'firewalld_state=%s\n' "$(firewall-cmd --state 2>/dev/null || printf inactive)"
  firewall-cmd --get-active-zones 2>/dev/null || true
else
  printf 'firewalld=absent\n'
fi
if command -v nft >/dev/null 2>&1; then nft list ruleset 2>/dev/null || true; else printf 'nft=absent\n'; fi
if command -v iptables >/dev/null 2>&1; then iptables -S 2>/dev/null || true; else printf 'iptables=absent\n'; fi
if command -v ip6tables >/dev/null 2>&1; then ip6tables -S 2>/dev/null || true; else printf 'ip6tables=absent\n'; fi
printf 'provider_firewall=not_checked inspect_security_group_nsg_acl_or_equivalent\n'

printf '[mandatory_access_controls]\n'
if command -v getenforce >/dev/null 2>&1; then printf 'selinux=%s\n' "$(getenforce 2>/dev/null || printf unknown)"; else printf 'selinux=not_detected\n'; fi
if command -v aa-status >/dev/null 2>&1; then aa-status 2>/dev/null | sed -n '1,8p'; else printf 'apparmor=not_detected\n'; fi

printf '[services]\n'
for service in ssh sshd x-ui cloudflared fail2ban firewalld unattended-upgrades dnf-automatic.timer; do
  printf '%s=' "$service"
  systemctl is-active "$service" 2>/dev/null || true
done
systemctl --failed --no-legend 2>/dev/null || true
if command -v cloud-init >/dev/null 2>&1; then cloud-init status 2>/dev/null || true; fi

printf '[containers]\n'
for runtime in docker podman containerd; do
  if command -v "$runtime" >/dev/null 2>&1; then printf '%s=present inspect_published_ports\n' "$runtime"; else printf '%s=absent\n' "$runtime"; fi
done

printf '[congestion]\n'
sysctl net.ipv4.tcp_congestion_control net.core.default_qdisc 2>/dev/null || true
printf 'preflight=collected mutations=none inspect_missing_failed_and_cloud_checks\n'
