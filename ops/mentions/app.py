#!/usr/bin/env python3
import os, re, json, hashlib, hmac, time, urllib.parse, urllib.request
from datetime import datetime, timezone, date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    import psycopg2
    import psycopg2.extras
except Exception:
    psycopg2 = None

DSN = os.getenv("DATABASE_URL", "postgres://ops:ops@ops_postgres:5432/platform")
BOT = os.getenv("SLACK_BOT_TOKEN", "")
SIGN = os.getenv("SLACK_SIGNING_SECRET", "")
TEAM_GROUP = os.getenv("SLACK_DEVOPS_GROUP", "devops-team")
PORT = int(os.getenv("PORT", "8091"))

def db():
    if not psycopg2:
        raise RuntimeError("psycopg2 missing")
    return psycopg2.connect(DSN)

def q(sql, args=(), fetch=False, one=False):
    conn = db(); cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cur.execute(sql, args)
    rows = cur.fetchall() if fetch else []
    conn.commit(); cur.close(); conn.close()
    return rows[0] if one and rows else rows

def keywords():
    try:
        rows = q("SELECT word, kind FROM mentions.keywords", fetch=True)
        return [(r["word"], r["kind"]) for r in rows]
    except Exception:
        return []

def extract_kw(text):
    found = []
    low = text.lower()
    for w, k in keywords():
        if w.lower() in low:
            found.append(w)
    return found

def slack_api(method, payload):
    if not BOT:
        return {}
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        f"https://slack.com/api/{method}", data=data,
        headers={"Authorization": f"Bearer {BOT}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode())

def permalink(channel, ts):
    d = slack_api("chat.getPermalink", {"channel": channel, "message_ts": ts})
    return d.get("permalink") or ""

def channel_name(cid):
    d = slack_api("conversations.info", {"channel": cid})
    ch = d.get("channel") or {}
    return ch.get("name") or cid

def user_name(uid):
    d = slack_api("users.info", {"user": uid})
    u = d.get("user") or {}
    p = u.get("profile") or {}
    return p.get("real_name") or u.get("name") or uid

MENTION_RE = re.compile(r"<@([UW][A-Z0-9]+)(?:\|([^>]+))?>")
SUBTEAM_RE = re.compile(r"<!subteam\^([A-Z0-9]+)(?:\|@?([^>]+))?>")

def short_text(t, n=140):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[:n] + "…"

def store_item(**kw):
    q("""INSERT INTO mentions.items
        (slack_ts, channel_id, channel_name, permalink, author_id, author_name,
         mention_type, mentioned_id, mentioned, text_full, text_short, keywords, msg_at, day)
        VALUES (%(slack_ts)s,%(channel_id)s,%(channel_name)s,%(permalink)s,%(author_id)s,%(author_name)s,
                %(mention_type)s,%(mentioned_id)s,%(mentioned)s,%(text_full)s,%(text_short)s,%(keywords)s,%(msg_at)s,%(day)s)
        ON CONFLICT (slack_ts, channel_id, mentioned_id) DO NOTHING""", kw)

def ingest_message(ev):
    text = ev.get("text") or ""
    cid = ev.get("channel") or ""
    ts = ev.get("ts") or ""
    uid = ev.get("user") or ""
    if not text or not ts:
        return 0
    chn = channel_name(cid) if BOT else cid
    auth = user_name(uid) if BOT and uid else uid
    link = permalink(cid, ts) if BOT else ""
    when = datetime.fromtimestamp(float(ts), tz=timezone.utc)
    day = when.date()
    n = 0
    targets = []
    for m in SUBTEAM_RE.finditer(text):
        name = m.group(2) or TEAM_GROUP
        targets.append(("team", m.group(1), name))
    if f"@{TEAM_GROUP}" in text.lower() and not targets:
        targets.append(("team", TEAM_GROUP, TEAM_GROUP))
    for m in MENTION_RE.finditer(text):
        sid = m.group(1)
        nm = m.group(2) or (user_name(sid) if BOT else sid)
        targets.append(("user", sid, nm))
    kws = extract_kw(text)
    for typ, mid, name in targets:
        store_item(
            slack_ts=ts, channel_id=cid, channel_name=chn, permalink=link,
            author_id=uid, author_name=auth, mention_type=typ, mentioned_id=mid,
            mentioned=name, text_full=text, text_short=short_text(text),
            keywords=kws, msg_at=when, day=day,
        )
        n += 1
    return n

def verify_slack(headers, body):
    if not SIGN:
        return True
    ts = headers.get("X-Slack-Request-Timestamp") or headers.get("x-slack-request-timestamp") or ""
    sig = headers.get("X-Slack-Signature") or headers.get("x-slack-signature") or ""
    if abs(time.time() - int(ts or 0)) > 60 * 5:
        return False
    basestr = f"v0:{ts}:{body}".encode()
    digest = "v0=" + hmac.new(SIGN.encode(), basestr, hashlib.sha256).hexdigest()
    return hmac.compare_digest(digest, sig)

class H(BaseHTTPRequestHandler):
    def log_message(self, *a):
        return

    def _json(self, code, obj):
        raw = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def _read(self):
        n = int(self.headers.get("Content-Length") or 0)
        return self.rfile.read(n).decode() if n else ""

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.end_headers()

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        if path in ("/health", "/api/health"):
            return self._json(200, {"ok": True})
        if path in ("/api/mentions", "/mentions/api/mentions"):
            day = (qs.get("day") or [str(date.today())])[0]
            who = (qs.get("who") or [""])[0]
            hist = (qs.get("history") or ["0"])[0] == "1"
            sql = "SELECT * FROM mentions.items WHERE 1=1"
            args = []
            if who:
                sql += " AND (mentioned ILIKE %s OR mentioned_id=%s)"
                args += [f"%{who}%", who]
            if not hist:
                sql += " AND day=%s"; args.append(day)
            else:
                sql += " AND day>=%s::date - 14"; args.append(day)
            sql += " ORDER BY msg_at DESC LIMIT 500"
            try:
                rows = q(sql, args, fetch=True)
            except Exception as e:
                return self._json(500, {"error": str(e)})
            return self._json(200, {"items": rows, "day": day})
        if path in ("/api/people", "/mentions/api/people"):
            day = (qs.get("day") or [str(date.today())])[0]
            try:
                rows = q("""
                  SELECT mentioned, mentioned_id, mention_type,
                         COUNT(*) FILTER (WHERE day=%s) AS today_count,
                         MAX(msg_at) AS last_at,
                         (ARRAY_AGG(permalink ORDER BY msg_at DESC))[1] AS last_link
                  FROM mentions.items
                  GROUP BY mentioned, mentioned_id, mention_type
                  ORDER BY today_count DESC, last_at DESC NULLS LAST
                """, (day,), fetch=True)
            except Exception as e:
                return self._json(500, {"error": str(e)})
            return self._json(200, {"people": rows, "day": day})
        if path in ("/api/keywords", "/mentions/api/keywords"):
            day = (qs.get("day") or [str(date.today())])[0]
            try:
                rows = q("""
                  SELECT unnest(keywords) AS word, COUNT(*) AS n
                  FROM mentions.items WHERE day=%s
                  GROUP BY 1 ORDER BY n DESC, word
                """, (day,), fetch=True)
                catalog = q("SELECT word, kind FROM mentions.keywords ORDER BY kind, word", fetch=True)
            except Exception as e:
                return self._json(500, {"error": str(e)})
            return self._json(200, {"today": rows, "catalog": catalog})
        # static
        rel = path.replace("/mentions/", "/").lstrip("/") or "index.html"
        root = "/app/ui"
        fp = os.path.join(root, rel)
        if not os.path.isfile(fp):
            fp = os.path.join(root, "index.html")
        if os.path.isfile(fp):
            data = open(fp, "rb").read()
            ctype = "text/html" if fp.endswith(".html") else "application/json" if fp.endswith(".json") else "text/css" if fp.endswith(".css") else "application/javascript"
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self._json(404, {"error": "not found"})

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        raw = self._read()
        if path.endswith("/api/slack/events"):
            if not verify_slack(self.headers, raw):
                return self._json(401, {"error": "bad slack signature"})
            try:
                body = json.loads(raw or "{}")
            except Exception:
                return self._json(400, {"error": "bad json"})
            if body.get("type") == "url_verification":
                return self._json(200, {"challenge": body.get("challenge")})
            ev = body.get("event") or {}
            if ev.get("type") in ("message", "app_mention") and not ev.get("subtype"):
                try:
                    ingest_message(ev)
                except Exception as e:
                    return self._json(500, {"error": str(e)})
            return self._json(200, {"ok": True})
        self._json(404, {"error": "not found"})

if __name__ == "__main__":
    print(f"mentions listening :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
