# The project pages

Read this before changing `templates/projects/`, `projects/setup.py`, `static/js/projects.js`
or the `.pj-*` classes. The rules behind them (the limit, permissions, webhooks):
[../architecture/projects.md](../architecture/projects.md). They sit in the app shell
([app-shell.md](app-shell.md)).

| Template | Page |
|---|---|
| `projects/list.html` | `/projects/`: the member's invitations, then a card per project they're in, or the empty state |
| `projects/detail.html` | `/projects/<slug>/`: the role tag, Team link, the setup checklist (Owners), then the repository panel |
| `projects/members.html` | `/projects/<slug>/members/`: the team, and for Owners the controls, pending invitations and the invite form |
| `projects/form.html`, `confirm_delete.html` | New, edit and delete |

Every word is in `projects/strings.py` (copy as data). The app shell already sets `copy`, so
these pages get theirs as `text`.

## Roles on the pages

Each page shows a member only what their role may do (`can` in the project page's context,
from `models.PERMISSIONS`): Edit for Owners and Maintainers, Delete, the setup checklist,
Unlink and the webhook for Owners, Refresh for Owners and Maintainers. A Viewer, or a
Maintainer on a project with no repository, gets a plain repository panel ("An Owner links
it"). The role is a `.pj-tag` (`data-role-tag`) under the description and on each card;
cards of projects the member doesn't own show their role instead of setup progress. The count
("1 of 5 projects") counts owned projects only.

## The team page

- One row per member (`[data-members] > li[data-member][data-role]`): their avatar, name
  (and username when it differs), "(You)" and role tag. Owners get a role `<select>` with
  "Change role" and, for others, "Remove".
- The panel's foot: "Leave project", or for the only Owner the reason they can't
  (`data-last-owner`).
- Owners also see **Pending invitations** (`[data-pending]`, each with Cancel) and **Invite a
  member** (`[data-invite]`: username and role).
- Everyone sees **Roles**: what each one may do (`strings.ROLE_NOTES`).
- The invitee's **Invitations** panel heads `/projects/` (`[data-invitations]`): the project,
  who invited them and as what, Accept (opens the project) and Decline.
- Every change is a POST form with redirects and messages; no JavaScript. Rows reuse the
  `.pj-panel`/`.pj-bar`/`.pj-tag` classes with Tailwind utilities (`.app-list` sets `padding: 0`
  outside the layers, so rows carry their own padding).

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
  says to set `HUB_PUBLIC_URL` to an `https://` address GitHub can reach.

## Copy buttons

`static/js/projects.js` (on the project page only): each `button.pj-copy[data-copy]` copies
the text of the element its `data-copy` names, then reads "Copied" (`data-copied`) for two
seconds. The buttons are `hidden` until the script shows them; without JavaScript the values
are plain selectable text.

## Each step's help

There's no separate guide page: the walkthrough lives in the checklist. Every step ends in a
`<details class="pj-help" data-help="<key>">` "Help with this step" (`strings.HELP_STEPS`).
Step 1's adds what the Hub can and can't do (`HELP_ACCESS`); step 4's adds every response
the webhook gives (`HELP_TROUBLE`, from `webhooks.Outcome`; a test keeps them in step), as a
table that stacks into blocks on a phone.

- **A first repository** (`views.first_repository`: none of the member's other projects has
  one): the current (or attention) step's help opens by itself, and "Before you start"
  (`HELP_BEFORE`, `data-help="before"`) heads the checklist, open until a step is done.
- **Later repositories**: every help is folded, and there's no "Before you start".
- The repository panel ends with what unlinking does (`HELP_UNLINK`).

## Icons

New line icons in `partials/icon.html`, each a motif (draws in when seen): `chain` (step 1),
`repo` (step 2, the repository panel), `hook` (step 3), `ping` (step 4), `guide` (the help); plain ones:
`copy`, `external`, `plus`, `check`, `folder`.

## The `.pj-*` classes

Monochrome tokens only, every `:hover` behind the hover gate. The bars use the Toolbox's
chips (`.tb-chip`, `.tb-chip-current`) inside `.pj-bar` (not `.tb-bar`, which the drawn
Toolbox restyles).

- `.pj-head`: title beside its actions (the shell's `.app-column` centres the page).
- `.pj-panel`, `.pj-bar`, `.pj-foot`, `.pj-tag` (`[data-state]`, `[data-complete]` invert it).
- `.pj-meter`: one segment per step, filled when done.
- `.pj-cards`, `.pj-card` (the title's link stretches over the card), `.pj-card-*`,
  `.pj-repo`, `.pj-progress`; `.pj-empty`, `.pj-preview`.
- `.pj-num`: Home's outlined numerals at step size. `.pj-steps`, `.pj-step[data-state]`,
  `.pj-step-head`, `.pj-step-title`, `.pj-step-summary`, `.pj-step-body`, `.pj-icon`.
- `.pj-fields`, `.pj-value`, `.pj-copy`: the webhook's values.
- `.pj-repo-body`, `.pj-repo-name`, `.pj-facts`: the repository panel.
- `.pj-help`, `.pj-help-body`, `.pj-help-title`, `.pj-before`: the help; `.pj-guide-list`,
  `.pj-table` (scrolls in its own box; stacks on a phone).
- Below 40rem: the checklist's progress wraps under its title, a step's tag sits by its icon,
  numerals shrink, each value takes its row, and a step's buttons wrap their words.

## Tests

`tests/test_projects_teams.py` (the pages per role, the team page, invitations on the list).
`tests/test_projects_setup.py` (the steps' states, the checklist at each stage, a real ping
completing it, the webhook values and copy markup, the local warning, the cards, each step's
help and when it opens). `tests/test_projects_browser.py` (`browser`): every page at 360 and
1280 px, dark and light: centred, nothing scrolls sideways or spills past its panel, the
current step's help open on a first repository, the copy button copies; the team pages (an Owner inviting
through the form, the invitations panel and accepting, a Viewer's page without controls); screenshots in `screenshots/projects/` for review by eye.
