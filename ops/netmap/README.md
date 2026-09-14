# Netmap

Інвентар хостів DevOps Hub. Allowlist CIDR only. `nmap -sn` без root/CVE/pcap.

Live: https://s.ks.tv/netmap/

```
# /opt/ops/netmap/.env
DATABASE_URL=postgres://ops:ops-change-me@ops_postgres:5432/platform
NETMAP_CIDRS=10.0.0.0/24
NETMAP_MAX_HOSTS=256
```

Сканувати можна лише CIDR з довідника. Більше /24 за замовчуванням — відмова.
