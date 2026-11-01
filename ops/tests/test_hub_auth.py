"""Тести auth для ops/mentions і ops/netmap: python3 -m unittest discover -s ops/tests"""
import importlib.util, json, os, threading, unittest, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

USERS = {"tok-admin": {"name": "Boss", "role": "admin"}, "tok-user": {"name": "U", "role": "user"}}

class FakeOncall(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass
    def do_GET(self):
        tok = (self.headers.get("Authorization") or "")[7:]
        me = USERS.get(tok)
        self.send_response(200 if me else 401)
        self.end_headers()
        self.wfile.write(json.dumps(me or {"error": "no session"}).encode())

def serve(handler):
    srv = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def call(base, path, method="GET", cookie=None, body=None, hdr=None):
    req = urllib.request.Request(base + path, method=method, data=(body or "").encode() if method == "POST" else None)
    if cookie:
        req.add_header("Cookie", "oncall_session=" + cookie)
    for k, v in (hdr or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code

HERE = os.path.dirname(os.path.abspath(__file__))

class HubAuth(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fake, base = serve(FakeOncall)
        os.environ["ONCALL_API"] = base
        os.environ.pop("SLACK_SIGNING_SECRET", None)
        os.environ.pop("DATABASE_URL", None)
        cls.mentions = load("mentions_app", os.path.join(HERE, "..", "mentions", "app.py"))
        cls.netmap = load("netmap_app", os.path.join(HERE, "..", "netmap", "app.py"))
        cls.msrv, cls.mbase = serve(cls.mentions.H)
        cls.nsrv, cls.nbase = serve(cls.netmap.H)

    def test_mentions_api_requires_session(self):
        self.assertEqual(call(self.mbase, "/api/mentions"), 401)
        self.assertEqual(call(self.mbase, "/api/people", hdr={"X-Oncall-User": "Boss"}), 401)
        self.assertEqual(call(self.mbase, "/api/backfill", cookie="tok-user"), 403)
        self.assertEqual(call(self.mbase, "/api/debug", cookie="tok-user"), 403)
        self.assertEqual(call(self.mbase, "/health"), 200)

    def test_mentions_slack_events_fail_closed(self):
        self.assertEqual(call(self.mbase, "/api/slack/events", "POST", body='{"event":{"type":"message","text":"x"}}'), 403)

    def test_netmap_post_admin_only(self):
        self.assertEqual(call(self.nbase, "/api/scan", "POST", body="{}"), 401)
        self.assertEqual(call(self.nbase, "/api/scan", "POST", cookie="tok-user", body="{}"), 403)
        self.assertEqual(call(self.nbase, "/api/cidrs", "POST", cookie="tok-user", body='{"cidr":"10.0.0.0/30"}'), 403)
        self.assertEqual(call(self.nbase, "/api/hosts"), 401)
        self.assertEqual(call(self.nbase, "/health"), 200)

    def test_netmap_admin_passes_auth(self):
        # admin проходить auth; далі 400 через поганий CIDR (БД не потрібна)
        self.assertEqual(call(self.nbase, "/api/cidrs", "POST", cookie="tok-admin", body='{"cidr":"bad"}'), 400)

if __name__ == "__main__":
    unittest.main()
