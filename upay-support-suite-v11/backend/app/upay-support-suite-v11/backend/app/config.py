"""Settings from environment variables (12-factor)."""
import os
from decimal import Decimal

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://upay:upay@localhost:5432/upay")
SECRET_KEY = os.getenv("UPAY_SECRET_KEY", "dev-only-change-me")      # signs login tokens
ADMIN_KEY = os.getenv("UPAY_ADMIN_KEY", "dev-admin-key")             # sent as X-Admin-Key by the admin console
DEMO_MODE = os.getenv("UPAY_DEMO_MODE", "1") == "1"                  # /api/auth/demo + add_money. MUST be 0 in production
TOKEN_TTL_S = int(os.getenv("UPAY_TOKEN_TTL_S", str(7 * 24 * 3600)))
SCHEDULER_INTERVAL_S = float(os.getenv("UPAY_SCHEDULER_INTERVAL_S", "15"))
CORS_ORIGINS = [o for o in os.getenv("UPAY_CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",") if o]

# business rules (same numbers as the demo app)
DAILY_LIMIT = Decimal("50000")
MONTHLY_LIMIT = Decimal("200000")
CASHOUT_FEE = Decimal("0.0185")
STUDENT_FEE_FACTOR = Decimal("0.8")          # student: 20% off the cash-out fee
UNDO_WINDOW_MS = 120_000                     # wrong-number cancel window: 2 minutes
UNDO_MAX_PER_DAY = 3
PIN_MAX_FAILS = 3
PIN_LOCK_MS = 60_000
GUARDIAN_STATEMENT_ROWS = 15
TZ_OFFSET_MIN = 360                          # Asia/Dhaka: day and month limits roll over at local midnight
PIN_ITERATIONS = 200_000

# Referral: a new customer who registers with an existing customer's code (UP + phone without the leading 01) gets REFERRAL_BONUS,
# and so does the referrer, up to REFERRAL_MAX_PER_REFERRER bonuses per referrer. Paid at registration, in the same transaction.
REFERRAL_BONUS = Decimal(os.getenv("UPAY_REFERRAL_BONUS", "50"))
REFERRAL_MAX_PER_REFERRER = int(os.getenv("UPAY_REFERRAL_MAX", "10"))

# SMS OTP (phone proof). Real SMS needs a provider: set UPAY_SMS_WEBHOOK_URL (POST {"to","text"}); without it the code is only logged
# (and returned in the response when DEMO_MODE=1 so the demo works with no SMS account).
SMS_WEBHOOK_URL = os.getenv("UPAY_SMS_WEBHOOK_URL", "")
OTP_TTL_S = int(os.getenv("UPAY_OTP_TTL_S", "120"))
OTP_MAX_TRIES = 5
OTP_RESEND_S = 30
OTP_MAX_SENDS_PER_HOUR = 5
OTP_TOKEN_TTL_S = 300


def otp_required() -> bool:
    """Register and login need a verified OTP. Read at call time so tests can switch it. Only turn off for local development."""
    return os.getenv("UPAY_OTP_REQUIRED", "1") == "1"
