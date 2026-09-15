#!/usr/bin/env python3
"""Netmap — allowlist CIDR inventory + nmap discovery for DevOps Hub."""
import ipaddress, json, os, re, subprocess, threading, time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs
import urllib.request

try:
    import psycopg2
    import psycopg2.extras
except Exception:
    psycopg2 = None

PORT = int(os.getenv("PORT", "8092"))
DSN = os.getenv("DATABASE_URL", "postgres://ops:ops-change-me@ops_postgres:5432/platform")
DEFAULT_CIDRS = os.getenv("NETMAP_CIDRS", "")  # comma-separated, empty = no auto-scan
MAX_HOSTS = int(os.getenv("NETMAP_MAX_HOSTS", "256"))
SCAN_LOCK = threading.Lock()
SCAN_JOB = {"status": "idle", "log": "", "result": None}

def q(sql, args=None, fetch=False, one=False):
    if not psycopg2:
        raise RuntimeError("psycopg2 missing")
    conn = psycopg2.connect(DSN)
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(sql, args or ())
        rows = cur.fetchall() if fetch else None
        conn.commit()
        if one:
            return rows[0] if rows else None
        return rows
    finally:
        conn.close()

SCHEMA = """
CREATE SCHEMA IF NOT EXISTS netmap;
CREATE TABLE IF NOT EXISTS netmap.cidrs (
  id SERIAL PRIMARY KEY,
  cidr TEXT UNIQUE NOT NULL,
  label TEXT NOT NULL DEFAULT '',
  enabled BOOLEAN NOT NULL DEFAULT true
);
CREATE TABLE IF NOT EXISTS netmap.hosts (
  ip INET PRIMARY KEY,
  mac TEXT NOT NULL DEFAULT '',
  hostname TEXT NOT NULL DEFAULT '',
  vendor TEXT NOT NULL DEFAULT '',
  cidr TEXT NOT NULL DEFAULT '',
  ports JSONB NOT NULL DEFAULT '[]',
  last_seen TIMESTAMPTZ NOT NULL DEFAULT now(),
  extra JSONB NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS netmap.scans (
  id SERIAL PRIMARY KEY,
  cidr TEXT NOT NULL,
  started TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished TIMESTAMPTZ,
  hosts_found INT NOT NULL DEFAULT 0,
  log TEXT NOT NULL DEFAULT ''
);
"""

def ensure():
    q(SCHEMA)
    for raw in [c.strip() for c in DEFAULT_CIDRS.split(",") if c.strip()]:
        try:
            net = ipaddress.ip_network(raw, strict=False)
            q("INSERT INTO netmap.cidrs (cidr,label) VALUES (%s,%s) ON CONFLICT (cidr) DO NOTHING",
              (str(net), "env"))
        except Exception as e:
            print("cidr", raw, e, flush=True)

def allowed_cidrs():
    try:
        rows = q("SELECT * FROM netmap.cidrs WHERE enabled ORDER BY id", fetch=True) or []
    except Exception:
        rows = []
    out = []
    for r in rows:
        try:
            out.append(ipaddress.ip_network(r["cidr"], strict=False))
        except Exception:
            pass
    return out, rows

def in_allowlist(ip, nets):
    addr = ipaddress.ip_address(ip)
    return any(addr in n for n in nets)

def parse_nmap(xml):
    hosts = []
    for block in re.findall(r"<host\b.*?</host>", xml, re.S):
        if "state=\"up\"" not in block and "state='up'" not in block:
            continue
        m = re.search(r'<address addr="([^"]+)" addrtype="ipv4"', block)
        if not m:
            continue
        ip = m.group(1)
        mac = ""
        vendor = ""
        mm = re.search(r'<address addr="([^"]+)" addrtype="mac"[^>]*vendor="([^"]*)"', block)
        if mm:
            mac, vendor = mm.group(1), mm.group(2)
        hn = ""
        hm = re.search(r'<hostname name="([^"]+)"', block)
        if hm:
            hn = hm.group(1)
        ports = []
        for pm in re.finditer(r'<port protocol="(\w+)" portid="(\d+)".*?<state state="([^"]+)"', block, re.S):
            if pm.group(3) == "open":
                ports.append({"proto": pm.group(1), "port": int(pm.group(2))})
        hosts.append({"ip": ip, "mac": mac, "hostname": hn, "vendor": vendor, "ports": ports})
    return hosts

def local_ips():
    out = []
    try:
        p = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5)
        out += [x for x in (p.stdout or "").split() if ":" not in x]
    except Exception:
        pass
    try:
        p = subprocess.run(["ip", "-4", "-o", "addr"], capture_output=True, text=True, timeout=5)
        for m in re.finditer(r"inet (\d+\.\d+\.\d+\.\d+)", p.stdout or ""):
            out.append(m.group(1))
    except Exception:
        pass
    return sorted(set(out))

def run_nmap(cidr):
    net = ipaddress.ip_network(cidr, strict=False)
    if net.num_addresses > MAX_HOSTS + 2:
        raise RuntimeError(f"CIDR {cidr} too large (max {MAX_HOSTS} hosts)")
    # Unprivileged container: ICMP/ARP недоступні. Шукаємо TCP connect.
    cmd = [
        "nmap", "-T4", "--max-retries", "1", "--host-timeout", "4s",
        "-sT", "-p", "22,53,80,443,8080,8084,8085,8443,9100",
        "-oX", "-", str(net),
    ]
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=240)
    xml = p.stdout or ""
    note = (p.stderr or "")[-800:]
    if p.returncode not in (0, 1) and not xml:
        raise RuntimeError(note or "nmap failed")
    hosts = parse_nmap(xml)
    # завжди фіксуємо локальні адреси контейнера/хоста в CIDR
    for ip in local_ips():
        try:
            if ipaddress.ip_address(ip) in net and not any(h["ip"] == ip for h in hosts):
                hosts.append({"ip": ip, "mac": "", "hostname": "self", "vendor": "netmap-container", "ports": []})
        except Exception:
            pass
    return hosts, f"cmd={' '.join(cmd)} rc={p.returncode} parsed={len(hosts)} stderr={note}"

def do_scan(cidr=None):
    nets, rows = allowed_cidrs()
    if not nets:
        return {"error": "немає allowlist CIDR — додайте в /api/cidrs"}
    targets = []
    if cidr:
        n = ipaddress.ip_network(cidr, strict=False)
        if not any(n.subnet_of(a) or n == a for a in nets):
            return {"error": "CIDR поза allowlist"}
        targets = [str(n)]
    else:
        targets = [str(a) for a in nets]
    found = 0
    logs = []
    for t in targets:
        q("INSERT INTO netmap.scans (cidr) VALUES (%s)", (t,))
        try:
            hosts, err = run_nmap(t)
            logs.append(f"{t}: {len(hosts)} up {err}")
            for h in hosts:
                if not in_allowlist(h["ip"], nets):
                    continue
                q("""INSERT INTO netmap.hosts (ip,mac,hostname,vendor,cidr,ports,last_seen)
                     VALUES (%s,%s,%s,%s,%s,%s,now())
                     ON CONFLICT (ip) DO UPDATE SET
                       mac=COALESCE(NULLIF(EXCLUDED.mac,''), netmap.hosts.mac),
                       hostname=COALESCE(NULLIF(EXCLUDED.hostname,''), netmap.hosts.hostname),
                       vendor=COALESCE(NULLIF(EXCLUDED.vendor,''), netmap.hosts.vendor),
                       ports=EXCLUDED.ports, last_seen=now(), cidr=EXCLUDED.cidr""",
                  (h["ip"], h["mac"], h["hostname"], h["vendor"], t, json.dumps(h["ports"])))
                found += 1
            q("UPDATE netmap.scans SET finished=now(), hosts_found=%s, log=%s WHERE id=(SELECT max(id) FROM netmap.scans WHERE cidr=%s)",
              (len(hosts), logs[-1], t))
        except Exception as e:
            logs.append(f"{t}: ERR {e}")
    return {"scanned": targets, "hosts": found, "log": "\n".join(logs)}

class H(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args, flush=True)

    def _json(self, code, obj):
        raw = json.dumps(obj, default=str, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode() if n else ""

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        path = u.path
        if path.endswith("/index.html") or path in ("/", "/netmap/", "/netmap"):
            try:
                with open("/app/ui/index.html", "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            except Exception as e:
                return self._json(500, {"error": str(e)})
        if path.endswith("/health"):
            return self._json(200, {"ok": True})
        if path.endswith("/api/cidrs"):
            _, rows = allowed_cidrs()
            return self._json(200, {"cidrs": rows})
        if path.endswith("/api/hosts"):
            rows = q("SELECT * FROM netmap.hosts ORDER BY last_seen DESC", fetch=True) or []
            return self._json(200, {"hosts": rows})
        if path.endswith("/api/graph"):
            rows = q("SELECT host(ip) AS ip, hostname, vendor, cidr FROM netmap.hosts", fetch=True) or []
            nodes = [{"id": r["ip"], "label": r["hostname"] or r["ip"], "group": r["cidr"] or "net"} for r in rows]
            edges = []
            # naive gateway: x.x.x.1 in same /24
            ips = {r["ip"] for r in rows}
            for r in rows:
                parts = r["ip"].split(".")
                if len(parts) == 4:
                    gw = ".".join(parts[:3] + ["1"])
                    if gw in ips and gw != r["ip"]:
                        edges.append({"from": gw, "to": r["ip"]})
            return self._json(200, {"nodes": nodes, "edges": edges})
        if path.endswith("/api/scan/status"):
            return self._json(200, SCAN_JOB)
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            body = json.loads(self._read() or "{}")
        except Exception:
            body = {}
        if path.endswith("/api/cidrs"):
            raw = (body.get("cidr") or "").strip()
            label = (body.get("label") or "").strip()
            try:
                net = ipaddress.ip_network(raw, strict=False)
            except Exception:
                return self._json(400, {"error": "bad CIDR"})
            if net.num_addresses > MAX_HOSTS + 2:
                return self._json(400, {"error": f"CIDR larger than {MAX_HOSTS} hosts"})
            q("INSERT INTO netmap.cidrs (cidr,label) VALUES (%s,%s) ON CONFLICT (cidr) DO UPDATE SET label=EXCLUDED.label, enabled=true",
              (str(net), label))
            _, rows = allowed_cidrs()
            return self._json(200, {"ok": True, "cidrs": rows})
        if path.endswith("/api/scan"):
            if SCAN_JOB.get("status") == "running":
                return self._json(200, SCAN_JOB)
            SCAN_JOB["status"] = "running"
            SCAN_JOB["result"] = None
            cidr = (body.get("cidr") or "").strip() or None
            def _run():
                try:
                    SCAN_JOB["result"] = do_scan(cidr)
                    SCAN_JOB["status"] = "done"
                except Exception as e:
                    SCAN_JOB["result"] = {"error": str(e)}
                    SCAN_JOB["status"] = "error"
            threading.Thread(target=_run, daemon=True).start()
            return self._json(200, {"status": "running"})
        self._json(404, {"error": "not found"})

if __name__ == "__main__":
    ensure()
    print(f"netmap :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
