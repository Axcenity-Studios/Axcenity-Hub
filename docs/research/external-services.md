# External services for Axcenity Hub

All sources checked **2026-11-23** unless noted. Prices and free tiers change; re-check before you sign up.

**Purpose.** The project proposal (sections 3–5) names five external dependencies: GitHub APIs and OAuth, SendGrid,
Cloudflare Turnstile, Cloudflare infrastructure and R2, and a SQLite→MySQL database path. This note checks each one
against primary sources for fit, current free tiers, setup effort for a beginner, and how to keep `pytest` fully
offline. It ends with a recommendation for each. The stack constraints are uv only (no pip/npm), tests never touch
the network, and free tiers come first. Where a primary source was unreachable or unclear, the note says so.

## Summary

| Service | Recommendation | Free tier (verified) | Needs domain? | Test strategy |
|---|---|---|---|---|
| GitHub REST/GraphQL | **REST** via `requests`, ETag caching plus webhooks; GraphQL not needed yet | 60 req/h unauth; 5,000 req/h per user token; installation tokens 5,000 up to 12,500 | No | `responses` + autouse network guard; fixture JSON taken from real release payloads |
| GitHub sign-in / linking | **django-allauth** GitHub provider for login, plus a **GitHub App** for repo access (OAuth App with no scopes is the simpler fallback) | Free | No (localhost callback works in dev) | Don't drive OAuth in tests: create `SocialAccount` rows directly; mock token and permission endpoints with `responses` |
| Transactional email | **Drop SendGrid.** Use Django's console backend now; pick **Resend** or **Postmark** through django-anymail once you own the domain | SendGrid: no free plan, only a 60-day trial. Resend: 3,000/mo, 100/day. Postmark: 100/mo | **Yes** for every provider to send to real users | locmem backend + `mailoutbox` (pytest-django) |
| Human verification | **Honeypot + server-side rate limits first.** Add Turnstile only on anonymous forms | Turnstile: free, unlimited challenges, 20 widgets | No (works on any hostname you list) | Turnstile dummy keys + `responses` mock of siteverify |
| Cloudflare DNS/WAF | Defer until the domain is bought; the free plan is enough | $0 plan: DNS, CDN, SSL, DDoS, Free Managed Ruleset, 1 rate-limit rule | **Yes** (nameserver change) | Not testable in pytest; nothing to mock |
| Cloudflare R2 | Out of scope per proposal; design for `STORAGES` so it is a config swap | 10 GB-month, 1M Class A, 10M Class B, free egress | Only for a production public URL (r2.dev is dev-only) | `FileSystemStorage`/`InMemoryStorage` in tests; `moto` if S3 code is ever written |
| Database | **SQLite** for dev/tests. For production, prefer **PostgreSQL** over MySQL (psycopg binary wheel works with uv; mysqlclient needs C headers) | Neon Postgres: 1 GB/project, no card (§5c) | No | pytest-django test DB (SQLite) |

## Open questions for the author

1. **Login vs. linking:** Is GitHub a *sign-in method* (create an account from GitHub), or only a *link* on an existing
   Hub account? This changes allauth settings (`SOCIALACCOUNT_EMAIL_AUTHENTICATION`, auto-signup).
2. **Private repos:** Must the Hub ever read *private* repos? If not, an OAuth App with **no scope** gives read-only
   public data and needs no GitHub App ([scopes](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps)).
   If yes, a GitHub App avoids the all-or-nothing `repo` scope.
3. **Download page shows prereleases:** Every engine release is a prerelease, so `GET /releases/latest` returns
   **404** today (verified 2026-11-23, below). Should `/download/` show the newest prerelease, with an "alpha" banner?
4. **Hosting target:** Where will production run? The answer decides the database (managed Postgres vs. MySQL), the
   cache backend for rate limiting (django-ratelimit needs Redis or Memcached for correctness), and whether webhooks
   can reach the app at all.
5. **Domain timing:** Email to real users, Cloudflare DNS/WAF, and an R2 custom domain all wait on the ~$12/yr domain.
   Is buying it in scope for the course timeline?
6. **Anonymous submissions:** Proposal open question 4 says "anonymous submissions", but every workflow table row
   lists *registered users*. Is there any anonymous write form (contact, bug report without login)? If not,
   Turnstile adds little.
7. **MySQL requirement:** Is MySQL a course requirement, or was it a placeholder for "a real server database"?

---

## 1. GitHub REST + GraphQL APIs

**What it does for the Hub.** Project Management ("connect GitHub repos"), GitHub Synchronization (webhooks, caching,
rate limits: proposal §4 unresolved decisions), and the public `/download/` page listing engine builds from
`Axcenity-Studios/Axcenity-Engine` releases.

**Verdict:** Feasible. REST covers every need. The download page works with no token at all.

### Releases for `/download/`
- `GET /repos/{owner}/{repo}/releases` (paginated, `per_page` max 100); `GET .../releases/latest`;
  `GET .../releases/tags/{tag}` ([releases API](https://docs.github.com/en/rest/releases/releases)).
- **`/releases/latest` skips prereleases:** "The latest release is the most recent non-prerelease, non-draft
  release" ([same page](https://docs.github.com/en/rest/releases/releases)). Live check (unauthenticated, 2026-11-23):
  `api.github.com/repos/Axcenity-Studios/Axcenity-Engine/releases/latest` returned **404**. The list endpoint returned
  `v0.3.0-alpha.1`, `v0.2.0-alpha.1`, and `v0.1.0-alpha.3`, all `prerelease: true`. **Use the list endpoint and pick the
  first non-draft entry.**
- Useful fields: release `tag_name`, `name`, `prerelease`, `draft`, `published_at`, `body`, `assets[]`. Asset `name`,
  `size`, `content_type`, `download_count`, `browser_download_url`, `digest`
  ([releases API](https://docs.github.com/en/rest/releases/releases)). In the live response every asset had
  `digest: "sha256:…"`, so the page can show checksums without downloading `SHA256SUMS.txt`. Assets include
  `.AppImage/.deb/.rpm/.pkg.tar.zst/.tar.gz` (Linux), `.dmg` (macOS), `.exe` and `-update.zip` (Windows), plus
  `axcenity-release.json(.minisig)` and `axcenity-history.json` from v0.2.0 on. Group them by OS with a filename pattern.
- Unauthenticated reads worked in the live check (`x-ratelimit-limit: 60`). The docs don't state explicitly that
  release endpoints accept anonymous requests.
- Send a `User-Agent`: "Requests without a valid `User-Agent` header will be rejected." Pin `X-GitHub-Api-Version`
  ([troubleshooting](https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api)).

### Rate limits ([REST rate limits](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api))
| Credential | Primary limit |
|---|---|
| Unauthenticated | 60 req/h per IP |
| Personal access token | 5,000 req/h |
| OAuth App user token | user's 5,000 req/h, **shared** across all of that user's apps/tokens |
| OAuth App client ID+secret (public data) | 5,000 req/h per app |
| GitHub App installation token | 5,000 req/h, +50 per repo over 20 and per org user over 20, max 12,500 |
| GitHub App user token | user's 5,000 req/h |

Secondary limits: at most 100 concurrent requests, 900 points/min for REST, about 80 content-creating requests per
minute and 500 per hour ([same page](https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api)).
GraphQL has a separate budget of 5,000 **points**/h per user. Every connection needs `first`/`last` set to 1–100
([GraphQL limits](https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api)).

### Conditional requests
Store the `etag` and send `if-none-match`. A `304` "does not count against your primary rate limit", **but only when
the request was made "while correctly authorized with an `Authorization` header"**
([best practices](https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api)).
So unauthenticated ETag polling still costs requests. Have the server call the release list with an app or client
credential and cache the result (Django cache, TTL around 10 min). A spike of page views then never multiplies API
calls. The same page says to "subscribe to webhook events instead of polling".

### Webhooks
- Relevant events: `release` (`published`, `prereleased`, `edited`, `deleted`, …; needs Contents: read), `push`
  (Contents: read), `repository` (`renamed`, `transferred`, `deleted`, …; Metadata: read), `member` and `membership`
  (org Members: read). GitHub Apps also get `installation` and `installation_repositories` automatically
  ([events](https://docs.github.com/en/webhooks/webhook-events-and-payloads)). Payloads over 25 MB are not delivered.
- Headers: `X-GitHub-Event`, `X-GitHub-Delivery` (GUID: store it to dedupe), `X-Hub-Signature-256`.
- Verification: HMAC-SHA256 of the raw body with the webhook secret, sent as `sha256=<hex>`. Compare in constant time
  (`hmac.compare_digest`). GitHub publishes a test vector: secret `It's a Secret to Everybody`, payload
  `Hello, World!`, signature `sha256=757107ea0eb2509fc211221cce984b8a37570b6d7586c22c46f4379c8b043e17`
  ([validating deliveries](https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries)).
  Use it verbatim as a unit test.
- A GitHub App has one webhook for every repo it can access. An OAuth App needs a per-repo webhook created through the
  API, and those webhooks are not cleaned up automatically
  ([differences](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps)).

### REST vs GraphQL
Use **REST**. The Hub's calls are a few fixed shapes (releases, one repo, permission check). REST supports 304 caching
and `responses` mocks it with plain URLs. GraphQL needs authentication for every call. The docs only describe
authenticated use, and anonymous access is not stated
([forming calls](https://docs.github.com/en/graphql/guides/forming-calls-with-graphql)). It also makes mocks harder:
one URL, matched on the request body. Revisit GraphQL only if a page needs deeply nested data in one round trip.

**Beginner setup.** None for releases. For repo features, a GitHub App or OAuth App (§2) plus a webhook secret in an
env var. Webhooks need a publicly reachable URL, so local dev needs a tunnel. GitHub's "redeliver" button and recorded
payloads cover testing.

**Mocking.** Use `responses` (it mocks only `requests`, and an unmatched URL raises `ConnectionError`:
[responses](https://github.com/getsentry/responses)). Put it in a single `services/github.py` client. Tests:
(a) list releases → OS-grouped context; (b) 304 path returns the cached value; (c) 403 or 5xx falls back to the cache
and shows a "GitHub unavailable" note (proposal §5: "GitHub failures will not render … the site unusable");
(d) webhook view with good and bad signatures. Save one trimmed real `/releases` JSON as a fixture.

**Risks → mitigations.** Rate exhaustion → server-side cache, authenticated ETag requests, per-user throttle.
Outage → serve the last cached list, with a `fetched_at` timestamp. Webhook spoofing → HMAC check before parsing.
Duplicate delivery → unique `delivery_id`. Prerelease-only repo → don't use `/latest`.

| Alternative | Note |
|---|---|
| GraphQL v4 | Requires a token for every call, point-based budget, harder to mock |
| PyGithub / githubkit | Extra dependency and abstraction; plain `requests` + `responses` is easier to test |
| Polling only | Simpler, but uses budget; GitHub recommends webhooks |

**Recommendation.** Use REST through a thin `requests`-based client with a fixed `User-Agent`, an API version header,
cached responses keyed by URL, and ETag revalidation using the app's credentials. The download page reads
`/releases?per_page=10`, skips drafts, and labels prereleases. Add a signed webhook endpoint for `release` events that
clears the cache, once the app has a public URL. Everything is mocked with `responses`, behind the autouse guard.

---

## 2. GitHub sign-in and account linking

**What it does for the Hub.** Proposal §3: "GitHub OAuth will be used to … connect their existing accounts". §2:
"GitHub repository permissions must be verified before repository-dependent operations". Open question 1: OAuth
scope and private repos.

**Verdict:** Feasible. The main decision is OAuth App vs. GitHub App.

### OAuth App vs GitHub App
- GitHub: "In general, GitHub Apps are preferred over OAuth apps"
  ([differences](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps)).
- **OAuth App scopes are coarse.** No scope gives "read-only access to public information". `public_repo` gives
  *read/write* on public repos. There is **no read-only private-repo scope**: private access means full `repo`
  ([scopes](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps)). OAuth tokens reach
  every repo the user can access and are long-lived by default.
- **GitHub App** permissions are fine-grained (e.g. Contents: read, Metadata: read only). The user chooses which repos
  to install the app on. Installation tokens expire after about 1 h
  ([differences](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps)).
  User access tokens (`ghu_`) expire after 8 h, refresh tokens (`ghr_`) after 6 months. A token "only has permissions
  that both the user and the app have". GitHub Apps do not use scopes
  ([user tokens](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)).
- Trade-off for a beginner: a GitHub App adds an install step, a private key (for installation tokens), and refresh
  handling. An OAuth App with no scopes is a 5-minute setup, but cannot see private repos.

### Verifying repo permission
- `GET /repos/{owner}/{repo}` with the *user's* token returns a `permissions` object (`admin`, `maintain`, `push`,
  `triage`, `pull`) for that user ([repos](https://docs.github.com/en/rest/repos/repos#get-a-repository)). This is the
  simplest check for "can this user link this repo": require `admin` (or `push`).
- `GET /repos/{owner}/{repo}/collaborators/{username}/permission` returns `permission` (admin/write/read/none) and
  `role_name` ([collaborators](https://docs.github.com/en/rest/collaborators/collaborators)). The docs say the
  "is collaborator" variant needs push access. Who may call the `/permission` variant is **ambiguous** in the docs.
- Keep Hub roles (Owner/Maintainer/Viewer) separate, as the proposal says. Check GitHub permission only at link time
  and before repo-dependent actions, and cache it briefly.

### Django libraries
| | django-allauth | social-auth-app-django |
|---|---|---|
| Latest (PyPI) | 65.22.1, 2026-11-13; Django 4.2–6.1; Py ≥3.11 ([PyPI](https://pypi.org/project/django-allauth/)) | 8.1.0, 2026-11-12; Django 5.2–6.1; Py ≥3.11 (PyPI JSON API) |
| GitHub | `github` provider; dev callback `http://127.0.0.1:8000/accounts/github/login/callback/`; `SCOPE` setting ([docs](https://docs.allauth.org/en/latest/socialaccount/providers/github.html)) | `GithubOAuth2`, `GithubOrganizationOAuth2`, `GithubTeamOAuth2`, and a dedicated **`GithubAppAuth`** ([docs](https://python-social-auth.readthedocs.io/en/latest/backends/github.html)) |
| Local accounts | Registration, email verification, password reset, and linking in one package | Social login only; local signup and reset come from Django's own views |
| Token storage | `SOCIALACCOUNT_STORE_TOKENS` (default `False`) ([config](https://docs.allauth.org/en/latest/socialaccount/configuration.html)) | Stored in `UserSocialAuth.extra_data` (not verified on a docs page this session) |

The allauth GitHub page doesn't mention GitHub Apps. GitHub Apps use the same `login/oauth/authorize` web flow, so
allauth's provider *should* work with a GitHub App's client ID and secret. That is **inferred, not confirmed by
allauth docs**, so test it early. Allauth does not refresh the 8-hour `ghu_` tokens for you.

**Mocking.** Don't run the OAuth dance in tests. Create `User` + `SocialAccount` (+ `SocialToken`) with factories, then
mock `api.github.com/repos/...` with `responses` for permission checks. One integration test can mock
`github.com/login/oauth/access_token` and `api.github.com/user` to cover the callback view.

**Risks → mitigations.** Over-broad `repo` scope scares users → GitHub App or no-scope OAuth. Email-collision account
takeover → keep `SOCIALACCOUNT_EMAIL_AUTHENTICATION=False` (docs: "Only set it to True if you are using providers that
can be fully trusted"). Token leakage → store tokens only when needed, never log them. Revoked access → treat a 401 or
404 from GitHub as "unlinked" and show a re-link prompt.

**Recommendation.** Use **django-allauth**. It also covers the proposal's register/login/password-recovery workflow, so
one library handles all of account management. Phase A: a GitHub **OAuth App with no scopes** for sign-in and linking,
with ownership checked through `GET /repos/{o}/{r}` → `permissions.admin` (public repos). Phase B, if private repos
matter: register a **GitHub App** (Contents: read, Metadata: read, webhook for `release`/`push`/`repository`), have
users install it on chosen repos, and use installation tokens for server sync. If allauth proves awkward with GitHub
App tokens, social-auth's `GithubAppAuth` is the documented fallback.

---

## 3. Transactional email (SendGrid and alternatives)

**What it does for the Hub.** Password reset and account recovery (proposal §3), and notifications.

**Verdict:** SendGrid is **no longer a free option**. Email to real users needs a domain with any provider. Develop
with Django's console backend until the domain exists.

### SendGrid status
- Twilio "retiring its Free Email API and Free Marketing Campaigns plan starting May 27, 2025". After 60 days, sending
  pauses unless the account upgrades ([Twilio changelog](https://www.twilio.com/en-us/changelog/sendgrid-free-plan)).
- New accounts get a "60 day timed free trial" capped at 100 emails/day. After it ends, "Any active email send
  integration using your account's API keys will stop sending messages"
  ([SendGrid support](https://support.sendgrid.com/hc/en-us/articles/35270136965403)).
- **django-anymail marks SendGrid "Unsupported since June 2025"** ("hasn't been tested against the live SendGrid API").
  It warns from 13.0.1 on ([anymail SendGrid](https://anymail.dev/en/stable/esps/sendgrid/)).
- Paid plan prices: **not verified**. `sendgrid.com/pricing` redirect-loops to a Twilio marketing page with no figures.

### Alternatives (all supported by django-anymail with "Full" status except SendGrid: [anymail ESPs](https://anymail.dev/en/stable/esps/))
| Provider | Free tier (verified 2026-11-23) | Domain needed to email real users? | Source |
|---|---|---|---|
| **Resend** | 3,000/mo, **100/day**, 3 domains, 30-day logs; Pro $20/mo for 50k | Yes. `resend.dev` "can only send emails to the email address associated with your Resend account" | [pricing](https://resend.com/pricing), [403 doc](https://resend.com/docs/knowledge-base/403-error-resend-dev-domain) |
| **Postmark** | 100/mo (Developer), up to 10 domains; Basic $15/mo for 10k | Yes. Before approval "you won't be able to send to any email address outside the domains you've added … and verified" | [pricing](https://postmarkapp.com/pricing), [approval](https://postmarkapp.com/support/article/1084-how-does-the-account-approval-process-work) |
| **Amazon SES** | No permanent free quota now: new AWS customers get up to $200 in Free Tier credits (use within 12 months); $0.10/1,000 | Sandbox: only to verified addresses, 200/24 h, 1/s; production access needs a website URL and review (≤96 h). A verified single address works as From | [pricing](https://aws.amazon.com/ses/pricing/), [sandbox](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html) |
| **Mailgun** | 100/day, 1 custom domain; Basic $15/mo for 10k | Probably (sandbox domain restricted to authorized recipients). **Help page 403, not verified** | [pricing](https://www.mailgun.com/pricing/) |
| **Brevo** | 300/day, "Sent with Brevo" sticker, 1 user | Not verified | **Help-center page 403'd; figures from a search snippet of** [help.brevo.com/…/208580669](https://help.brevo.com/hc/en-us/articles/208580669) |

### Dev and tests
- Django 6.1 adds the `MAILERS` setting. `EMAIL_BACKEND` and the `EMAIL_*` settings are **deprecated** and keep
  working (with warnings) until they are removed ([6.1 release notes](https://docs.djangoproject.com/en/stable/releases/6.1/)).
  Dev: `"django.core.mail.backends.console.EmailBackend"` prints mail to the terminal. Django's test runner
  automatically swaps in the locmem backend, and messages land in `django.core.mail.outbox`
  ([email docs](https://docs.djangoproject.com/en/stable/topics/email/)).
- pytest-django's `mailoutbox` fixture gives "a clean email outbox" per test
  ([helpers](https://pytest-django.readthedocs.io/en/latest/helpers.html)). Its docs don't name the backend, so set
  the locmem backend explicitly in the test settings to be safe.
- To assert Anymail-specific params, use `anymail.backends.test.EmailBackend`
  ([anymail test backend](https://anymail.dev/en/stable/tips/test_backend/)).

**Beginner setup (once the domain exists).** Create an account → add the domain → paste the SPF/DKIM (and
Return-Path/DMARC) records at the DNS host (Cloudflare) → wait for verification → API key in an env var →
`uv add django-anymail[resend]` → set the backend in `MAILERS`. About 1 hour.

**Risks → mitigations.** Free tiers vanish (SendGrid did) → Anymail means switching provider is a settings change.
No domain yet → console backend. Admin-editable keys (proposal §5) → read keys from env vars, not from the database.
A secret stored in a DB row is easy to leak through the admin or fixtures.

**Recommendation.** Replace SendGrid in the proposal. Code against Django's mail API only: `send_mail` and the
allauth/Django password-reset templates. Use console in dev and locmem in tests. Once the domain is bought, add
django-anymail with **Resend** (3,000/mo is plenty and setup is the simplest) or **Postmark** (best deliverability
reputation, but only 100/mo free). Either is one settings block. Note the reason for the change in the final report:
"SendGrid retired its free plan in 2025."

---

## 4. Cloudflare Turnstile (and alternatives)

**What it does for the Hub.** Proposal §5: "Cloudflare Turnstile will provide the additional protection". Open
question 4: verifying anonymous submissions.

**Verdict:** Feasible and free, but probably **not needed in phase 1**. All rate-limited forms in the workflow table
are for logged-in users, and per-user limits already stop abuse there. Signup and password reset are the real
anonymous targets.

### Facts
- Free plan: up to 20 widgets, 10 hostnames per widget, "Unlimited challenges", and Turnstile "can be used
  independently without requiring other Cloudflare services" ([plans](https://developers.cloudflare.com/turnstile/plans/)).
  So **no domain on Cloudflare is required**. You list the hostnames the widget may run on.
- Server flow: `POST https://challenges.cloudflare.com/turnstile/v0/siteverify` with `secret` and `response` (plus
  optional `remoteip` and `idempotency_key`). Tokens are valid for 300 s, single-use (`timeout-or-duplicate`), and at
  most 2048 chars. The response has `success`, `hostname`, `action`, and `error-codes`
  ([server-side validation](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)).
- **Test keys** ([testing](https://developers.cloudflare.com/turnstile/troubleshooting/testing/)):
  sitekeys `1x00000000000000000000AA` (pass, visible), `2x00000000000000000000AB` (fail),
  `1x00000000000000000000BB` / `2x00000000000000000000BB` (invisible pass/fail),
  `3x00000000000000000000FF` (forces an interactive challenge). Secrets `1x0000000000000000000000000000000AA` (pass),
  `2x0000000000000000000000000000000AA` (fail), `3x0000000000000000000000000000000AA` (`timeout-or-duplicate`).
  Dummy token `XXXX.DUMMY.TOKEN.XXXX`. The test keys work on localhost.
- Django packages: `django-turnstile` 0.1.3 lists only Django ≤4.0 classifiers (PyPI JSON API), which makes it a poor
  fit. Writing the ~20-line siteverify call yourself is simpler, and testing it is trivial.

### Alternatives
| Option | Free tier | Test keys | Notes |
|---|---|---|---|
| **Turnstile** | Free, unlimited | Yes (above) | No Cloudflare zone needed |
| hCaptcha | Free tier exists (limits **not stated** on [Pro page](https://www.hcaptcha.com/pro)); Pro $99/mo annual | sitekey `10000000-ffff-ffff-ffff-000000000001`, secret `0x0000000000000000000000000000000000000000` ([docs](https://docs.hcaptcha.com/)) | Users usually see a challenge on the free tier |
| reCAPTCHA | 10,000 assessments/month free ([FAQ](https://developers.google.com/recaptcha/docs/faq)) | v2 test sitekey `6LeIxAcTAAAAAJcZVRqyHh71UMIEGNQ_MXjiZKhI` | Google Cloud project; privacy concerns |
| Honeypot field + rate limiting | Free | n/a | Stops naive bots; no third party or JS |
| django-ratelimit 4.1.0 | Free | n/a | `@ratelimit(key="user_or_ip", rate="5/m", method="POST")` ([usage](https://django-ratelimit.readthedocs.io/en/stable/usage.html)). **Last release 2023-07** (PyPI). Needs Redis or Memcached; locmem and file caches aren't shared across processes, and the DB cache lacks atomic increments ([install](https://django-ratelimit.readthedocs.io/en/stable/installation.html)) |

**Rate limits as business rules.** "5 posts/day", "5 comments/minute", "5 projects/user", and "1 showcase/day" are
business rules, so enforce them as **DB count queries in model or services validation** (e.g. `ForumPost.objects.filter(
author=u, created__gte=now-1day).count() < 5`). Those are deterministic, testable with freezegun or `timezone` mocks,
and need no cache. Use django-ratelimit (or a DRF throttle) only for anonymous or IP-level throttling.

**Mocking.** Settings in tests: Turnstile secret `1x…AA`. In the test, the `responses` mock for siteverify returns
`{"success": true}` or `{"success": false, "error-codes": ["invalid-input-response"]}`. Also test the "network error →
fail closed" path. Dev can use the real test keys against the live endpoint; tests never do.

**Recommendation.** Phase 1: honeypot plus DB-enforced business limits plus allauth's built-in login rate limits. Add
Turnstile (own small client, `responses`-mocked) to signup, password reset, and any anonymous form, once one exists.
Turnstile beats hCaptcha and reCAPTCHA here: it is free, mostly invisible, and has the clearest test keys.

---

## 5. Cloudflare infrastructure, R2, and the database

### 5a. Cloudflare DNS / proxy / WAF
**What it does for the Hub.** "Additional infrastructure, security, and traffic management" (proposal §4).
- The Free plan ($0, "personal or hobby projects") includes DNS, CDN, Universal SSL, "Unmetered DDoS Protection", WAF
  with the Free Managed Ruleset, 70 Cloudflare Rules, and "Simple bots" mitigation. Pro is $20/mo annual or $25/mo
  monthly ([network plans](https://www.cloudflare.com/plans/network-cdn/)).
- Free plan rate limiting: **1 rule**, counted by IP, 10 s period, 10 s mitigation
  ([rate limiting rules](https://developers.cloudflare.com/waf/rate-limiting-rules/)). That is a coarse backstop, not a
  replacement for Django limits.
- **Domain required:** "You need a registered domain", and you must set Cloudflare's two nameservers at the registrar
  ([full setup](https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/)).
- Django gotcha when proxied: the client IP arrives in `CF-Connecting-IP`/`X-Forwarded-For`, so rate-limit keys and
  Turnstile `remoteip` must read the right header. Also set `SECURE_PROXY_SSL_HEADER` and `CSRF_TRUSTED_ORIGINS`.
  (This is standard Django deployment practice. Cloudflare's header docs were not fetched this session.)
- **Verdict:** Nothing to build or test now. Adopt it after buying the domain. Free is enough.

### 5b. Cloudflare R2
- Free (Standard class): 10 GB-month, 1M Class A ops, 10M Class B ops per month, **egress free**. Paid: $0.015/GB-month,
  $4.50/M Class A, $0.36/M Class B. The free tier doesn't apply to Infrequent Access
  ([R2 pricing](https://developers.cloudflare.com/r2/pricing/)).
- S3 API at `https://<ACCOUNT_ID>.r2.cloudflarestorage.com`, region `auto`. **Not implemented:** ACLs, object lock,
  versioning, bucket policies, object tagging, and others ([S3 compat](https://developers.cloudflare.com/r2/api/s3/api/)).
  So don't set `default_acl` / `public-read` in django-storages.
- django-storages: use the S3 backend (`storages.backends.s3.S3Storage`) with `bucket_name`, `endpoint_url`,
  `access_key`, and `secret_key` set to R2 values ([R2 page](https://django-storages.readthedocs.io/en/latest/backends/s3_compatible/cloudflare-r2.html),
  [S3 options](https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html)). Also set
  `region_name="auto"`, as in Cloudflare's own boto3 example ([boto3](https://developers.cloudflare.com/r2/examples/aws/boto3/)).
  django-storages 1.14.6 was released 2025-04 and its classifiers stop at Django 5.1 (PyPI JSON API). **Check Django 6.x
  compatibility** before adopting it.
- Public URLs: `r2.dev` "is rate-limited and should only be used for development purposes". A custom domain must be
  a Cloudflare zone in the same account ([public buckets](https://developers.cloudflare.com/r2/buckets/public-buckets/)).
  So **production use needs the domain too**.
- Reported boto3 ≥1.36 checksum-header incompatibilities with R2: **not confirmed** on any page fetched this session.
- **Mocking:** Tests use `InMemoryStorage` or a tmp `FileSystemStorage` through `STORAGES`/`settings` override. If
  S3-specific code is ever written, use `moto`'s `mock_aws` with fake `AWS_*` env vars set to `testing`
  ([moto](https://docs.getmoto.org/en/latest/docs/getting_started.html)).
- **Verdict:** Out of scope (proposal §5 lists R2 as out of scope). Keep uploads behind Django's `STORAGES` API so
  adopting R2 later is a settings change.

### 5c. Database
Django 6.1 support: PostgreSQL ≥15, MySQL ≥8.4, MariaDB ≥10.11, SQLite ≥3.37.0
([databases](https://docs.djangoproject.com/en/stable/ref/databases/)).
- **SQLite:** "an excellent development alternative for applications that are predominantly read-only or require a
  smaller installation footprint". It "can't support a high level of concurrency", and `database is locked` means
  you've hit that limit. Mitigations: `"transaction_mode": "IMMEDIATE"` and a `timeout`. `select_for_update()` "will
  have no effect" ([same](https://docs.djangoproject.com/en/stable/ref/databases/)). That matters for the "max N per
  day" checks under concurrent requests.
- **MySQL:** InnoDB is recommended. The default `utf8mb4_0900_ai_ci` collation makes comparisons
  **case-insensitive**, so `"Fred"` equals `"freD"` ([same](https://docs.djangoproject.com/en/stable/ref/databases/)).
  This silently changes "project names must be unique": on SQLite and Postgres the unique constraint is
  case-sensitive by default. Fix: enforce case-insensitive uniqueness explicitly with
  `UniqueConstraint(Lower("name"), …)` on every backend. The recommended driver, mysqlclient, ships **no Linux wheels**
  and needs `default-libmysqlclient-dev build-essential pkg-config`
  ([mysqlclient](https://pypi.org/project/mysqlclient/)). That is an awkward fit for a uv-only setup. The pure-Python
  MySQL Connector is the documented alternative.
- **PostgreSQL:** `psycopg[binary]` "will install a self-contained package with all the libraries needed", with no
  libpq or compiler ([psycopg install](https://www.psycopg.org/psycopg3/docs/basic/install.html)). `uv add` just works.
- **Deployment checklist** says nothing about which engine to pick. It says to keep DB credentials as secret as
  `SECRET_KEY` and to set up backups
  ([checklist](https://docs.djangoproject.com/en/stable/howto/deployment/checklist/)).

| Free hosted option | Free tier (verified) | Source |
|---|---|---|
| Neon (Postgres) | 100 projects, 1 GB storage per project (20 GB total), 100 CU-hours/project/month, scales to zero after 5 min, no card | [neon.com/pricing](https://neon.com/pricing) |
| Supabase (Postgres) | 500 MB per project, 2 active projects, paused after 1 week inactive | [supabase.com/pricing](https://supabase.com/pricing) |
| PythonAnywhere free | 1 web app on a `*.pythonanywhere.com` subdomain, no custom domain, outbound HTTP allowlist. The fetched pricing page showed MySQL marked "No" for free accounts. **Ambiguous; confirm before relying on it** | [pricing](https://www.pythonanywhere.com/pricing/) |

**What "SQLite now, MySQL later" implies.** Write only portable ORM code (no raw SQL). Give every uniqueness rule an
explicit, case-defined constraint. Don't rely on `select_for_update` for limits until the server DB exists. Run the
test suite against the target engine once before launch. Moving data later is `dumpdata`/`loaddata` or a fresh
migrate.

**Recommendation.** Keep SQLite for dev and tests, which is exactly the proposal's plan. For production, prefer
**PostgreSQL** (Neon free tier) over MySQL. It installs cleanly under uv, has the binary wheel, and avoids
collation surprises. If MySQL is a hard course requirement, use it with an explicit `db_collation` and test the
uniqueness rule on it.

---

## Sources (all checked 2026-11-23)

GitHub
- https://docs.github.com/en/rest/using-the-rest-api/rate-limits-for-the-rest-api
- https://docs.github.com/en/rest/using-the-rest-api/best-practices-for-using-the-rest-api
- https://docs.github.com/en/rest/using-the-rest-api/troubleshooting-the-rest-api
- https://docs.github.com/en/rest/releases/releases
- https://docs.github.com/en/rest/repos/repos#get-a-repository
- https://docs.github.com/en/rest/collaborators/collaborators
- https://docs.github.com/en/graphql/overview/rate-limits-and-query-limits-for-the-graphql-api
- https://docs.github.com/en/graphql/guides/forming-calls-with-graphql
- https://docs.github.com/en/webhooks/webhook-events-and-payloads
- https://docs.github.com/en/webhooks/using-webhooks/validating-webhook-deliveries
- https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/differences-between-github-apps-and-oauth-apps
- https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps
- https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app
- Live API check: https://api.github.com/repos/Axcenity-Studios/Axcenity-Engine/releases (and `/releases/latest` → 404)

Auth libraries
- https://docs.allauth.org/en/latest/socialaccount/providers/github.html
- https://docs.allauth.org/en/latest/socialaccount/configuration.html
- https://pypi.org/project/django-allauth/
- https://python-social-auth.readthedocs.io/en/latest/backends/github.html
- PyPI JSON API (`https://pypi.org/pypi/<pkg>/json`) for social-auth-app-django, django-anymail, django-storages,
  django-ratelimit, django-turnstile, responses, moto versions and dates

Email
- https://www.twilio.com/en-us/changelog/sendgrid-free-plan
- https://support.sendgrid.com/hc/en-us/articles/35270136965403
- https://anymail.dev/en/stable/esps/ · https://anymail.dev/en/stable/esps/sendgrid/ · https://anymail.dev/en/stable/tips/test_backend/
- https://resend.com/pricing · https://resend.com/docs/knowledge-base/403-error-resend-dev-domain
- https://postmarkapp.com/pricing · https://postmarkapp.com/support/article/1084-how-does-the-account-approval-process-work
- https://aws.amazon.com/ses/pricing/ · https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html
- https://www.mailgun.com/pricing/
- https://help.brevo.com/hc/en-us/articles/208580669 (403 on fetch; search snippet only)
- https://docs.djangoproject.com/en/stable/topics/email/ · https://docs.djangoproject.com/en/stable/releases/6.1/
- https://pytest-django.readthedocs.io/en/latest/helpers.html

Turnstile and alternatives
- https://developers.cloudflare.com/turnstile/plans/
- https://developers.cloudflare.com/turnstile/get-started/
- https://developers.cloudflare.com/turnstile/get-started/server-side-validation/
- https://developers.cloudflare.com/turnstile/troubleshooting/testing/
- https://docs.hcaptcha.com/ · https://www.hcaptcha.com/pro
- https://developers.google.com/recaptcha/docs/faq
- https://django-ratelimit.readthedocs.io/en/stable/usage.html · https://django-ratelimit.readthedocs.io/en/stable/installation.html

Cloudflare, R2, storage
- https://www.cloudflare.com/plans/network-cdn/
- https://developers.cloudflare.com/waf/rate-limiting-rules/
- https://developers.cloudflare.com/dns/zone-setups/full-setup/setup/
- https://developers.cloudflare.com/r2/pricing/
- https://developers.cloudflare.com/r2/api/s3/api/
- https://developers.cloudflare.com/r2/examples/aws/boto3/
- https://developers.cloudflare.com/r2/buckets/public-buckets/
- https://django-storages.readthedocs.io/en/latest/backends/s3_compatible/cloudflare-r2.html
- https://django-storages.readthedocs.io/en/latest/backends/amazon-S3.html
- https://docs.getmoto.org/en/latest/docs/getting_started.html
- https://github.com/getsentry/responses

Database
- https://docs.djangoproject.com/en/stable/ref/databases/
- https://docs.djangoproject.com/en/stable/howto/deployment/checklist/
- https://pypi.org/project/mysqlclient/
- https://www.psycopg.org/psycopg3/docs/basic/install.html
- https://neon.com/pricing · https://supabase.com/pricing · https://www.pythonanywhere.com/pricing/
