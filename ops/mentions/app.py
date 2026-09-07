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
USER = os.getenv("SLACK_USER_TOKEN", "")
SIGN = os.getenv("SLACK_SIGNING_SECRET", "")
TEAM_GROUP = os.getenv("SLACK_DEVOPS_GROUP", "devops-team")
PORT = int(os.getenv("PORT", "8091"))
ONCALL_API = os.getenv("ONCALL_API", "http://oncall_nginx_5")

SCHEMA_SQL = """
CREATE SCHEMA IF NOT EXISTS mentions;
CREATE TABLE IF NOT EXISTS mentions.items (
  id            BIGSERIAL PRIMARY KEY,
  slack_ts      TEXT NOT NULL,
  channel_id    TEXT NOT NULL DEFAULT '',
  channel_name  TEXT NOT NULL DEFAULT '',
  permalink     TEXT NOT NULL DEFAULT '',
  author_id     TEXT NOT NULL DEFAULT '',
  author_name   TEXT NOT NULL DEFAULT '',
  mention_type  TEXT NOT NULL DEFAULT 'user',
  mentioned_id  TEXT NOT NULL DEFAULT '',
  mentioned     TEXT NOT NULL DEFAULT '',
  text_full     TEXT NOT NULL DEFAULT '',
  text_short    TEXT NOT NULL DEFAULT '',
  keywords      TEXT[] NOT NULL DEFAULT '{}',
  msg_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  day           DATE NOT NULL DEFAULT CURRENT_DATE,
  reactions_json TEXT NOT NULL DEFAULT '[]',
  replies_json    TEXT NOT NULL DEFAULT '[]',
  reply_count     INT NOT NULL DEFAULT 0,
  UNIQUE (slack_ts, channel_id, mentioned_id)
);
CREATE INDEX IF NOT EXISTS idx_mentions_day ON mentions.items (day DESC, msg_at DESC);
CREATE TABLE IF NOT EXISTS mentions.keywords (
  id SERIAL PRIMARY KEY,
  word TEXT UNIQUE NOT NULL,
  kind TEXT NOT NULL DEFAULT 'service'
);
"""

def ensure_schema():
    try:
        q(SCHEMA_SQL)
        q("ALTER TABLE mentions.items ADD COLUMN IF NOT EXISTS reactions_json TEXT DEFAULT '[]'")
        q("ALTER TABLE mentions.items ADD COLUMN IF NOT EXISTS replies_json TEXT DEFAULT '[]'")
        q("ALTER TABLE mentions.items ADD COLUMN IF NOT EXISTS reply_count INT DEFAULT 0")
        print("schema ok", flush=True)
    except Exception as e:
        print("schema err", e, flush=True)

NAME_CACHE = {}
BACKFILL_JOB = {"status": "idle", "result": None}

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


def refresh_oncall_roster():
    """Replace mentions.roster with OnCall /api/data team_members only."""
    import datetime as dt
    now = dt.date.today()
    url = f"{ONCALL_API.rstrip('/')}/api/data?year={now.year}&month={now.month}"
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print("oncall roster", e, flush=True)
        return []
    members = data.get("team_members") or []
    names = []
    try:
        q("DELETE FROM mentions.roster")
    except Exception as e:
        print("roster wipe", e, flush=True)
    for m in members:
        name = (m.get("name") or m.get("username") or "").strip()
        uname = (m.get("username") or "").strip()
        sid = (m.get("slack_id") or m.get("slack") or "").strip()
        if not name or name.lower() == "admin":
            continue
        key = sid or ("name:"+name)
        try:
            q("""INSERT INTO mentions.roster (slack_id, name, username, is_team)
                 VALUES (%s,%s,%s,false)
                 ON CONFLICT (slack_id) DO UPDATE SET name=EXCLUDED.name, username=EXCLUDED.username""",
              (key, name, uname))
        except Exception as e:
            print("roster upsert", e, flush=True)
        names.append({"slack_id": sid, "name": name, "username": uname})
    print("roster oncall", len(names), "from", url, flush=True)
    try:
        q("""INSERT INTO mentions.roster (slack_id, name, username, is_team)
             VALUES (%s,%s,%s,true)
             ON CONFLICT (slack_id) DO UPDATE SET name=EXCLUDED.name, is_team=true""",
          ("S03QEQF27AN", "@devops-team", "devops-team"))
    except Exception:
        pass
    return names


def roster_allow():
    rows = []
    try:
        rows = q("SELECT slack_id, name, username, is_team FROM mentions.roster", fetch=True) or []
    except Exception:
        rows = []
    if not rows:
        rows = refresh_oncall_roster()
        try:
            rows = q("SELECT slack_id, name, username, is_team FROM mentions.roster", fetch=True) or rows
        except Exception:
            pass
    ids, names = set(), set()
    for r in rows:
        if isinstance(r, dict):
            if r.get("slack_id"): ids.add(str(r["slack_id"]).lstrip("@").upper())
            if r.get("name"): names.add(r["name"].lower())
            if r.get("username"): names.add(r["username"].lower())
        else:
            if r.get("slack_id"): ids.add(str(r["slack_id"]).lstrip("@").upper())
    names.add(TEAM_GROUP.lower())
    names.add("devops-team")
    ids.add("S03QEQF27AN")
    return ids, names

def allowed_mention(mid, name):
    ids, names = roster_allow()
    mid = (mid or "").lstrip("@")
    name = (name or "").lstrip("@")
    if mid.upper() in ids or mid in ids:
        return True
    if name.lower() in names:
        return True
    if "devops" in name.lower():
        return True
    return False

def extract_kw(text):
    found = []
    low = text.lower()
    for w, k in keywords():
        if w.lower() in low:
            found.append(w)
    return found

def slack_api_tok(token, method, payload):
    if not token:
        return {"ok": False, "error": "no_token"}
    data = urllib.parse.urlencode(payload).encode()
    req = urllib.request.Request(
        f"https://slack.com/api/{method}", data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())

def slack_api(method, payload):
    return slack_api_tok(BOT, method, payload)

def list_bot_channels():
    chans = []
    cursor = ""
    for typ in ("public_channel,private_channel",):
        cursor = ""
        while True:
            payload = {"types": "public_channel,private_channel", "limit": "200", "exclude_archived": "true"}
            if cursor:
                payload["cursor"] = cursor
            d = slack_api("conversations.list", payload)
            if not d.get("ok"):
                return chans, d.get("error")
            for c in d.get("channels") or []:
                if c.get("is_member") or c.get("is_private"):
                    chans.append({"id": c.get("id"), "name": c.get("name")})
            cursor = ((d.get("response_metadata") or {}).get("next_cursor") or "")
            if not cursor:
                break
    return chans, None

def history_channel(cid, limit=80):
    d = slack_api("conversations.history", {"channel": cid, "limit": str(limit)})
    return d.get("messages") or [], d.get("ok"), d.get("error")


def backfill():
    """Workspace-wide: user token + search.messages. Fallback: history in joined channels."""
    if USER:
        roster = refresh_oncall_roster()
        queries = ["@devops-team", "<!subteam^S03QEQF27AN>"]
        for m in roster[:30]:
            if m.get("name"):
                queries.append("@" + m["name"].split()[0])
            if m.get("slack_id") and m["slack_id"].startswith("U"):
                queries.append("<@" + m["slack_id"] + ">")
        total, detail = 0, []
        for query in queries:
            d = slack_api_tok(USER, "search.messages", {"query": query, "count": "50", "sort": "timestamp", "sort_dir": "desc"})
            if not d.get("ok"):
                detail.append({"q": query, "error": d.get("error")})
                continue
            matches = ((d.get("messages") or {}).get("matches") or [])
            got = 0
            for m in matches:
                ev = {
                    "text": m.get("text") or "",
                    "channel": (m.get("channel") or {}).get("id") or "",
                    "ts": m.get("ts") or "",
                    "user": m.get("user") or "",
                }
                try:
                    got += ingest_message(ev, force_team=True)
                except Exception as e:
                    print("ingest", e, flush=True)
            total += got
            detail.append({"q": query, "hits": len(matches), "ingested": got})
        return {"ingested": total, "mode": "search.user", "detail": detail}
    if not BOT:
        return {"error": "no SLACK_USER_TOKEN (xoxp) and no SLACK_BOT_TOKEN"}
    # fallback joined channels only
    chans, err = list_bot_channels()
    if err and not chans:
        return {"error": err, "ingested": 0, "mode": "history.bot", "hint": "додайте SLACK_USER_TOKEN=xoxp-... для пошуку по всьому workspace"}
    total, detail = 0, []
    for ch in (chans or [])[:40]:
        msgs, ok, e = history_channel(ch["id"])
        if not ok:
            detail.append({"ch": ch.get("name"), "error": e})
            continue
        got = 0
        for m in msgs:
            if m.get("subtype"):
                continue
            ev = {"text": m.get("text") or "", "channel": ch["id"], "ts": m.get("ts") or "", "user": m.get("user") or ""}
            try:
                got += ingest_message(ev)
            except Exception:
                pass
        total += got
        if got:
            detail.append({"ch": ch.get("name"), "ingested": got})
    return {"ingested": total, "mode": "history.bot", "channels": len(chans or []), "detail": detail[:20], "hint": "для всіх каналів потрібен xoxp (User OAuth Token)"}


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


def display_name(uid):
    if not uid:
        return ""
    uid = uid.strip("<>@")
    if uid in NAME_CACHE:
        return NAME_CACHE[uid]
    if uid.startswith("S") or uid == TEAM_GROUP:
        NAME_CACHE[uid] = "@devops-team"
        return NAME_CACHE[uid]
    if BOT and uid.startswith("U"):
        try:
            d = slack_api("users.info", {"user": uid})
            u = d.get("user") or {}
            p = u.get("profile") or {}
            nm = p.get("display_name") or p.get("real_name") or u.get("name") or uid
            NAME_CACHE[uid] = nm
            return nm
        except Exception:
            pass
    NAME_CACHE[uid] = uid
    return uid

def pretty_text(text):
    text = text or ""
    def sub_user(m):
        return "@" + display_name(m.group(1))
    def sub_team(m):
        handle = m.group(2) or "devops-team"
        return "@" + handle.lstrip("@")
    text = re.sub(r"<@([UWS][A-Z0-9]+)(?:\|[^>]+)?>", sub_user, text)
    text = re.sub(r"<!subteam\^([A-Z0-9]+)(?:\|@?([^>]+))?>", sub_team, text)
    text = re.sub(r"<([^|>]+)\|([^>]+)>", r"\2", text)
    return text

def enrich_thread(channel, ts):
    reactions, replies = [], []
    if not BOT or not channel or not ts:
        return reactions, replies
    d = slack_api("conversations.replies", {"channel": channel, "ts": ts, "limit": "50"})
    msgs = d.get("messages") or []
    if msgs:
        root = msgs[0]
        for rx in root.get("reactions") or []:
            users = [display_name(u) for u in (rx.get("users") or [])]
            reactions.append({"name": rx.get("name"), "count": rx.get("count") or len(users), "users": users})
        for m in msgs[1:]:
            replies.append({
                "ts": m.get("ts"),
                "user": display_name(m.get("user") or ""),
                "text": pretty_text(m.get("text") or ""),
                "reactions": [
                    {"name": r.get("name"), "count": r.get("count"), "users": [display_name(u) for u in (r.get("users") or [])]}
                    for r in (m.get("reactions") or [])
                ],
            })
    return reactions, replies

def short_text(t, n=140):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = re.sub(r"\s+", " ", t).strip()
    return t if len(t) <= n else t[:n] + "…"

def store_item(**kw):
    q("""INSERT INTO mentions.items
        (slack_ts, channel_id, channel_name, permalink, author_id, author_name,
         mention_type, mentioned_id, mentioned, text_full, text_short, keywords, msg_at, day,
         reactions_json, replies_json, reply_count)
        VALUES (%(slack_ts)s,%(channel_id)s,%(channel_name)s,%(permalink)s,%(author_id)s,%(author_name)s,
                %(mention_type)s,%(mentioned_id)s,%(mentioned)s,%(text_full)s,%(text_short)s,%(keywords)s,%(msg_at)s,%(day)s,
                %(reactions_json)s,%(replies_json)s,%(reply_count)s)
        ON CONFLICT (slack_ts, channel_id, mentioned_id) DO UPDATE SET
          text_full=EXCLUDED.text_full, text_short=EXCLUDED.text_short,
          author_name=EXCLUDED.author_name, mentioned=EXCLUDED.mentioned,
          reactions_json=EXCLUDED.reactions_json, replies_json=EXCLUDED.replies_json,
          reply_count=EXCLUDED.reply_count""", kw)

def ingest_message(ev, force_team=False):
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
    if force_team and not targets:
        targets.append(("team", TEAM_GROUP, TEAM_GROUP))
    for m in MENTION_RE.finditer(text):
        sid = m.group(1)
        nm = m.group(2) or (user_name(sid) if BOT else sid)
        targets.append(("user", sid, nm))
    kws = extract_kw(text)
    targets = [(typ, mid, name) for typ, mid, name in targets if allowed_mention(mid, name) or typ == "team"]
    for typ, mid, name in targets:
        nice = pretty_text(text)
        who = display_name(mid) if typ != "team" else "@devops-team"
        rx, th = enrich_thread(cid, ts)
        store_item(
            slack_ts=ts, channel_id=cid, channel_name=chn, permalink=link,
            author_id=uid, author_name=display_name(uid) or auth, mention_type=typ, mentioned_id=mid,
            mentioned=who, text_full=nice, text_short=short_text(nice),
            keywords=kws, msg_at=when, day=day,
            reactions_json=json.dumps(rx, ensure_ascii=False),
            replies_json=json.dumps(th, ensure_ascii=False),
            reply_count=len(th),
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
        if path in ("/health", "/api/health") or path.endswith("/api/slack/events"):
            return self._json(200, {"ok": True, "bot": bool(BOT), "path": path})
        if path.endswith("/api/debug"):
            cnt = 0
            err = None
            try:
                row = q("SELECT COUNT(*) AS n FROM mentions.items", fetch=True, one=True)
                cnt = (row or {}).get("n") or 0
            except Exception as e:
                err = str(e)
            nros=0
            try:
                rr=q("SELECT COUNT(*) AS n FROM mentions.roster", fetch=True, one=True)
                nros=(rr or {}).get("n") or 0
            except Exception:
                pass
            return self._json(200, {"bot": bool(BOT), "user": bool(USER), "db": cnt, "roster": nros, "db_error": err})
        if path.endswith("/api/backfill/status"):
            return self._json(200, BACKFILL_JOB)
        if path.endswith("/api/backfill"):
            if BACKFILL_JOB.get("status") == "running":
                return self._json(200, BACKFILL_JOB)
            import threading
            BACKFILL_JOB["status"] = "running"
            BACKFILL_JOB["result"] = None
            def _run():
                try:
                    BACKFILL_JOB["result"] = backfill()
                    BACKFILL_JOB["status"] = "done"
                except Exception as e:
                    BACKFILL_JOB["result"] = {"error": str(e)}
                    BACKFILL_JOB["status"] = "error"
            threading.Thread(target=_run, daemon=True).start()
            return self._json(200, {"status": "running", "ingested": 0, "hint": "пошук у фоні, повторіть кнопку за 10с"})
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
                sql += """ AND (day=%s OR (
                    mention_type='team' AND COALESCE(reply_count,0)=0
                    AND COALESCE(reactions_json,'[]') IN ('[]','null','')
                    AND msg_at < NOW() - INTERVAL '10 hours'
                    AND msg_at >= NOW() - INTERVAL '7 days'
                ))"""
                args.append(day)
            else:
                sql += " AND day>=%s::date - 14"; args.append(day)
            author = (qs.get("author") or [""])[0]
            if author:
                sql += " AND author_name=%s"
                args.append(author)
            sql += " ORDER BY channel_name ASC, msg_at DESC LIMIT 500"
            try:
                rows = q(sql, args, fetch=True)
            except Exception as e:
                return self._json(500, {"error": str(e)})
            for row in rows:
                try:
                    rx = row.get("reactions_json") or "[]"
                    empty_rx = rx in ("[]","null","")
                    stale = (row.get("mention_type")=="team"
                             and int(row.get("reply_count") or 0)==0
                             and empty_rx
                             and row.get("msg_at"))
                    row["stale"] = bool(stale)
                except Exception:
                    row["stale"] = False
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
        if path.endswith("/api/slack/events") or path.endswith("/slack/events"):
            try:
                body = json.loads(raw or "{}")
            except Exception:
                body = {}
            # Slack URL check must succeed even if signing secret not set yet
            if body.get("type") == "url_verification" or body.get("challenge"):
                return self._json(200, {"challenge": body.get("challenge")})
            if SIGN and not verify_slack(self.headers, raw):
                return self._json(401, {"error": "bad slack signature"})
            ev = body.get("event") or {}
            if ev.get("type") in ("message", "app_mention") and not ev.get("subtype"):
                try:
                    ingest_message(ev)
                except Exception as e:
                    print("ingest event", e, flush=True)
            return self._json(200, {"ok": True})
        self._json(404, {"error": "not found"})

def poll_loop():
    import time as _t
    _t.sleep(8)
    while True:
        try:
            print("backfill", backfill(), flush=True)
        except Exception as e:
            print("backfill err", e, flush=True)
        _t.sleep(300)

if __name__ == "__main__":
    ensure_schema()
    refresh_oncall_roster()
    print(f"mentions listening :{PORT} bot={bool(BOT)} user={bool(USER)}", flush=True)
    import threading
    threading.Thread(target=poll_loop, daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
