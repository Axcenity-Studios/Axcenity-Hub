# The app shell and the entrance

Read this before changing signed-in pages, the sign-in pages or allauth's templates.
The security rules behind them: [../architecture/accounts.md](../architecture/accounts.md).

## Two layouts beside the marketing shell

Both extend `templates/base.html` (theme, fonts, stylesheet, `shell.js`).

| Template | For | Holds |
|---|---|---|
| `app/shell.html` | Signed-in pages (projects, Account settings; later forums, reports) | `.app-bar` (wordmark, "Account center", theme switch, account menu), `.app-frame` with the `#app-rail` and `<main class="app-main">`, which holds one centred `.app-column` (60rem) |
| `app/entrance.html` | Sign in, sign up, reset, the two-factor step, re-authentication | The same bar without the menu, and one `.entrance-panel` on the grid backdrop |

- **Rail** (`.app-rail`): a `<details>` that's open without JavaScript; an inline script
  folds it below 1024 px, where its summary ("Menu") is the toggle. Sections come from
  `{% app_rail %}` (`accounts/templatetags/app_shell.py`): **Workspace** (Projects), then
  **Account** (one item, Account settings) for a signed-in member only. `page_key` names a
  view's page from its name (`strings.PAGES`; every `mfa_*` page is two_factor; every page of
  a namespace in `strings.RAIL_NAMESPACES`, such as `projects:*`, is its item); `rail_key`
  makes every account tab the Account settings item. Later phases add items to `strings.RAIL_HUB`.
- **Column** (`.app-column`): every page, the messages included, sits in one column centred
  in the space beside the rail. allauth's pages put their parts straight in it; their forms,
  panels and text keep a 46rem measure.
- **Template context:** the shell sets `copy` (accounts' strings) for the whole page, so a
  page with its own copy passes it under another name (the project pages use `text`).
- **Account menu** (`.app-user`): a `<details>`; its button shows the member's photo (and
  username from 30rem). It holds the photo, name and email, **Account settings**, and
  **Sign out**, a POST form with its CSRF token (never a link). Signed out, the bar shows
  **Sign in** instead, returning to the page.
- **`{% member as me %}`**: the signed-in member for the shell (name, username, email, photo
  URL or initial, bio, "Member since", email verified, two-factor on, GitHub `linked`,
  `attention` or `""`), worked out once per request. It never writes and never asks GitHub
  (GitHub's state is the stored `needs_reconnect`). `partials/avatar.html` draws a photo or
  the initial on a tile (`.app-avatar`, round, `--avatar` is its size).

## Account settings

Profile, Email, Password, Two-factor and Connected accounts are tabs of one page.
`accounts/base.html` fills the shell's `before_content` block with the header (`.ac-head`):
the photo, name, handle and "Member since", the three states (`.ac-status`, each a link to
its tab; "on" is a filled dot, never a colour), and the tabs (`.ac-tabs`, from
`strings.ACCOUNT_TABS` through `{% account_tabs %}`; on a phone they scroll in their own
strip and the states become rows). The Hub's pages extend it; allauth's reach it through
`allauth/layouts/manage.html`.

| Tab | Template | Holds |
|---|---|---|
| Profile | `accounts/profile.html` | The form (photo, display name, bio; multipart) beside a preview as others see it, with username and join date |
| Email | `accounts/email.html` | The address, its state and use, resend; "What we send" (`strings.EMAIL_SENDS`) |
| Password | `account/password_change.html` (allauth's, overridden) | The form beside "A good password" (the validators in words) |
| Two-factor | `mfa/index.html` (allauth's, overridden) | The authenticator app and recovery codes as numbered steps (`.pj-step`), each with its state tag and actions; allauth's activate, deactivate and codes pages keep its own templates |
| Connected accounts | `accounts/connections.html` | The GitHub panel (`data-github-state`), then "What linking does" (`strings.GITHUB_WHAT`) |

The bodies reuse the projects' parts (`.pj-panel`, `.pj-bar`, `.pj-facts`, `.pj-steps`,
`.pj-tag`). `{% fill copy.X key=value %}` fills copy with `{placeholders}`. Photos are
validated and remade by `accounts/avatars.py` ([../architecture/accounts.md](../architecture/accounts.md)).
- **Messages**: `partials/messages.html`, a polite live region, in both layouts.
- Copy lives in `accounts/strings.py`; templates read it with `{% account_copy as copy %}`.

## allauth's pages

allauth renders through layouts and "elements"; the Hub overrides them all in
`templates/allauth/`:

- `layouts/entrance.html` → `app/entrance.html`; `layouts/manage.html` →
  `app/shell.html`; `layouts/base.html` → the entrance.
- `elements/*.html`: headings (`.app-title`, `.app-heading`), paragraphs, panels
  (`.app-panel`), tables, alerts, badges, forms (`.app-form` with `.app-actions`) and
  buttons. A button is `btn-primary` when allauth tags it `prominent` (or `primary`
  without `outline`), or when it's an untagged submit; otherwise `btn-quiet`.
- `elements/fields.html` and the Hub's own forms use `partials/form_fields.html` (each field
  through `partials/form_field.html`, which a page can include for one field): form
  errors (`.app-form-errors`), each field with its label, errors and help, checkboxes
  inline, the **honeypot** (`website`) inside `.app-honeypot` (off-screen, `aria-hidden`,
  `tabindex=-1`), and the **Turnstile** widget when the form's `turnstile_site_key` is
  set. Cloudflare's `api.js` is the one script loaded from another site: Cloudflare
  requires it, so it can't be vendored. It's absent unless Turnstile is configured.
- `socialaccount/`: a cancelled or failed GitHub link (`login_cancelled.html`,
  `authentication_error.html`) and allauth's link messages (`messages/*.txt`), in the
  Hub's words: GitHub is linked, never signed in with. Copy in `accounts/strings.py`.
- Connected accounts (`accounts/connections.html`) marks its panel with
  `data-github-state` (`ok`, `needs_reconnect`, `unavailable` or `none`).
- The TOTP QR code (`.app-qr`) carries its own white paper (`accounts.adapter.MFAAdapter`),
  so it scans in either scheme without a fixed colour in the chrome.

## Classes

| Class | What |
|---|---|
| `.app-column`, `.app-page`, `.app-page-head`, `.app-title`, `.app-lede` | The centred column, a page and its header |
| `.app-avatar`, `.app-avatar-initial`, `.app-user-card` | A photo or initial; the menu's card |
| `.ac-head`, `.ac-id`, `.ac-status`, `.ac-stat`, `.ac-tabs`, `.ac-tab` | Account settings' header and tabs |
| `.ac-split`, `.ac-body`, `.ac-photo`, `.ac-preview`, `.ac-facts`, `.ac-points` | The tabs' bodies: a panel and its aside, the photo row, the preview, facts, points with icon tiles |
| `.app-panel`, `.app-heading`, `.app-rows`, `.app-list` | 1px panels and their content |
| `.app-field`, `.app-field-check`, `.app-help`, `.app-field-errors` | Fields on `inset`, ring `line-strong`, focus ring ink |
| `.app-badge`, `.app-mono`, `.app-link`, `.app-notice`, `.app-message` | Small parts |

Everything is monochrome: errors are `fg-strong` with an ink ring and a "!" marker,
never a colour. Every `:hover` is behind the hover gate. The nav's Sign in links to
`account_login`; signed in, it reads **Account** (the profile).

## Tests

`test_accounts.py` (the rail, the tabs and their current items, the header's states, the
sign-out form; entrance layout), `test_accounts_photos.py` (the photo), `test_projects.py`
(project pages in the shell, Projects current), `test_accounts_browser.py` (sign in through
the form, rail, menu and every tab at 360 and 1280 px, dark and light, centred, no sideways
scroll, a photo uploaded; screenshots in `screenshots/accounts/`).
