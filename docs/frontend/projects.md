# The project pages

Read this before changing `templates/projects/`, `projects/setup.py`, `static/js/projects.js`
or the `.pj-*` classes. The rules behind them (the limit, permissions, webhooks):
[../architecture/projects.md](../architecture/projects.md). They sit in the app shell
([app-shell.md](app-shell.md)).

| Template | Page |
|---|---|
| `projects/list.html` | `/projects/`: a card per project, or the empty state |
| `projects/detail.html` | `/projects/<slug>/`: the setup checklist, then the repository panel |
| `projects/form.html`, `confirm_delete.html` | New, edit and delete |
| `projects/guide.html` | `/projects/guide/`: the setup guide (public) |

Every word is in `projects/strings.py` (copy as data). The app shell already sets `copy`, so
these pages get theirs as `text`.

## The setup checklist

`projects.setup.setup_for(user, link)` turns the real records into four steps, each `done`,
`current`, `attention`, `waiting` or `off`:

| Step | Done when | Otherwise |
|---|---|---|
| 01 Link your GitHub account | the member has a GitHub link | `attention` when GitHub refused its token |
| 02 Link a repository | the project has a link | `attention` when GitHub reports it deleted |
| 03 Add the webhook on GitHub | `webhook_shown_at` is set (or a delivery arrived) | `off` without `GITHUB_WEBHOOK_SECRET` |
| 04 Wait for GitHub's first delivery | `first_webhook_at` is set | `off` likewise |

Only the first unfinished step is `current`; later ones wait. Progress is out of four always:
with webhooks off the setup is never complete ("2 / 4", "Live updates aren't available on this
Hub yet."), and step 3 tells a member their repository is still linked and refreshes hourly.
Only a development server (`DEBUG`) adds the operator's hint (set `GITHUB_WEBHOOK_SECRET`);
members of a hosted Hub never see the server's settings named. The view (`step_rows`) adds
each step's words and summary ("Linked as octocat.", "First delivery …").

- The checklist is a `<details id="setup">`: open until every available step is done, then
  folded to its bar ("Repository connected", the meter, "Show steps"). No JavaScript.
- A step's state is its tag, its numeral (solid for the current step, outlined otherwise) and
  an ink rule down its left edge; done steps' icon tiles turn ink. Never colour.
- The current step opens in place: the Connected accounts button, the link form, or the
  webhook step's **Show webhook settings**.
- **Showing the webhook's values** is `GET ?webhook=show#setup-webhook`: the view runs
  `services.webhook_settings` (an admin check with GitHub, recording `webhook_shown_at`),
  then shows GitHub's Add webhook form field by field (`strings.WEBHOOK_FIELDS`): payload URL,
  content type, secret, events. A refused check shows its reason in the step. A response
  carrying the secret is never cached (`add_never_cache_headers`). The secret never appears
  without `?webhook=show`.
- **Open GitHub's Add webhook page** links to `<repository>/settings/hooks/new` in a new tab.
- The payload URL is built on `HUB_PUBLIC_URL` when set (`views.payload_url`). When the
  URL's host is `localhost`, `127.0.0.1` or `::1`, the step warns that GitHub can't reach it,
  says to set `HUB_PUBLIC_URL` to a tunnel's address, and points at the guide's "Testing on
  your own computer" (which covers quick and named Cloudflare tunnels).

## Copy buttons

`static/js/projects.js` (on the project page only): each `button.pj-copy[data-copy]` copies
the text of the element its `data-copy` names, then reads "Copied" (`data-copied`) for two
seconds. The buttons are `hidden` until the script shows them; without JavaScript the values
are plain selectable text.

## The guide

`/projects/guide/` (`ProjectGuideView`) is public, so it can be shared and read before
signing up. Sections, each with an anchor: `#before`, `#steps` (the four steps, the same
numerals and icons as the checklist), `#access`, `#trouble` (every response the webhook gives,
from `webhooks.Outcome`; a test keeps them in step), `#unlink`, `#local` (the tunnel).
Signed out, the app shell shows **Sign in** in its bar and only the rail's Hub section.

## Icons

New line icons in `partials/icon.html`, each a motif (draws in when seen): `chain` (step 1),
`repo` (step 2, the repository panel), `hook` (step 3), `ping` (step 4), `guide`; plain ones:
`copy`, `external`, `plus`, `check`, `folder`.

## The `.pj-*` classes

Monochrome tokens only, every `:hover` behind the hover gate. The bars use the Toolbox's
chips (`.tb-chip`, `.tb-chip-current`) inside `.pj-bar` (not `.tb-bar`, which the drawn
Toolbox restyles).

- `.app-page-wide`: a 60rem column for these pages. `.pj-head`: title beside its actions.
- `.pj-panel`, `.pj-bar`, `.pj-foot`, `.pj-tag` (`[data-state]`, `[data-complete]` invert it).
- `.pj-meter`: one segment per step, filled when done.
- `.pj-cards`, `.pj-card` (the title's link stretches over the card), `.pj-card-*`,
  `.pj-repo`, `.pj-progress`; `.pj-empty`, `.pj-preview`.
- `.pj-num`: Home's outlined numerals at step size. `.pj-steps`, `.pj-step[data-state]`,
  `.pj-step-head`, `.pj-step-title`, `.pj-step-summary`, `.pj-step-body`, `.pj-icon`.
- `.pj-fields`, `.pj-value`, `.pj-copy`: the webhook's values.
- `.pj-repo-body`, `.pj-repo-name`, `.pj-facts`: the repository panel.
- `.pj-section`, `.pj-guide-list`, `.pj-table` (scrolls in its own box), `.pj-terminal`.
- Below 40rem: the checklist's progress wraps under its title, a step's tag sits by its icon,
  numerals shrink, each value takes its row, and a step's buttons wrap their words.

## Tests

`tests/test_projects_setup.py` (the steps' states, the checklist at each stage, a real ping
completing it, the webhook values and copy markup, the local warning, the cards, the guide
signed in and out). `tests/test_projects_browser.py` (`browser`): every page at 360 and
1280 px, dark and light: nothing scrolls sideways or spills past its panel, the copy button
copies; screenshots in `screenshots/projects/` for review by eye.
