# upay Support Suite (plain HTML + CSS + JS)

Files
- index.html  customer app (wallet + Customer Service: live chat, email, complaint with photo/voice)
- admin.html  admin console (live chat inbox with AI analysis, emails, complaints with photo/voice playback, customers, transactions, FAQ, policies, announcements)
- style.css   all styles (includes print layout for the statement)
- core.js     shared helpers, Bangla/English dictionary, student-account defaults
- ai.js       support assistant (intent, redaction, FAQ match)
- db.js       storage (localStorage + cross-tab sync + atomic inc). Replace makeDb() with a real API
- customer.js wallet app (payments, PIN, limits, student plan, guardian, split, support)
- admin.js    admin console
- app.js      boot only (picks admin or customer)
- ../tests/   browser tests (see Tests below)

Run
Best: serve the folder, then open both pages in two tabs.
    python3 -m http.server 8000
    http://localhost:8000/index.html   (customer)
    http://localhost:8000/admin.html   (admin)
Chrome can also open the files directly (double click). Firefox needs the local server.

Voice recording needs microphone permission (works on localhost or https).

More customers: index.html?u=rahim&n=Rahim  (each ?u= is a separate customer)

Data lives in the browser (localStorage) and syncs between tabs on the same browser.
To go multi-device, replace makeDb() in db.js with calls to a backend (FastAPI + PostgreSQL).
All data is synthetic. Reply texts are samples, replace them with upay-approved wording (KB in app.js).

Language
- More > Language switches the whole customer app between Bangla and English (saved in the browser, page reloads).
- The admin console is always English. Bangla texts stored by the app (complaint categories, system messages) are shown in English there.

Account types (More > Account Type)
- Personal: default.
- Islamic: customer can switch directly.
- Student: needs admin approval. The customer fills the form, a request appears in admin > Student accounts, admin approves or rejects (a note is required to reject), and the customer sees the result in the app.
- Admin > Student accounts > Application rules: edit the guidelines (English and Bangla), accepted email domains (default: edu, ac) and which items are required (edu email, university name, student ID number, ID card photo, selfie with ID).
- NOTE: this is a browser-only demo, so the approval is not enforced by a server. For production, check acct/studentOK on the backend.

Student benefits (demo rules, edit constants in app.js)
- Cash Out fee: base 1.85%, verified student accounts get 20% off the fee (feeOf). Send Money fee: 0.
- History: search by phone/name/transaction ID; each row shows day, date, time, phone, receiver name (from saved accounts) and transaction ID.
- More > Student Plan (verified students only): money buckets (set money aside per category, pay from a bucket) and auto transfer (saved account + date/time; sends automatically when money arrives).

Round 2 features
- Every wallet gets a demo phone number (More > profile). Send Money to another wallet's number credits that user and shows their real name.
- Wrong-number protection: Send Money shows recipient name (or a warning if not found) before sending, then a 2-minute Cancel banner that returns the money if the recipient has not spent it.
- Guardian Link (More): a student adds a guardian's number, guardian approves from the bell, then can send money into a student's bucket and view their last 15 transactions.
- Bill Split (home grid): enter total + friends' numbers; each gets a request (bell) to Pay or decline.
- Auto transfer can repeat monthly; History page has a This-month summary by category.
- Needs 2+ wallets (open the app with different ?u= users) to try guardian / split / send between users.

Round 3 (safety, limits, statement)
- Atomic money: every balance change uses db inc() (reads the latest stored value, checks, writes in one locked step), so two tabs/devices can no longer overwrite each other. It also refuses overdraft and debits on frozen wallets. Admin adjustments and reversals use it too. On a real backend this must be a database transaction.
- PIN: first payment asks you to set a 4-digit PIN; every outgoing payment, bill-split payment, guardian send and auto-transfer creation asks for it. 3 wrong tries lock PIN entry for 60 s. More > Change PIN works. Stored as a salted hash in the wallet (demo grade, verify on the server in production).
- Limits: daily 50,000 and monthly 200,000 are enforced on every outgoing payment (also auto-transfers). Account > Transaction Limit shows usage. Change LIM in customer.js.
- Cancel (wrong number): at most 3 cancellations per 24 h per wallet, and only if the recipient still has the money (checked atomically).
- Bill split: each friend pays floor(total / (friends+1)), the remainder stays with you, so requests never add up to more than the bill. Duplicate numbers are ignored. Paying twice is blocked.
- Guardian: when a guardian opens the student's statement the student gets a notification and can remove the link (Guardian Link > x).
- Statement: each row shows balance after the transaction. History has CSV export (what the filter/search shows, opens correctly in Excel with Bangla) and PDF / Print (browser print dialog > Save as PDF).
- Demo tools (More > Demo tools): open test users in new tabs (rahim, karim, abbu, nusrat), make yourself a verified student, clear your PIN. Remove this row before production.

Known limits (need a backend)
- Auto transfer only fires while the app is open (on open, when money arrives, and every 30 s). A server scheduler is needed for "sends even when the app is closed".
- Student approval, PIN, limits and balances all live in the browser, so a technical user can change them. Enforce all of them on the server.
- Bangla/English still works by matching Bangla text against the dictionary in core.js; a new Bangla string needs an entry there or it stays Bangla in English mode (strings built with L(bn,en) do not need one).

Tests
    python3 -m http.server 8765 --directory upay-support-suite &
    python3 tests/test_upay.py            # all (includes t_impact_tab), or name a test: python3 tests/test_upay.py t_pin
Needs Python Playwright + Chromium. Covers: concurrent balance updates, fees (normal and student 20% off), free send + receiver name + wrong-number warning, limits, PIN set/wrong/lock, cancel rules, bill split + guardian notification, CSV export, admin load.

Round 4 (real backend: FastAPI + PostgreSQL)
- config.js: `window.UPAY_API=null` = browser-storage demo (as before). `window.UPAY_API=""` = talk to the backend on the same origin (the backend serves this folder and its own /config.js, so just open http://localhost:8000/).
- In backend mode the SERVER decides fees, balance, limits, PIN, student status and the 2-minute cancel. The browser cannot change a balance or approve a student (only the admin API can).
- Auto transfer now runs from a server scheduler, so it sends even when the app is closed.
- Chat / email / complaints / student applications are stored in Postgres (docs table). Appended messages are merged, so a stale agent reply cannot erase a newer customer message.
- Admin console (admin.html) asks for the admin key (UPAY_ADMIN_KEY).
- Setup, API list, tests and production checklist: see ../backend/README.md.

Round 5 (login / sign-up)
- auth.js shows a login page first: mobile number + 4-digit PIN. "Create a new account" asks name, mobile number, NID (10/13/17 digits), birth date, then a 4-digit PIN (typed twice). The PIN is the same PIN used to approve payments.
- More > Sign out returns to the login page. The session is kept in this browser until you sign out.
- Demo mode (UPAY_API=null): accounts live in localStorage (3 wrong PINs lock login for 1 minute). New accounts start with ৳0 (use Add Money to try). NID is not kept, only its last 4 digits.
- Backend mode: POST /api/auth/register and /api/auth/login (see backend/README.md). index.html?u=rahim still skips the login (demo tools and tests).

Round 6 (friendlier app)
- extras.js: first-time tour (3 slides, skipped for ?u= users), rotating safety tips on Home, More > Text size (normal / large / extra large), More > Install as an app (PWA: manifest.json, sw.js, icons).
- Favourites: Send Money > star a recipient; starred people show as chips on top of the page (Round 7: stored on the server in backend mode, see below).
- Receipt: History > tap a transaction > picture receipt > Share (phone share sheet, or download on desktop).
- Refer a friend: code = UP + your number (More > Refer, or the home tile). Demo mode: sign up with the code and both wallets get 50. Backend mode: both get 50 at registration (server rule, max 10 per referrer, see backend/README.md).

Round 7 (settings that follow you, operator hint, reminders, saved billers, lost phone)
- Favourites, profile photo, reminders and saved billers: in backend mode they are stored on the server (table `prefs`), so a new phone or a cleared browser gets them back after login. The phone keeps a local copy so the app also opens offline. The first time a phone connects, whatever it already had is uploaded once; after that the server copy wins. Demo mode (UPAY_API=null) keeps them in the browser as before.
- Recharge: the number's prefix (013/017 Grameenphone, 014/019 Banglalink, 016/018 Robi, 015 Teletalk) shows the operator under the number box. It is only a hint: a ported number can belong to another operator, and nothing is sent to an operator because there is no recharge provider connected yet. Prefix table: `OPS` in core.js.
- Pay Bill > Saved billers: the customer saves their own bill account (type from the existing list + account/meter number + a name) and picks it next time. There is no built-in directory of billers.
- More > Monthly reminders: name + day of the month (1-28) + optional amount + optional saved biller. It appears on Home from 2 days before the day until the customer taps Done for that month. A reminder created after its day has passed starts next month. It is only visible when the app is open, there is no push notification.
- More > Lost your phone? Freeze: the customer enters the PIN and the wallet is frozen (no send, bill, cash out, split, auto transfer). It also works from another phone after logging in with number + PIN; the login page says so. Only an admin can unfreeze (Admin > Customers > Unfreeze), after checking who is asking. The admin list shows "Frozen (by customer)".
- Not built (needs a decision or an outside service): SMS OTP, NID photo auto-fill, face or fingerprint login, a biller directory, real operator recharge.
- Tests: `python3 tests/test_upay.py` (demo mode) and, with the backend running on :8000, `python3 tests/test_backend_ui.py` (checks that a fresh browser gets the favourites, photo, reminders and billers back, and that freeze reaches the server).

Round 8 (measured impact)
- Admin > Impact: live numbers computed from the ledger, wallets, student requests, chats and complaints: wrong-number sends cancelled and money returned, student 20% fee discount saved (paid fee / 4), bucket users and bucket payments, student approval rate and average decision time, active wallets, assistant-answered chats, resolved complaints. "Download impact report (CSV)" exports them.
- Customer > History > This month: "Your savings" shows the student discount and wrong-send money returned.
- In demo mode the data is synthetic; on the backend the same screen reads the real ledger.

Round 9 (demo-ready)
- Admin > Impact > "Load sample data (demo)" fills the console with clearly synthetic customers, transactions, cancels, student requests, chats and complaints (all ids start with demo_), so the Impact numbers are not empty when someone opens it. "Remove sample data" deletes only those rows. Hidden in backend mode.
- Admin > Impact now starts with a "Before vs after" card (worked examples from the app rules).
- Sample-data numbers are synthetic. Do not present them as real results.

Round 10 (on-device smart checks, improved)
- ai.js `riskCheck`: before a Send Money is confirmed, the number and amount are scored against the customer's own history and favourites. Signals: one digit away from someone they already pay (typo or swapped digits, shows who), not found on upay, never paid before (more if the amount is large), cancelled before, amount 3x or more above their usual send (median, so one big payment does not hide the next), most of the balance, 3+ sends in 10 minutes, late night. Medium/high shows a "Safety check" box with reasons and what to do. It only advises: limits, PIN and cancel are still enforced by the server.
- ai.js `forecast`: History > This month > "Money forecast": recent days count more (half-life 5 days), one-off spikes are capped, spendable money = free balance (buckets excluded) minus unpaid reminders this month, shows how many days it lasts and the safe amount per day until month end, and says when there is little history.
- Both run on the phone with no network call and list their reasons. They are statistics and rules, not a trained model or an LLM. Test: t_smart_checks.

Round 11 (security and responsible AI, from judge feedback)
- SMS OTP: sign-up and login now need a 6-digit code after the number (and PIN). Server rules (backend/app/otp.py): code lives 2 min, 5 wrong tries kill it, resend after 30 s, max 5 codes per number per hour, only an HMAC of the code is stored. A verified code becomes a single-use otp_token (5 min, tied to the number and purpose) that /api/auth/register and /api/auth/login require (UPAY_OTP_REQUIRED=1 is the default). Login answers the same for known and unknown numbers (no account probing).
- No SMS provider is connected. Set UPAY_SMS_WEBHOOK_URL (POST {"to","text"}) to send real SMS. Without it the code is only logged, and when UPAY_DEMO_MODE=1 the API/app show it in a "Demo SMS" box so the demo works. With UPAY_DEMO_MODE=0 the code is never returned.
- Browser demo mode (UPAY_API=null): the code is made in the browser and shown in the Demo SMS box. This is a simulation, not security. A "DEMO MODE" badge is shown at the bottom of the app.
- More > "AI and your data": plain-language panel (where smart checks are used, they are rules/statistics not a trained model, they only advise, what stays on the phone, what is masked, how to reach a human). The Safety check box has a helpful / not helpful button (stored in table ai_feedback in backend mode).
- Admin > "Security & AI": list of controls, customer feedback counts per smart check, and the audit log (logins, sign-ups, freeze/unfreeze, student approval, balance adjust; never PINs, codes or full NIDs). API: GET /api/admin/audit, GET /api/admin/ai-feedback, POST /api/ai/feedback.
- Tests: backend tests/test_api.py TestOtp (OTP required, single use, 5 tries, other number's token refused, resend limit, audit, feedback); browser t_otp_signup and t_ai_panel.
- Still not done: a real SMS provider and real NID/KYC check (needs outside services), device binding so trusted phones skip the code.
