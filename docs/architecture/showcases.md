# Showcases

Read this before touching `showcases/`: showcases, their tags and likes, who may change them,
the one-a-day limit, and the images members upload. The pages: [../frontend/showcases.md](../frontend/showcases.md).
The list's search, tag filter and pages: [lists.md](lists.md#the-showcase-list-showcaseslistingpy).
Reporting and the moderation states: [reports.md](reports.md).

| Module | Does |
|---|---|
| `models.py` | `Tag` (a name: 2–24 lower-case letters and digits, words joined by hyphens; unique, and lower case is a database check); `Showcase` (author, title ≤ 100, `slug`, plain-text description ≤ 5,000, `image` and `card` with their sizes, `image_alt` ≤ 200, tags (≤ 5), `created`, `edited_at`, `state`), newest first; `Like` (one per member per showcase: a database constraint). Querysets: `authored_by(user)`, `visible_to(user)`, `published()`, `with_likes()` (`like_count`) |
| `images.py` | `check(upload)` (the refusals below) and `process(upload)` (the two WebPs the Hub stores) |
| `services.py` | `create_showcase`, `edit_showcase`, `delete_showcase`, `like`, `unlike`, `has_liked`, `limit_message`, `slug_candidates`: the rules below, whichever way a write arrives |
| `listing.py` | `SHOWCASES`: search, the tag and published filters, three sorts, 24 a page |
| `forms.py` | `ShowcaseForm` (a plain form: its cleaned `image` is an `images.Processed`, its `tags` a list of names) |
| `views.py` | Thin views; `AuthorShowcaseMixin` (the 404s), `PublishedShowcaseMixin` (only a published showcase takes likes); reuses the forum's `HtmxAwareMixin`, `person`, `count_words`, `mark_invalid` |
| `signals.py` | A deleted showcase (or its author's account) takes its image files with it |
| `management/commands/seed_showcase_demo.py` | 30 backdated demo showcases with placeholder images, tags and likes (development only, idempotent) |
| `admin.py` | Read-only: looking up showcases and tags. Acting on them is moderation's (Phase 15) |
| `strings.py` | Every word on the pages, as data |

## Who may do what

| Action | Who | Everyone else |
|---|---|---|
| Browse the list and open a showcase | Anyone, signed in or not | — |
| Publish (`showcases:create`) | A verified member, one a day | Signed out: sign in. Unverified: `accounts:verify_email` |
| Edit (`showcases:edit`) | The showcase's author, verified | **404** |
| Delete (`showcases:delete`) | The showcase's author, verified or not | **404** |
| Like, take it back (`showcases:like`) | A verified member who didn't publish it, on a published showcase | The author: "You can't like your own showcase." A hidden one: **404** |
| Report (`reports:create`, kind `showcase`) | A verified member, someone else's published showcase | **404** ([reports.md](reports.md)) |

- **One lookup decides ownership:** the edit and delete views find the showcase only through
  `visible_to(user).authored_by(user)` (`AuthorShowcaseMixin`), before sign-in or
  verification run, so another member, staff who aren't the author and a signed-out visitor
  all get the same 404 as for a slug that doesn't exist. The services check again
  (`PermissionDenied`).
- **The verification gate:** `create_showcase`, `edit_showcase` and `like` call
  `ensure_can_contribute`; their views mix in `VerifiedEmailRequiredMixin`. Deleting your own
  showcase and taking back a like are never gated.
- Descriptions are plain text: escaped, with line breaks kept. A member's showcases and likes
  are deleted with their account; a showcase's likes and reports go with it. Tags stay.

## The one-a-day limit

`SHOWCASE_LIMIT` (1) within `SHOWCASE_WINDOW` (24 hours, rolling): the member's showcases,
hidden and removed ones too (deleted ones don't exist). `create_showcase` runs it like the
forum's limits ([forums.md](forums.md#the-posting-limits)): one transaction, `lock_member`,
`next_allowed`, then the insert, so simultaneous requests can't publish two. The refusal is
`LimitReached` ("You can publish 1 showcase a day. You can publish again in 3 hours, 12
minutes."); `limit_message` lets the publish page say so before the member chooses a file
(the service still decides). `now=` is for tests.

## Images

An upload is untrusted bytes. `images.check` runs before anything decodes the pixels, in this
order, and each refusal has a code and a message (`images.MESSAGES`):

| Code | Refused |
|---|---|
| `too_big` | More than 8 MB (`MAX_BYTES`; exactly 8 MB passes), judged before reading it |
| `not_an_image` | Bytes Pillow can't read as an image (text, SVG, an empty file, a decompression bomb) |
| `wrong_format` | Anything but PNG, JPEG or WebP, judged by the bytes, never the name or the declared type (a TIFF named `.png` is refused; GIF is refused: only its first frame would be kept) |
| `too_small` | Narrower than 640 or shorter than 360 pixels |
| `too_large` | More than 8000 pixels on either side |
| `bad_ratio` | One side more than 4 times the other (exactly 4:1 passes) |

`images.process` then decodes it (a file whose header passed but whose pixels don't, such as
a truncated one, is `not_an_image` too), turns it upright from its EXIF, and re-encodes it as
two WebPs scaled down to fit (never up): `display` (1920 px on the long side) and `card` (800
px). No metadata or original bytes are kept. The form does both, so every refusal is a form
error and nothing is written for a refused upload.

Files go through Django's default storage (the `ImageField`s), so object storage later is a
settings change. Each file gets a fresh random name (`showcases/<hex>.webp`,
`showcases/cards/<hex>.webp`). The services write them only after the limit has passed, and
delete them if the save then fails; a new image on edit deletes the old files after saving;
deleting a showcase or its author deletes them (`signals.py`). Django reads the whole upload
before the form sees it: production's web server should cap request bodies (around 10 MB).

## Slugs and tags

- **Slugs** (`/showcases/<slug>/`) come from the title when it's published (`slugify`, cut to
  fit, `showcase` when nothing is left, as for a title in another script) and stay when the
  title changes, so a shared link keeps working. A taken one is numbered (`hall-2`, up to
  `SLUG_ATTEMPTS`), then given a random suffix; `new` is reserved for the publish page. The
  unique index decides between simultaneous ones: each attempt saves in a savepoint.
- **Tags** are typed separated by commas or spaces (`Tag.parse`: lower-cased, a leading `#`
  dropped, each once), at most 5. A name that isn't one (`ray_tracing`, `x`) is refused by
  name. They're made when first used (`get_or_create`), and are never deleted.

## Tests

`tests/test_showcases_images.py` (the image check, test-first), `tests/test_showcases.py`,
`tests/test_showcases_list.py`, `tests/test_showcases_browser.py` (`browser`). See
[../TESTING.md](../TESTING.md).
