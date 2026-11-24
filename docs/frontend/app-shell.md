# The app shell and the entrance

Read this before changing signed-in pages, the sign-in pages or allauth's templates.
The security rules behind them: [../architecture/accounts.md](../architecture/accounts.md).

## Two layouts beside the marketing shell

Both extend `templates/base.html` (theme, fonts, stylesheet, `shell.js`).

| Template | For | Holds |
|---|---|---|
| `app/shell.html` | Signed-in pages (projects, profile, email, password, two-factor, connected accounts; later forums, reports) | `.app-bar` (wordmark, "Hub", theme switch, account menu), `.app-frame` with the `#app-rail` and `<main class="app-main">` |
| `app/entrance.html` | Sign in, sign up, reset, the two-factor step, re-authentication | The same bar without the menu, and one `.entrance-panel` on the grid backdrop |

- **Rail** (`.app-rail`): a `<details>` that's open without JavaScript; an inline script
  folds it below 1024 px, where its summary ("Hub and account") is the toggle. Sections
  come from `{% app_rail %}` (`accounts/templatetags/app_shell.py`): **Hub** (Projects),
  then **Account**. It marks the current page from the view name (`strings.RAIL_PAGES`;
  every `mfa_*` page is Two-factor; every page of a namespace in `strings.RAIL_NAMESPACES`,
  such as `projects:*`, is its item). Later phases add items to `strings.RAIL_HUB`.
- **Template context:** the shell sets `copy` (accounts' strings) for the whole page, so a
  page with its own copy passes it under another name (the project pages use `text`).
- **Account menu** (`.app-user`): a `<details>` with the email and **Sign out**, a POST
  form with its CSRF token (never a link).
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
- `elements/fields.html` and the Hub's own forms use `partials/form_fields.html`: form
  errors (`.app-form-errors`), each field with its label, errors and help, checkboxes
  inline, the **honeypot** (`website`) inside `.app-honeypot` (off-screen, `aria-hidden`,
  `tabindex=-1`), and the **Turnstile** widget when the form's `turnstile_site_key` is
  set. Cloudflare's `api.js` is the one script loaded from another site: Cloudflare
  requires it, so it can't be vendored. It's absent unless Turnstile is configured.
- allauth's own pages put their parts straight in `<main>`; `.app-main > :not(.app-page)`
  gives them the same 46rem measure as the Hub's `.app-page`.
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
| `.app-page`, `.app-page-head`, `.app-title`, `.app-lede` | A page's column and header |
| `.app-panel`, `.app-heading`, `.app-rows`, `.app-list` | 1px panels and their content |
| `.app-field`, `.app-field-check`, `.app-help`, `.app-field-errors` | Fields on `inset`, ring `line-strong`, focus ring ink |
| `.app-badge`, `.app-mono`, `.app-link`, `.app-notice`, `.app-message` | Small parts |
| `.app-project` | A row of the projects list: the name and its repository, wrapping on phones |

Everything is monochrome: errors are `fg-strong` with an ink ring and a "!" marker,
never a colour. Every `:hover` is behind the hover gate. The nav's Sign in links to
`account_login`; signed in, it reads **Account** (the profile).

## Tests

`test_accounts.py` (the shell's rail, current item and sign-out form; entrance layout),
`test_projects.py` (project pages in the shell, Projects current),
`test_accounts_browser.py` (sign in through the form, rail and menu at 360 and 1280 px,
dark and light, no sideways scroll; screenshots in `screenshots/accounts/`).
