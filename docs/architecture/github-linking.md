# GitHub account linking

Read this before touching GitHub linking, `accounts/github.py`, `accounts/crypto.py`,
`GitHubLink` or the `SOCIALACCOUNT_*` settings. Sign-in itself:
[accounts.md](accounts.md).

A member links **one** GitHub account to their Hub account from **Connected accounts**
(`/accounts/3rdparty/`). allauth's `socialaccount` app and GitHub provider run the OAuth
flow; the Hub adds the policy and the token storage around it.

| Module | Does |
|---|---|
| `adapter.SocialAccountAdapter` | Linking only (below); apps from the environment only; a 404 when linking is off |
| `models.GitHubLink` | One per `SocialAccount` (deleted with it): encrypted tokens, `expires_at`, `needs_reconnect`, `checked_at` |
| `crypto.py` | Fernet encryption with the keys in `GITHUB_TOKEN_KEYS` |
| `github.py` | `check_link` (is the token still good?), `refresh_tokens`, `mark_needs_reconnect`; Phase 10's repository calls build on it |
| `signals.store_github_tokens` | Stores a new link's tokens once allauth has saved the account |
| `views.ConnectionsView`, `views.GitHubConnectView` | Replace allauth's `socialaccount_connections` and `github_login` (same URLs and names) |

## A link, never a sign-in

GitHub is never a way into the Hub, so it can't bypass a password or two-factor sign-in:

- `github_login` is the Hub's `GitHubConnectView`: members only, POST only, and it always
  starts allauth's **connect** process (a GET goes back to Connected accounts).
- `pre_social_login` refuses any finished authorisation that isn't a connect by the
  signed-in member, a GitHub account another member has linked (`GITHUB_LINKED_ELSEWHERE`),
  or a second GitHub account (`GITHUB_ONE_ACCOUNT`). `SocialAccount`'s unique
  (provider, uid) holds the first rule in the database too.
- `is_open_for_signup` is false; `list_providers` is empty, so the sign-in and sign-up pages
  show no GitHub button. Signup, email lookup and auto-connect by email are off.

## The OAuth App and its secrets

An **OAuth App with no scopes** (public profile and public repositories only). Its id and
secret come from `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`; `SocialApp` rows are
ignored and their admin is unregistered. Linking is on only when the id, the secret and a
token key are all set; otherwise every GitHub URL is a 404 and the page says linking isn't
available. Production refuses to start with an app but no key.

Register the app on GitHub (Settings → Developer settings → OAuth Apps) with the callback
`http://127.0.0.1:8000/accounts/github/login/callback/` in development (production: the
same path on the site's https origin).
Put the three values in `.env` (from `.env.example`) and run with
`uv run --env-file .env python manage.py tailwind runserver`; keep the same key, since tokens
saved with one key read only with it (a new key means reconnecting).

## OAuth state

allauth's: a random `state` stored in the member's session, sent to GitHub and checked on
the callback. It works **once** (deleted when used) and for 10 minutes. A missing,
unknown, reused or another session's state gets allauth's error page (401, Hub copy in
`templates/socialaccount/`) before the code is exchanged, and links nothing.

## Tokens at rest

- `SOCIALACCOUNT_STORE_TOKENS` is off: allauth's `SocialToken` table (plain text) stays
  empty, and its admin is unregistered. The Hub stores tokens in `GitHubLink`, encrypted
  with **Fernet** (AES-128-CBC with an HMAC-SHA256 tag).
- `GITHUB_TOKEN_KEYS` holds comma-separated Fernet keys: the first encrypts, every one
  decrypts. To rotate, put a new key first and keep the old one until every link has been
  re-stored. Make a key with
  `uv run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
  A malformed key stops settings from loading (without echoing it).
- A token is decrypted only for one request to GitHub (`GitHubLink.access_token`). It's
  never logged (logs name the link's id), shown on a page, in the admin (`GitHubLink` has
  no admin page) or in `repr`, and never put in the session: connecting doesn't need a
  fresh re-authentication, because allauth would park the new token in the session while
  it waited.
- **Unlinking** deletes the `SocialAccount`, and the `GitHubLink` and its tokens with it.

## Revoked and expired tokens

`check_link(link, now=)` runs when Connected accounts is viewed, at most once per
`GITHUB_LINK_CHECK_INTERVAL` (15 minutes). It calls `GET /user` with the member's token:

| GitHub says | Result |
|---|---|
| 200 | `OK`: `checked_at` set, the GitHub username kept current (only if it's a valid username) |
| 401, or a token no configured key can read | `NEEDS_RECONNECT`: the link is marked; GitHub isn't asked again with that token; the page prompts to reconnect |
| 5xx, 403, 404, timeout, malformed reply | `UNAVAILABLE`: nothing changes; the page says GitHub couldn't be reached |

**Expiring tokens** (a GitHub App's user tokens; an OAuth App's don't expire): when
`expires_at` has passed (with a minute's margin), the refresh token is exchanged first.
GitHub rotates both tokens; the new pair is stored encrypted and the old refresh token is
gone. A refused refresh (`bad_refresh_token`), or no refresh token, means reconnecting.

**Reconnecting** runs the same connect flow; the adapter stores the new tokens and clears
`needs_reconnect`.

## Unlinking

The Unlink button POSTs to Connected accounts. It needs a **fresh re-authentication**
(allauth's `reauthentication_required`): allauth asks for the password or a two-factor
code, then replays the POST. allauth's "last way to sign in" check is skipped, since GitHub
never is one here. A member can only ever unlink their own link.

## Tests

`tests/test_accounts_github.py`. No test drives real OAuth: `SocialAccount` rows are made
directly, and `github.com/login/oauth/access_token` and `api.github.com/user` are mocked
with `responses` (`tests/fixtures/github/user.json` is GitHub's public example account,
trimmed). The `github_on` fixture sets the app and the token key.
