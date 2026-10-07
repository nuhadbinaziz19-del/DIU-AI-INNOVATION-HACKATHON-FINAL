"""SMS one-time passwords: proves the person holds the phone number before sign-up or login.
Rules: 6 digits, 2 minute life, 5 wrong tries then the code is dead, resend only after 30 s, max 5 codes per number per hour.
Only an HMAC of the code is stored. A verified code is exchanged for a short-lived, single-use otp_token."""
from __future__ import annotations
import base64, hashlib, hmac, json, logging, secrets, time
from . import config as C
from .ledger import LedgerError, now_ms

log = logging.getLogger("upay.otp")
PURPOSES = ("register", "login")


def _hash(phone: str, purpose: str, code: str) -> str:
    return hmac.new(C.SECRET_KEY.encode(), f"otp|{phone}|{purpose}|{code}".encode(), hashlib.sha256).hexdigest()


def _check_phone(phone: str, purpose: str) -> str:
    phone = (phone or "").strip()
    if not (len(phone) == 11 and phone.isdigit() and phone.startswith("01")):
        raise LedgerError("bad_request", "Enter an 11-digit mobile number")
    if purpose not in PURPOSES:
        raise LedgerError("bad_request", "Unknown purpose")
    return phone


def send_sms(phone: str, text: str) -> None:
    if C.SMS_WEBHOOK_URL:
        import urllib.request
        req = urllib.request.Request(C.SMS_WEBHOOK_URL, data=json.dumps({"to": phone, "text": text}).encode(),
                                     headers={"Content-Type": "application/json"}, method="POST")
        urllib.request.urlopen(req, timeout=8).read()
    else:
        log.warning("SMS (no provider configured) to %s***: %s", phone[:5], "code hidden" if not C.DEMO_MODE else text)


def request_code(db, phone: str, purpose: str, exists: bool, now: int | None = None) -> dict:
    """Creates and sends a code. For login the answer is the same whether or not the number has an account (no account probing);
    the SMS is only sent when it does."""
    phone, now = _check_phone(phone, purpose), now or now_ms()
    with db.tx() as c:
        last = c.one("SELECT created_at FROM otps WHERE phone=%s AND purpose=%s ORDER BY created_at DESC LIMIT 1", phone, purpose)
        if last and now - last["created_at"] < C.OTP_RESEND_S * 1000:
            raise LedgerError("rate_limited", "Wait %d seconds before asking for a new code" % (C.OTP_RESEND_S - (now - last["created_at"]) // 1000))
        n = c.one("SELECT count(*) AS n FROM otps WHERE phone=%s AND created_at > %s", phone, now - 3600_000)["n"]
        if n >= C.OTP_MAX_SENDS_PER_HOUR:
            raise LedgerError("rate_limited", "Too many codes requested, try again in an hour")
        code = "%06d" % secrets.randbelow(10**6)
        if exists or purpose == "register":
            c.run("INSERT INTO otps (phone,purpose,code_hash,created_at,expires_at) VALUES (%s,%s,%s,%s,%s)",
                  phone, purpose, _hash(phone, purpose, code), now, now + C.OTP_TTL_S * 1000)
        else:                                   # fake row so timing and rate limits look the same
            c.run("INSERT INTO otps (phone,purpose,code_hash,created_at,expires_at,tries) VALUES (%s,%s,%s,%s,%s,%s)",
                  phone, purpose, "-", now, now + C.OTP_TTL_S * 1000, 99)
    if exists or purpose == "register":
        send_sms(phone, "upay 2.0 code: %s. Valid %d min. Never share it with anyone." % (code, C.OTP_TTL_S // 60))
    out = {"ok": True, "expires_in": C.OTP_TTL_S, "resend_in": C.OTP_RESEND_S}
    if C.DEMO_MODE and (exists or purpose == "register"):
        out["demo_code"] = code                 # demo only: lets the demo run without an SMS account
    return out


def verify_code(db, phone: str, purpose: str, code: str, now: int | None = None) -> dict:
    phone, now = _check_phone(phone, purpose), now or now_ms()
    code = (code or "").strip()
    with db.tx() as c:
        row = c.one("SELECT * FROM otps WHERE phone=%s AND purpose=%s AND NOT verified ORDER BY created_at DESC LIMIT 1", phone, purpose)
        if not row or row["expires_at"] < now or row["tries"] >= C.OTP_MAX_TRIES:
            ok = None
        else:
            c.run("UPDATE otps SET tries=tries+1 WHERE id=%s", row["id"])      # committed even when the code is wrong
            ok = row["code_hash"] != "-" and hmac.compare_digest(row["code_hash"], _hash(phone, purpose, code))
            if ok:
                c.run("UPDATE otps SET verified=true WHERE id=%s", row["id"])
    if not ok:                                  # raised after the transaction so the try counter is kept
        raise LedgerError("otp_wrong", "Wrong or expired code")
    oid = row["id"]
    body = base64.urlsafe_b64encode(json.dumps({"o": oid, "p": phone, "k": purpose, "exp": int(time.time()) + C.OTP_TOKEN_TTL_S},
                                               separators=(",", ":")).encode()).rstrip(b"=").decode()
    sig = hmac.new(C.SECRET_KEY.encode(), ("otpt|" + body).encode(), hashlib.sha256).hexdigest()
    return {"otp_token": body + "." + sig}


def consume_token(db, token: str | None, phone: str, purpose: str) -> None:
    """Called by register / login. The token must be genuine, unexpired, for this number and purpose, and is single use."""
    err = LedgerError("otp_required", "Verify your phone with the SMS code first")
    if not token:
        raise err
    try:
        body, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, hmac.new(C.SECRET_KEY.encode(), ("otpt|" + body).encode(), hashlib.sha256).hexdigest()):
            raise err
        d = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except LedgerError:
        raise
    except Exception:
        raise err
    if d["exp"] < time.time() or d["p"] != phone.strip() or d["k"] != purpose:
        raise err
    with db.tx() as c:
        if c.run("UPDATE otps SET used=true WHERE id=%s AND verified AND NOT used", d["o"]) != 1:
            raise err
