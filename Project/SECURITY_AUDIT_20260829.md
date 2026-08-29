# CareerAI regression and security audit — 29 Aug 2026

## Included fixes

- Password reset now persists the new Django password hash, signs out all existing sessions for that account, and logs out the recovery browser. A valid new password works; the old password does not.
- Forgot-password responses no longer reveal whether an email address is registered. New registrations require a valid, unique email address.
- The dashboard `Performance` item now opens `/performance/`, not Career Guidance. The new protected page only reads the signed-in user's completed interviews and shows score trend, averages, best/latest score, category averages, and recent report links.
- AI Interview and Career Guidance navigation now link to the same Performance page.
- Production settings now reject the development secret when `DJANGO_DEBUG=0`, enable secure cookies/HSTS, deny framing, and redirect HTTP to HTTPS in production by default. Local HTTP remains usable with `DJANGO_DEBUG=1`.
- `media/` is ignored by Git so uploaded resumes are not accidentally committed.
- Gemini authentication now uses the `x-goog-api-key` header instead of putting the key in the request URL/log line.

## Checks run

All of the following passed against the project source:

| Check | Result |
| --- | --- |
| `python manage.py check` | Passed |
| `python manage.py makemigrations --check --dry-run` | No changes detected |
| `python manage.py test users` | 9 tests passed |
| `python -m py_compile` for project Python files | Passed |
| `node --check users/static/users/landing.js` | Passed |
| Anonymous dashboard access | Redirects to `/login/?next=/dashboard/` |
| Password reset with valid OTP | New password accepted; old password rejected; stale session rejected |
| Performance access | User-owned data only; another user's interview is not shown |
| Interview counts | Easy/medium are clamped to 15–30; hard is fixed at 40 |
| Interview report HTML/PDF | Both returned successfully with a completed sample session |
| `python manage.py check --deploy` with a long secret and `DJANGO_DEBUG=0` | Passed with no warnings |

## Required local upgrade step

The source includes migration `users.0006_interviewfeedback_professional_answers`. If the database used by the local server shows it as unapplied, run these commands from the folder containing `manage.py`:

```powershell
python manage.py migrate
python manage.py showmigrations users
```

The last migration must show `[X] 0006_interviewfeedback_professional_answers`. Do not copy or commit `db.sqlite3` or uploaded files from `media/`; they can contain personal resume data.

## Remaining production hardening items

1. Login, OTP, resend, forgot-password, and interview APIs do not yet have a shared IP/account rate limiter. The OTP has expiry, hashing, attempt limits, and resend cooldown, but an attacker can create many sessions. Add cache-backed throttling before public launch.
2. Keep HTTPS enabled at the hosting/reverse-proxy layer. If a trusted proxy terminates TLS, configure its forwarded-protocol handling correctly; only override `SECURE_SSL_REDIRECT` when the proxy already performs the redirect.
3. When `ENABLE_AI=true`, resume text is sent to the configured Gemini/OpenRouter endpoint. Tell users this clearly and keep the default local mode for private/offline practice.
4. PDF signature, size, and extension checks are present, but a production upload pipeline should add malware scanning and resource/time limits for hostile PDFs.
5. The uploaded archive contained `.git`, `db.sqlite3`, and resume PDFs. Never publish those artifacts. If a real API key or production secret was ever committed to Git history, revoke and rotate it.
6. Existing databases may contain duplicate/blank emails created before the new registration validation. Review those accounts before relying on email recovery.

No `.env` file or secret value was required or read for this audit.
