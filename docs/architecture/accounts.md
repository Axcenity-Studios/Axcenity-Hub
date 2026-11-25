# Accounts and sign-in security

Read this before touching `accounts/`, the allauth settings, sessions, rate limits or
production settings. Templates and the app shell: [../frontend/app-shell.md](../frontend/app-shell.md).
Linking a GitHub account (`GitHubLink`, `crypto.py`, `github.py`): [github-linking.md](github-linking.md).

django-allauth (`allauth.account`, `allauth.mfa`) runs registration, sign-in, sign-out,
email verification, password reset and two-factor sign-in. The `accounts` app adds the
Hub's policy around it:

| Module | Does |
|---|---|
| `models.py` | `Profile` (display name, bio, photo; one per user, made by `signals.create_profile`), `AuthAttempt` (the rate-limit backstop's rows) |
| `avatars.py` | Profile photos: `check` (an upload's rules) and `process` (the one image the Hub keeps) |
| `stages.py`, `adapter.py` | The verification policy (below); `AccountAdapter`, `MFAAdapter` (QR code with its own white paper) |
| `access.py` | The contribution gate: `has_verified_email`, `ensure_can_contribute`, `VerifiedEmailRequiredMixin` |
| `integrity.py` | Case-insensitive unique indexes and the duplicate check migration 0002 runs first |
| `forms.py` | allauth's forms plus the backstop, Turnstile and the reset honeypot; `ProfileForm` |
| `throttle.py`, `turnstile.py` | The database rate-limit backstop; the Cloudflare Turnstile client |
| `middleware.py` | `SessionAgeMiddleware`: idle and absolute session limits |
| `views.py`, `urls.py`, `strings.py` | Profile, email status and verify pages; copy as data |

## Profile photos

`ProfileForm` takes a photo (`photo`, not a model field) and a `remove_photo` box.

- **Checked before decoding** (`avatars.check`): at most 2 MB, read by Pillow as PNG, JPEG,
  WebP or GIF (anything else, or anything it can't read, is refused), and 64 to 4096 pixels
  on each side, from the header. Each refusal is a form error in plain words.
- **Remade, never kept** (`avatars.process`, run in `clean_photo` so a file that won't
  decode is a form error, not a failed save): the first frame, turned upright by its EXIF,
  cropped to a centred square, scaled to 256 px and saved as WebP. The stored file carries
  no metadata and none of the upload's bytes, under a fresh random name
  (`avatars/<uuid>.webp`), so a new photo is never served from a cache.
- **No file left behind:** replacing or removing a photo deletes the old file once the
  profile is saved; deleting a profile (or its user) deletes its photo
  (`signals.delete_photo`).
- **Storage:** Django's default storage under `MEDIA_ROOT` (`DJANGO_MEDIA_ROOT`). A
  development server serves `/media/` (`config/media.py`, only while `DEBUG` is on);
  production's web server serves the folder. Photos are public: other members see them.

## Email verification policy

**Unverified accounts can sign in, but can't post, create projects or submit reports
until their email is verified.**

- allauth runs `ACCOUNT_EMAIL_VERIFICATION = "mandatory"`. It's the only mode in which
  signup is both enumeration-safe and email-unique: a signup with a taken address (any
  case) creates nothing, ends on the same "check your inbox" page as a new one, and the
  owner gets an "Account Already Exists" email. (`optional` would have to reveal the
  conflict; `PREVENT_ENUMERATION = "strict"` would let accounts share an address.)
- Mandatory would also block an unverified password login. `AccountAdapter.get_login_stages()`
  (allauth's documented hook) swaps `EmailVerificationStage` for
  `SignupVerificationStage`, which applies allauth's mandatory handling only when
  `login.signup` is true. If an allauth upgrade removes that stage, the adapter raises.
- The gate: views that contribute mix in `VerifiedEmailRequiredMixin` (anonymous → sign
  in; unverified → `accounts:verify_email`, the link re-sent, the view never runs);
  services call `ensure_can_contribute(user)` (raises `EmailNotVerified`).
- allauth's verification-email cooldown is per address (`confirm_email`: 1 per 3 min).
  Within it nothing is sent, so allauth's "Confirmation email sent" message would appear
  only for unused addresses; `AccountAdapter.add_message` drops it at signup.
- `test_signup_and_password_login_hold_the_whole_verification_policy` drives all of this
  through allauth's real views.

## Usernames and emails

- Sign-in is by **email** only (one key per account for the rate limits). Usernames are
  public handles: 3–30 letters, digits, `-` or `_` (`validators.py`), a reserved list in
  `ACCOUNT_USERNAME_BLACKLIST`, stored as typed. Emails are stored lower-cased.
- **Unique whatever the case**, three layers: allauth's forms, the admin's forms
  (`admin.CaseInsensitiveUniqueMixin`), and unique indexes on `LOWER(auth_user.username)`,
  `LOWER(auth_user.email)` (non-blank) and `LOWER(account_emailaddress.email)`.
- Migration 0002 first runs `integrity.check_no_case_conflicts`: if rows already differ
  only in case it stops, naming each (table, id, value), and changes nothing. Fix them by
  hand, then migrate again. Nothing is ever deleted or merged automatically.
- One address per account: the Hub's `EmailView` replaces allauth's `account_email` page
  (status and resend only), because allauth's add-email form would accept another
  account's address unverified.

## Sessions and cookies

- Session cookie HttpOnly; session, CSRF and theme cookies `SameSite=Lax`, and `Secure`
  in production.
- A session ends after **24 hours idle** (`SESSION_IDLE_TIMEOUT`) or **14 days after
  sign-in** (`SESSION_ABSOLUTE_TIMEOUT`), enforced server-side by `SessionAgeMiddleware`.
  Without "Remember me" the cookie also ends with the browser.
- The session key changes at sign-in (Django), on a password change
  (`update_session_auth_hash`), and when two-factor is turned on or off or recovery codes
  are regenerated (`signals.rotate_session_on_security_change`).
- Sign-out is a POST and deletes the session row; a GET only shows the confirmation.

## Password reset

Links last **one hour** (`PASSWORD_RESET_TIMEOUT`), work once, and die with any password
change (Django's token includes the password hash). Opening a link moves the token into
the session and redirects to a token-free URL; `Referrer-Policy: same-origin` and no
off-site resources on that page keep it from leaking. `ACCOUNT_LOGIN_ON_PASSWORD_RESET`
is off: the member signs in afterwards (two-factor still applies).

## Rate limits: two layers

1. **Cache** (allauth, `ACCOUNT_RATE_LIMITS`): failed sign-ins 10/min per IP and 5 per
   5 min per account; signups 10/hour per IP; reset requests 10/hour per IP, 3/hour per
   address; two-factor codes share the per-account failed-login limit.
2. **Database backstop** (`throttle.LIMITS`, `AuthAttempt` rows), looser and longer:
   failed sign-ins, signups, reset requests and failed codes, per IP and per account. It
   still holds when the cache is cleared or isn't shared. Rows store HMAC-SHA256 hashes
   (keyed from `SECRET_KEY`), never an address or IP, and are dropped after a day.

Every refusal reads the same whether or not the account exists. Behind a proxy set
`DJANGO_BEHIND_PROXY` so allauth reads the client IP from `X-Forwarded-For`
(`ALLAUTH_TRUSTED_PROXY_COUNT`).

**Production cache:** `DatabaseCache` (table `axcenity_cache`; run
`manage.py createcachetable` once), or Redis when `DJANGO_REDIS_URL` is set. Either is
shared by every worker, so the cache limits and the release list's cache hold across
processes. The rate-limit tests run on both local memory and the database cache.

## Enumeration and timing

Login, signup and reset give the same response whether or not the account exists. For an
unknown email allauth's backend still hashes the password once, as for a wrong one
(tested by counting hashes). A reset for an unknown address sends an "unknown account"
email, so each request sends exactly one.

## Two-factor sign-in

An authenticator app (TOTP) with ten one-time recovery codes (`MFA_SUPPORTED_TYPES`).
Enrolling, regenerating codes and turning it off need a fresh re-authentication
(allauth only accepts an explicit one, not the sign-in itself). After the password, the
member isn't signed in until the code step passes, so no page can be reached around it.
An unverified address can't enrol (`MFA_ALLOW_UNVERIFIED_EMAIL` off).

## Bots: honeypots and Turnstile

- Honeypots named `website` on signup (allauth's) and the reset request
  (`forms.ResetPasswordForm`): a filled one gets the normal success page and nothing is
  created or sent.
- **Turnstile** (`turnstile.verify`) on signup and the reset request, only when both
  `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` are set. It fails closed (no token, a
  refusal, a timeout or a bad reply refuses the form) and is never the only check: the
  honeypot and both rate-limit layers run whatever it says. Cloudflare's test keys
  (site `1x00000000000000000000AA`, secret `1x0000000000000000000000000000000AA`) work
  on localhost; tests mock siteverify with `responses`.

## Production settings

Production is `DJANGO_DEBUG=false`. Settings then refuse to load without a 50+ character
`DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`, and turn on the SSL redirect, HSTS (a
year, subdomains, preload), secure cookies, the shared cache and SMTP email. Always on:
`X-Frame-Options: DENY`, `nosniff`, `Referrer-Policy: same-origin`, COOP same-origin.
`manage.py check --deploy --fail-level WARNING` passes (tested). Variables:
[../ARCHITECTURE.md](../ARCHITECTURE.md#settings).
