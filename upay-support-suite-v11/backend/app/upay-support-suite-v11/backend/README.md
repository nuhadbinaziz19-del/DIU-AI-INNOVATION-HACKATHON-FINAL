# upay backend (FastAPI + PostgreSQL)

Serves the REST API under `/api` and also the front-end folder `../upay-support-suite` at `/`.

## Run (Docker)
    cp backend/.env.example backend/.env   # change the secrets
    docker compose up --build   # run from the folder that contains docker-compose.yml; http://localhost:8000, admin: /admin.html

## Run (without Docker)
    createdb upay
    pip install -r requirements.txt
    export DATABASE_URL=postgresql://user:pass@localhost:5432/upay
    uvicorn app.main:app_factory --factory --port 8000
The schema (`schema.sql`) is applied automatically at start (idempotent).

## Settings (environment)
| name | meaning |
|---|---|
| DATABASE_URL | Postgres connection string |
| UPAY_SECRET_KEY | signs login tokens - long random string |
| UPAY_ADMIN_KEY | the admin console sends it as `X-Admin-Key` |
| UPAY_DEMO_MODE | `1` = demo login, add-money, demo tools, demo badge, OTP shown on screen. **Must be `0` in production.** With `0` the app also refuses to start if UPAY_SECRET_KEY / UPAY_ADMIN_KEY are still the dev defaults |
| UPAY_REFERRAL_BONUS / UPAY_REFERRAL_MAX | referral bonus per person (default 50) / max bonuses one referrer can earn (default 10) |
| UPAY_SCHEDULER_INTERVAL_S | how often auto-transfer rules are checked (default 15) |
| UPAY_CORS_ORIGINS | comma separated origins if the front-end is hosted elsewhere |
| UPAY_STATIC_DIR | front-end folder to serve |

## How money is kept safe
- Every payment is one DB transaction. Wallet rows are locked with `SELECT ... FOR UPDATE` in sorted id order (no deadlock); `CHECK (balance >= 0)` is the last safety net.
- `Idempotency-Key` header: a retried request (double tap, bad network) is applied once.
- PIN: PBKDF2-SHA256 (200k rounds, salted). 3 wrong tries lock 60 s; the counter is committed even when the request fails.
- Daily 50,000 / monthly 200,000 limits (Asia/Dhaka day boundaries). Cash-out fee 1.85% (verified students pay 20% less), send money is free.
- Cancel: within 2 minutes, max 3 per 24 h, only if the receiver still has the money free (not in a bucket).
- Money columns are `NUMERIC(14,2)`; the ledger is append-only (a reversal is a new row).

## Tests
    pytest                                   # needs real fastapi + psycopg + a Postgres (PGHOST/PGUSER...)
    python3 tests/e2e_server.py &            # browser tests (Playwright) on port 8800
    python3 tests/e2e_api.py
`tests/test_ledger.py` plus `tests/test_api.py` (45 tests together) run against a real Postgres. If FastAPI is not installed the API tests fall back to `tests/fastapi_shim` (a tiny test-only stand-in); with `pip install -r requirements.txt` they use the real FastAPI.
Test Postgres helper: `tests/pg_start.sh`.

## Before real customers (not done in this demo)
- Replace `/api/auth/demo` with OTP (SMS) login; set `UPAY_DEMO_MODE=0`; remove "Demo tools" from the app.
- Real payment rails (bKash/bank/agent network), KYC, audit/AML rules - this is a wallet ledger, not a licensed payment system.
- Rate limiting is in memory (one process); use a shared store (Redis) or a gateway when running several workers.
- JSON money values are numbers; if you need exact strings, change the response encoding.
- HTTPS, backups, monitoring, secrets management.

## Sign-up and login (customers)
- `POST /api/auth/register` `{name, phone, nid, dob (YYYY-MM-DD), pin}` creates the wallet (balance 0) and returns `{token, wallet}`. One account per mobile number and per NID. The NID is stored only as an HMAC hash (keyed with UPAY_SECRET_KEY) plus its last 4 digits.
- `POST /api/auth/login` `{phone, pin}` returns `{token, wallet}`. Wrong PINs use the same counter and 60 s lock as payments; unknown number and wrong PIN give the same error. Both calls are rate limited per number.
- Still to do before real customers: SMS OTP to prove the number, real NID/KYC verification (this only checks the format), and set `UPAY_DEMO_MODE=0` so `/api/auth/demo` is closed.

## Customer settings and lost-phone freeze
- `GET /api/prefs` returns `{favs, billers, reminders}` (the photo is separate because it is big). `GET /api/prefs/{key}` returns `{value}` for one of `favs`, `billers`, `reminders`, `photo`. `PUT /api/prefs/{key}` `{value}` replaces it. Each key is validated (favourites need a real 01XXXXXXXXX number and duplicates are dropped, reminder day 1-28, photo only a JPEG data URL up to 300,000 characters). A customer only sees their own rows; any other key gives 403. Stored in table `prefs` (created automatically at start).
- `POST /api/freeze` `{pin}` freezes the caller's own wallet. It needs the PIN (wrong tries count and lock like payments), so a customer who has no PIN yet cannot use it. It records `frozen_by = "self"` and `frozen_at`. Freezing twice is harmless.
- Only an admin can unfreeze: `POST /api/admin/freeze {uid, frozen:false}` (header `X-Admin-Key`). That clears `frozen_by`. A customer-side unfreeze does not exist on purpose, because without SMS OTP or eKYC the server cannot tell the owner from a thief who holds the phone.

## SMS OTP, audit log, AI feedback (Round 11)
- `POST /api/auth/otp/request {phone, purpose: "register"|"login"}` sends a 6-digit code (2 min). `POST /api/auth/otp/verify {phone, purpose, code}` returns `{otp_token}` (single use, 5 min, tied to number and purpose). `register` and `login` need `otp_token` unless `UPAY_OTP_REQUIRED=0` (development only).
- Limits: 5 wrong tries per code, resend after 30 s, 5 codes per number per hour, plus per-number request limits.
- SMS: set `UPAY_SMS_WEBHOOK_URL` (POST `{"to","text"}`) to your SMS gateway. Not set = code is only logged; with `UPAY_DEMO_MODE=1` it is also returned as `demo_code`. Production: `UPAY_DEMO_MODE=0`.
- Tables `otps`, `audit_log`, `ai_feedback` are created automatically. Audit log never stores PINs, codes or full NIDs. Admin: `GET /api/admin/audit`, `GET /api/admin/ai-feedback`.

## Referral bonus (Round 12)
- Code = `UP` + the customer's number without the leading `01` (shown in More > Refer). `POST /api/auth/register` takes an optional `referral_code`.
- Rule: the new customer and the referrer each get `UPAY_REFERRAL_BONUS` (50), paid at registration inside the same DB transaction as the sign-up (all or nothing). Each referred customer can be rewarded once (`referrals.referee_uid` is the primary key). One referrer can earn at most `UPAY_REFERRAL_MAX` (10) bonuses; after that the friend still registers, with no bonus (`wallet.referral.status = "limit"`). The referrer row is locked, so parallel sign-ups cannot pass the cap.
- A wrong or unknown code (or a frozen referrer) is rejected with `bad_referral` BEFORE the one-time OTP token is used, so the customer can fix the code and continue. Own code is rejected.
- Bonus shows in history as kind `referral` and cannot be cancelled like Send Money. Admin: `GET /api/admin/referrals`; the audit log records `referral_bonus`.
- Business note: this is promo money created by upay (marketing cost). Immediate payout is easy to farm with fake accounts; before real customers consider paying only after the friend's first cash-in/payment.

## Demo vs production
- `GET /config.js` now also sets `window.UPAY_DEMO` (true only when `UPAY_DEMO_MODE=1`). With it false the app removes More > Demo tools, ignores the `?u=` login shortcut, hides the demo badge and the "Demo SMS" box, and Add Money says a bank/card gateway is not connected.
- With it true the app shows a "DEMO SERVER" badge, a "DEMO ONLY" tag on Demo tools, and the SMS code is shown in a labelled "Demo SMS" box (simulated OTP).
