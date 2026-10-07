"""HTTP-level tests for the FastAPI app. Needs `pip install -r requirements.txt` (fastapi + httpx).
Uses UPAY_TEST_DATABASE_URL (psycopg) when set, otherwise the psql shim against a local test database.
Run:  python3 -m unittest tests.test_api -v"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from tests import _fastapi
try:
    from fastapi.testclient import TestClient
    from app.main import create_app
    HAVE_FASTAPI = True
except Exception as e:        # fastapi / httpx not installed
    print("API tests skipped:", e)
    HAVE_FASTAPI = False
if HAVE_FASTAPI and _fastapi.SHIM:
    print("NOTE: real FastAPI is not installed, running app/main.py on the test-only shim (tests/fastapi_shim)")

SCHEMA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema.sql")


@unittest.skipUnless(HAVE_FASTAPI, "fastapi/httpx not installed")
class TestApi(unittest.TestCase):
    def setUp(self):
        url = os.getenv("UPAY_TEST_DATABASE_URL")
        if url:
            from app.db import PsycopgDatabase
            self.db = PsycopgDatabase(url)
            with self.db.tx() as c:
                c.run("DROP SCHEMA public CASCADE"); c.run("CREATE SCHEMA public")
            self.db.init_schema(SCHEMA)
        else:
            from tests.psql_shim import PsqlDatabase
            self.db = PsqlDatabase(host=os.getenv("PGHOST", "/tmp")); self.db.reset(SCHEMA)
        self.c = TestClient(create_app(self.db, start_scheduler=False), raise_server_exceptions=False)

    def login(self, uid):
        r = self.c.post("/api/auth/demo", json={"uid": uid, "name": uid.title()})
        self.assertEqual(r.status_code, 200, r.text)
        return {"Authorization": "Bearer " + r.json()["token"]}

    def test_requires_token_and_rejects_forged(self):
        self.assertEqual(self.c.get("/api/me").status_code, 401)
        self.assertEqual(self.c.get("/api/me", headers={"Authorization": "Bearer abc.def"}).status_code, 401)
        h = self.login("rahim"); tok = h["Authorization"][7:]
        body, sig = tok.split(".")
        self.assertEqual(self.c.get("/api/me", headers={"Authorization": f"Bearer {body}.{sig[:-2]}xx"}).status_code, 401)
        self.assertEqual(self.c.get("/api/me", headers=h).status_code, 200)

    def test_pay_flow_pin_and_errors(self):
        a, b = self.login("rahim"), self.login("karim")
        kph = self.c.get("/api/me", headers=b).json()["phone"]
        r = self.c.post("/api/pay", headers=a, json={"service": "send", "amount": 100, "to_phone": kph, "pin": "1234"})
        self.assertEqual((r.status_code, r.json()["error"]), (400, "pin_required"))
        self.assertEqual(self.c.post("/api/pin", headers=a, json={"new_pin": "1234"}).status_code, 200)
        r = self.c.post("/api/pay", headers=a, json={"service": "send", "amount": 100, "to_phone": kph, "pin": "0000"})
        self.assertEqual((r.status_code, r.json()["error"]), (401, "pin_wrong"))
        r = self.c.post("/api/pay", headers={**a, "Idempotency-Key": "abc"}, json={"service": "send", "amount": 100, "to_phone": kph, "pin": "1234"})
        self.assertEqual(r.status_code, 200, r.text); self.assertEqual(float(r.json()["balance"]), 12400.0)
        r2 = self.c.post("/api/pay", headers={**a, "Idempotency-Key": "abc"}, json={"service": "send", "amount": 100, "to_phone": kph, "pin": "1234"})
        self.assertEqual((r2.json()["tx_id"], r2.json()["replayed"]), (r.json()["tx_id"], True))
        self.assertEqual(float(self.c.get("/api/me", headers=b).json()["balance"]), 12600.0)
        self.assertEqual(self.c.post(f"/api/undo/{r.json()['tx_id']}", headers=a).status_code, 200)
        self.assertEqual(self.c.post("/api/undo/nope", headers=a).status_code, 404)

    def test_user_cannot_touch_other_users_or_admin(self):
        a, b = self.login("rahim"), self.login("karim")
        self.assertEqual(self.c.get("/api/admin/wallets", headers=a).status_code, 403)
        self.assertEqual(self.c.post("/api/admin/adjust", headers=a, json={"uid": "rahim", "delta": 999999}).status_code, 403)
        self.assertEqual(self.c.post("/api/admin/student", headers=a, json={"uid": "rahim", "ok": True}).status_code, 403)
        self.assertEqual(self.c.post("/api/account-type", headers=a, json={"acct": "student"}).status_code, 403)
        key = {"X-Admin-Key": os.getenv("UPAY_ADMIN_KEY", "dev-admin-key")}
        self.assertEqual(self.c.get("/api/admin/wallets", headers=key).status_code, 200)
        self.assertEqual(self.c.post("/api/admin/adjust", headers=key, json={"uid": "rahim", "delta": 50}).status_code, 200)
        # documents: a customer cannot write someone else's chat or set a complaint's status
        self.assertEqual(self.c.put("/api/docs/chats/karim", headers=a, json={"msgs": []}).status_code, 403)
        r = self.c.put("/api/docs/complaints/c1", headers=a, json={"cat": "x", "body": "hi", "status": "resolved", "replies": [{"t": "fake"}]})
        self.assertEqual((r.json()["status"], r.json()["replies"]), ("new", []))
        self.assertEqual(self.c.get("/api/docs/complaints/c1", headers=b).status_code, 404)

    def test_student_features_need_admin_approval(self):
        a = self.login("rahim")
        r = self.c.post("/api/buckets", headers=a, json={"name": "food", "amount": 100})
        self.assertEqual((r.status_code, r.json()["error"]), (403, "not_student"))
        self.assertEqual(self.c.post("/api/demo/make-student", headers=a).status_code, 200)
        self.assertEqual(self.c.post("/api/buckets", headers=a, json={"name": "food", "amount": 100}).status_code, 200)
        self.assertEqual(self.c.get("/api/me", headers=a).json()["buckets"][0]["name"], "food")
        self.assertNotIn("pin_hash", self.c.get("/api/me", headers=a).json())

    def test_prefs_are_private_validated_and_survive_relogin(self):
        a, b = self.login("rahim"), self.login("karim")
        fav = [{"phone": "01711111111", "name": "Abbu"}, {"phone": "01711111111", "name": "dup"}]
        r = self.c.put("/api/prefs/favs", headers=a, json={"value": fav})
        self.assertEqual(r.status_code, 200, r.text); self.assertEqual(len(r.json()["value"]), 1)       # duplicate number dropped
        self.assertEqual(self.c.get("/api/prefs", headers=a).json()["favs"][0]["name"], "Abbu")
        self.assertEqual(self.c.get("/api/prefs", headers=b).json()["favs"], [])                        # another customer sees nothing
        self.assertEqual(self.c.put("/api/prefs/favs", headers=a, json={"value": [{"phone": "123"}]}).status_code, 400)
        self.assertEqual(self.c.put("/api/prefs/secret", headers=a, json={"value": 1}).status_code, 403)
        self.assertEqual(self.c.get("/api/prefs/secret", headers=a).status_code, 403)
        self.assertEqual(self.c.put("/api/prefs/favs", headers={}, json={"value": []}).status_code, 401)
        # reminders: day must be 1..28, label needed
        ok = {"label": "Electricity", "day": 5, "amount": 860, "type": "Electricity", "account": "1234"}
        self.assertEqual(self.c.put("/api/prefs/reminders", headers=a, json={"value": [ok]}).status_code, 200)
        for bad in ({**ok, "day": 31}, {**ok, "day": 0}, {**ok, "label": ""}, {**ok, "amount": -5}, {**ok, "day": True}):
            self.assertEqual(self.c.put("/api/prefs/reminders", headers=a, json={"value": [bad]}).status_code, 400, bad)
        self.assertEqual(self.c.put("/api/prefs/billers", headers=a, json={"value": [{"type": "Gas", "account": "99", "label": "Home"}]}).status_code, 200)
        self.assertEqual(self.c.put("/api/prefs/billers", headers=a, json={"value": [{"type": "Gas", "account": ""}]}).status_code, 400)
        # photo: only a small jpeg data URL; it is not part of the bulk /api/prefs answer
        jpg = "data:image/jpeg;base64,/9j/4AAQ"
        self.assertEqual(self.c.put("/api/prefs/photo", headers=a, json={"value": jpg}).status_code, 200)
        self.assertEqual(self.c.put("/api/prefs/photo", headers=a, json={"value": "data:text/html;base64,PHNjcmlwdD4="}).status_code, 400)
        self.assertEqual(self.c.put("/api/prefs/photo", headers=a, json={"value": "data:image/jpeg;base64," + "A" * 300_001}).status_code, 400)
        self.assertEqual(self.c.get("/api/prefs/photo", headers=a).json()["value"], jpg)
        self.assertNotIn("photo", self.c.get("/api/prefs", headers=a).json())
        self.assertEqual(self.c.put("/api/prefs/photo", headers=a, json={"value": ""}).status_code, 200)
        self.assertEqual(self.c.get("/api/prefs/photo", headers=a).json()["value"], "")

    def test_self_freeze_needs_pin_and_only_admin_can_unfreeze(self):
        a, b = self.login("rahim"), self.login("karim")
        kph = self.c.get("/api/me", headers=b).json()["phone"]
        r = self.c.post("/api/freeze", headers=a, json={"pin": "1234"})
        self.assertEqual((r.status_code, r.json()["error"]), (400, "pin_required"))              # no PIN set yet: cannot prove who is asking
        self.c.post("/api/pin", headers=a, json={"new_pin": "1234"})
        r = self.c.post("/api/freeze", headers=a, json={"pin": "0000"})
        self.assertEqual((r.status_code, r.json()["error"]), (401, "pin_wrong"))
        self.assertFalse(self.c.get("/api/me", headers=a).json()["frozen"])
        self.assertEqual(self.c.post("/api/freeze", headers={}, json={"pin": "1234"}).status_code, 401)
        self.assertEqual(self.c.post("/api/freeze", headers=a, json={"pin": "1234"}).status_code, 200)
        me = self.c.get("/api/me", headers=a).json()
        self.assertEqual((me["frozen"], me["frozen_by"]), (True, "self")); self.assertGreater(me["frozen_at"], 0)
        r = self.c.post("/api/pay", headers=a, json={"service": "send", "amount": 10, "to_phone": kph, "pin": "1234"})
        self.assertEqual((r.status_code, r.json()["error"]), (403, "frozen"))
        self.assertEqual(self.c.post("/api/freeze", headers=a, json={"pin": "1234"}).status_code, 200)   # twice is harmless
        self.assertEqual(self.c.post("/api/admin/freeze", headers=a, json={"uid": "rahim", "frozen": False}).status_code, 403)
        key = {"X-Admin-Key": os.getenv("UPAY_ADMIN_KEY", "dev-admin-key")}
        self.assertEqual(self.c.post("/api/admin/freeze", headers=key, json={"uid": "rahim", "frozen": False}).status_code, 200)
        me = self.c.get("/api/me", headers=a).json()
        self.assertEqual((me["frozen"], me["frozen_by"], me["frozen_at"]), (False, "", 0))
        self.assertEqual(self.c.post("/api/pay", headers=a, json={"service": "send", "amount": 10, "to_phone": kph, "pin": "1234"}).status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)


@unittest.skipUnless(HAVE_FASTAPI, "fastapi/httpx not installed")
class TestOtp(TestApi):
    """SMS OTP: needed for sign-up and login, 5 tries, single use, no account probing, audit trail."""
    def setUp(self):
        super().setUp(); os.environ["UPAY_OTP_REQUIRED"] = "1"
    def tearDown(self):
        os.environ.pop("UPAY_OTP_REQUIRED", None)

    def otp(self, phone, purpose):
        r = self.c.post("/api/auth/otp/request", json={"phone": phone, "purpose": purpose}); self.assertEqual(r.status_code, 200, r.text)
        return r.json()

    def verify(self, phone, purpose, code):
        return self.c.post("/api/auth/otp/verify", json={"phone": phone, "purpose": purpose, "code": code})

    REG = {"name": "Nusaiba", "phone": "01711111111", "nid": "1234567890", "dob": "2000-01-01", "pin": "1234"}

    def test_register_needs_otp_then_login_needs_otp(self):
        self.assertEqual(self.c.post("/api/auth/register", json=self.REG).json()["error"], "otp_required")
        code = self.otp(self.REG["phone"], "register")["demo_code"]
        t = self.verify(self.REG["phone"], "register", code).json()["otp_token"]
        r = self.c.post("/api/auth/register", json={**self.REG, "otp_token": t}); self.assertEqual(r.status_code, 200, r.text)
        # token is single use and tied to purpose
        self.assertEqual(self.c.post("/api/auth/register", json={**self.REG, "otp_token": t}).json()["error"], "otp_required")
        self.assertEqual(self.c.post("/api/auth/login", json={"phone": self.REG["phone"], "pin": "1234", "otp_token": t}).json()["error"], "otp_required")
        import time; time.sleep(0.01)
        # login: PIN alone is not enough
        self.assertEqual(self.c.post("/api/auth/login", json={"phone": self.REG["phone"], "pin": "1234"}).json()["error"], "otp_required")

    def test_wrong_code_five_tries_then_dead_and_token_bound_to_number(self):
        ph = "01722222222"; code = self.otp(ph, "register")["demo_code"]
        wrong = "000000" if code != "000000" else "111111"
        for _ in range(5):
            self.assertEqual(self.verify(ph, "register", wrong).status_code, 401)
        self.assertEqual(self.verify(ph, "register", code).status_code, 401)          # right code, but the code is dead now
        ph2 = "01733333333"; c2 = self.otp(ph2, "register")["demo_code"]
        t = self.verify(ph2, "register", c2).json()["otp_token"]
        r = self.c.post("/api/auth/register", json={**self.REG, "phone": "01744444444", "otp_token": t})
        self.assertEqual(r.json()["error"], "otp_required")                           # token of another number

    def test_resend_limit_and_no_account_probing(self):
        ph = "01755555555"; self.otp(ph, "register")
        r = self.c.post("/api/auth/otp/request", json={"phone": ph, "purpose": "register"}); self.assertEqual(r.status_code, 429)
        a = self.otp("01766666666", "login")                                          # unknown number: same shape, no code leaked
        self.assertEqual(sorted(a), ["expires_in", "ok", "resend_in"])

    def reg(self, phone, nid, ref=None):
        code = self.otp(phone, "register")["demo_code"]
        t = self.verify(phone, "register", code).json()["otp_token"]
        body = {**self.REG, "phone": phone, "nid": nid, "otp_token": t}
        if ref is not None:
            body["referral_code"] = ref
        return self.c.post("/api/auth/register", json=body)

    def test_referral_bonus_paid_to_both_once_and_capped(self):
        r = self.reg("01711111111", "1234567890"); self.assertEqual(r.status_code, 200, r.text)
        ha = {"Authorization": "Bearer " + r.json()["token"]}
        code = "UP" + "01711111111"[2:]
        # wrong code is rejected and does NOT burn the OTP token
        ph = "01722222222"; c2 = self.otp(ph, "register")["demo_code"]; t = self.verify(ph, "register", c2).json()["otp_token"]
        body = {**self.REG, "phone": ph, "nid": "2234567890", "otp_token": t}
        for bad in ("UP999999999", "UP12", code.replace("UP", "XX")):
            self.assertEqual(self.c.post("/api/auth/register", json={**body, "referral_code": bad}).json()["error"], "bad_referral")
        ok = self.c.post("/api/auth/register", json={**body, "referral_code": code.lower()}); self.assertEqual(ok.status_code, 200, ok.text)
        self.assertEqual(ok.json()["wallet"]["referral"]["status"], "paid")
        self.assertEqual(float(ok.json()["wallet"]["balance"]), 50.0)
        self.assertEqual(float(self.c.get("/api/me", headers=ha).json()["balance"]), 50.0)
        kinds = [x["kind"] for x in self.c.get("/api/history", headers=ha).json()]
        self.assertEqual(kinds, ["referral"])
        # no code: no bonus; the bonus cannot be undone like a Send Money
        self.assertEqual(float(self.reg("01733333333", "3234567890").json()["wallet"]["balance"]), 0.0)
        tid = self.c.get("/api/history", headers=ha).json()[0]["id"]
        self.assertEqual(self.c.post(f"/api/undo/{tid}", headers=ha).status_code, 403)
        # cap: after 10 bonuses a referrer's code still registers the friend, but pays nothing
        import app.config as C
        C.REFERRAL_MAX_PER_REFERRER, old = 2, C.REFERRAL_MAX_PER_REFERRER
        try:
            r3 = self.reg("01744444444", "4234567890", code); self.assertEqual(r3.json()["wallet"]["referral"]["status"], "paid")
            r4 = self.reg("01755555555", "5234567890", code)
            self.assertEqual((r4.status_code, r4.json()["wallet"]["referral"]["status"], float(r4.json()["wallet"]["balance"])), (200, "limit", 0.0))
            self.assertEqual(float(self.c.get("/api/me", headers=ha).json()["balance"]), 100.0)
        finally:
            C.REFERRAL_MAX_PER_REFERRER = old
        rows = self.c.get("/api/admin/referrals", headers={"X-Admin-Key": "dev-admin-key"}).json()
        self.assertEqual(len(rows), 2)

    def test_demo_off_closes_demo_endpoints_and_config(self):
        import app.config as C
        h = self.login("rahim")
        self.assertIn("UPAY_DEMO=true", self.c.get("/config.js").text)
        C.DEMO_MODE = False
        try:
            self.assertEqual(self.c.post("/api/auth/demo", json={"uid": "x1", "name": "X"}).status_code, 403)
            for p in ("add-money", "make-student", "reset-pin"):
                self.assertEqual(self.c.post("/api/demo/" + p, headers=h, json={"amount": 5}).status_code, 403)
            self.assertIn("UPAY_DEMO=false", self.c.get("/config.js").text)
            self.assertNotIn("demo_code", self.otp("01766666666", "register"))
        finally:
            C.DEMO_MODE = True

    def test_audit_and_ai_feedback(self):
        code = self.otp(self.REG["phone"], "register")["demo_code"]
        t = self.verify(self.REG["phone"], "register", code).json()["otp_token"]
        tok = self.c.post("/api/auth/register", json={**self.REG, "otp_token": t}).json()["token"]
        h = {"Authorization": "Bearer " + tok}
        self.assertEqual(self.c.post("/api/ai/feedback", headers=h, json={"feature": "riskcheck", "helpful": False, "note": "x"}).status_code, 200)
        a = {"X-Admin-Key": "dev-admin-key"}
        self.assertEqual(self.c.get("/api/admin/ai-feedback", headers=a).json()[0]["not_helpful"], 1)
        log = self.c.get("/api/admin/audit", headers=a).json()
        self.assertTrue(any(x["action"] == "register" for x in log))
        self.assertNotIn("1234567890", str(log))
