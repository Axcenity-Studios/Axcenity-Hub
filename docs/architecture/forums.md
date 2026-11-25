# Forums

Read this before touching `forums/`: posts, their comments and ratings, who may change them,
the posting limits, and the services every write goes through. The pages and their HTMX:
[../frontend/forums.md](../frontend/forums.md). Reporting and the moderation states:
[reports.md](reports.md).

| Module | Does |
|---|---|
| `models.py` | `ForumPost` (author, title ≤ 120, plain-text body ≤ 10,000, `created`, `edited_at`, `state`), newest first; `Comment` (post, author, body ≤ 2,000, `created`, `state`), oldest first; `Rating` (post, user, score 1–5; one per member per post and the score's range are database constraints). Querysets: `authored_by(user)`, `visible_to(user)` and `published()` (from `reports.moderation`), and `ForumPost…with_stats(user)` (`comment_count`, `rating_count`, `rating_average`) |
| `services.py` | `create_post`, `edit_post`, `delete_post`, `add_comment`, `delete_comment`, `rate_post`, `clear_rating`: the rules below, whichever way a write arrives |
| `forms.py` | `PostForm`, `CommentForm`: trimmed, blank refused, lengths in plain words (`strings.py`) |
| `views.py` | Thin views; `AuthorPostMixin` and `AuthorCommentMixin` (the 404s), `PostedPostMixin` (only a published post takes comments and ratings), `HtmxAwareMixin` (redirects and `Vary`) |
| `admin.py` | Read-only: looking up posts and comments, with their state. Changing others' content, or its state, is moderation's (Phase 15) |
| `strings.py` | Every word on the pages, as data |

## Who may do what

| Action | Who | Everyone else |
|---|---|---|
| Read the list and a post | Anyone, signed in or not | — |
| Publish (`forums:create`) | A verified member | Signed out: sign in. Unverified: `accounts:verify_email` |
| Edit (`forums:edit`) | The post's author, verified | **404** |
| Delete (`forums:delete`) | The post's author, verified or not | **404** |
| Comment (`forums:comment_create`) | A verified member, on a published post | Signed out: sign in. Unverified: verify. A hidden post: **404** |
| Delete a comment (`forums:comment_delete`) | The comment's author, verified or not | **404** |
| Rate (`forums:rate`) | A verified member who didn't write the post, on a published post | The author: "You can't rate your own post." A hidden post: **404** |
| Report (`reports:create`) | A verified member, someone else's published post or comment | **404** ([reports.md](reports.md)) |

- **One lookup decides ownership:** the edit and delete views find the post only through
  `ForumPost.objects.authored_by(request.user)` (`AuthorPostMixin`), which is empty for a
  signed-out visitor. Another member, a staff member or superuser who isn't the author, and a
  signed-out visitor all get the same 404 as for a post that doesn't exist, never a 403 and
  never a sign-in redirect, so the URL reveals nothing. The lookup runs before sign-in or
  verification checks.
- **The services check again:** `edit_post` and `delete_post` raise `PermissionDenied` for
  anyone but the author (the views never reach them for anyone else).
- **The verification gate** ([accounts.md](accounts.md)): `create_post` and `edit_post` call
  `ensure_can_contribute`; their views mix in `VerifiedEmailRequiredMixin`. Deleting your own
  post is never gated.
- `edit_post` sets `edited_at`; the pages show "Edited".
- A member's posts, comments and ratings are deleted with their account
  (`on_delete=CASCADE`); a post's comments, ratings and reports go with it.
- Bodies are plain text: escaped, with line breaks kept (`linebreaks`). No Markdown, no HTML.
  A `TextField`'s `max_length` binds only forms, so each body also has a
  `MaxLengthValidator`, and the services' `full_clean` refuses an over-long one.

## Hidden and removed content

Posts and comments have a moderation `state` ([reports.md](reports.md#moderation-states)).
Every read goes through `visible_to(request.user)`: the list, its counts, a post's page, its
comments, the comment URL, and the author-only lookups (so an author's own hidden post is a
404 to them as well). Every interaction goes through `published()`: commenting, rating and
reporting need visible content under a visible post, for staff too. A post's ratings are
shown only with the post. No view has a rule of its own.

## Ratings

1 to 5 stars, one per member per post: rating again changes it (`update_or_create`, which
on a race to create reads the winner's row back), and Clear deletes it. The post's author
can't rate it (`RatingRefused`). The pages show the average to one decimal place ("4.0 out
of 5") and the count. The view takes only the strings `"1"` to `"5"` (not `"٣"`, which
`isdigit` accepts) and `"clear"`.

## The posting limits

| Limit | Constant | Counts |
|---|---|---|
| 5 posts in 24 hours | `POST_LIMIT`, `POST_WINDOW` | The member's posts, hidden and removed ones too (deleted ones don't exist) |
| 5 comments in a minute | `COMMENT_LIMIT`, `COMMENT_WINDOW` | The member's comments, likewise |

Rolling windows, not calendar days: a row exactly one window old no longer counts. Each
creation runs in one transaction: `lock_member`, `next_allowed` (the time the window frees a
place, or None), then insert, so simultaneous requests can't slip a sixth past
([projects.md](projects.md#the-five-project-limit-concurrency-safe)). The refusal is
`LimitReached` with the wait in words ("You can comment again in 42 seconds."); the new-post
page and the comment form show it as a form error and keep the draft. The services take
`now=` for tests.

## Later phases

12C adds search, filters, sorting and pagination to the list; 15 lets admins act on others'
content and set its state through moderation.

## Tests

`tests/test_forums.py`, `tests/test_forums_comments.py`, `tests/test_reports.py`;
`tests/test_forums_browser.py` (`browser`). See
[../TESTING.md](../TESTING.md).
