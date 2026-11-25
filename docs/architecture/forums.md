# Forums

Read this before touching `forums/`: posts, who may change them, and the services every
write goes through. The pages and their HTMX: [../frontend/forums.md](../frontend/forums.md).

| Module | Does |
|---|---|
| `models.py` | `ForumPost` (author, title ≤ 120, plain-text body ≤ 10,000, `created`, `edited_at`), newest first; `ForumPostQuerySet.authored_by(user)`; `is_author(user)` |
| `services.py` | `create_post`, `edit_post`, `delete_post`: the rules below, whichever way a write arrives |
| `forms.py` | `PostForm`: title and body, trimmed, blank refused, lengths in plain words (`strings.py`) |
| `views.py` | Thin views; `AuthorPostMixin` (the 404), `HtmxAwareMixin` (redirects and `Vary`) |
| `admin.py` | Read-only: looking up posts. Changing others' posts is moderation's (Phase 15) |
| `strings.py` | Every word on the pages, as data |

## Who may do what

| Action | Who | Everyone else |
|---|---|---|
| Read the list and a post | Anyone, signed in or not | — |
| Publish (`forums:create`) | A verified member | Signed out: sign in. Unverified: `accounts:verify_email` |
| Edit (`forums:edit`) | The post's author, verified | **404** |
| Delete (`forums:delete`) | The post's author, verified or not | **404** |

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
- A member's posts are deleted with their account (`on_delete=CASCADE`).
- Bodies are plain text: escaped, with line breaks kept (`linebreaks`). No Markdown, no HTML.

## Later phases

12B adds comments, ratings, the posting limits (5 posts a day, 5 comments a minute; through
`accounts.limits.lock_member`) and reports with hidden and removed states; 12C adds search,
filters, sorting and pagination to the list; 15 lets admins act on others' posts through
moderation.

## Tests

`tests/test_forums.py`; `tests/test_forums_browser.py` (`browser`). See
[../TESTING.md](../TESTING.md).
