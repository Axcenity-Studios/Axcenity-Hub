"""The showcase pages' copy and messages, as data."""

from . import images

# The list.
TITLE = "Showcases"
LEDE = "What members have built with Axcenity Engine."
NEW_SHOWCASE = "New showcase"
SIGN_IN_TO_PUBLISH = "Sign in to publish"
EMPTY_TITLE = "No showcases yet"
EMPTY_TEXT = "Publish the first one: a level, a scene or a tool you built with the engine."
NO_MATCH_TITLE = "No showcases match"
NO_MATCH_TEXT = "Try other words, another tag, or clear the search and filters."
SHOWCASES_LABEL = "Showcases"
SHOWCASES_COUNT = "{count} showcase"
SHOWCASES_COUNT_PLURAL = "{count} showcases"
TAGGED = "Tagged {tag}"

# Finding showcases: search, filters, sorting and pages (showcases.listing).
CONTROLS_LABEL = "Search, filter and sort showcases"
SEARCH_LABEL = "Search showcases"
SEARCH_PLACEHOLDER = "Search titles and descriptions"
PAGES_LABEL = "Showcase pages"
SORT_NEWEST = "Newest"
SORT_OLDEST = "Oldest"
SORT_LIKED = "Most liked"
FILTER_TAG = "Tag"
TAG_ANY = "Any tag"
FILTER_POSTED = "Published"
POSTED_ANY = "Any time"
POSTED_DAY = "Past 24 hours"
POSTED_WEEK = "Past week"
POSTED_MONTH = "Past month"

# A showcase's page.
BACK = "All showcases"
YOURS = "Your showcase"
PUBLISHED = "Published {when}"
EDITED_AT = "Edited {when}"
EDITED = "Edited"
TAGS_LABEL = "Tags"
SHOWCASE_ACTIONS = "Showcase actions"
EDIT = "Edit"
DELETE = "Delete"
REPORT = "Report"
REPORTED = "Reported"

# Likes.
LIKES_LABEL = "Likes"
LIKE_COUNT = "{count} like"
LIKE_COUNT_PLURAL = "{count} likes"
LIKE = "Like"
UNLIKE = "Liked"
LIKE_HINT = "Like this showcase"
UNLIKE_HINT = "Take back your like"
SIGN_IN_TO_LIKE = "Sign in to like"
LIKE_OWN = "You can't like your own showcase."
LIKED = "Liked."
UNLIKED = "Like taken back."

# Publishing and editing.
CREATE_TITLE = "New showcase"
CREATE_LEDE = (
    "Share a level, a scene or a tool you built with Axcenity Engine. "
    "You can publish one showcase a day."
)
EDIT_TITLE = "Edit showcase"
PUBLISH = "Publish"
SAVE = "Save"
CANCEL = "Cancel"
CREATED = "Showcase published."
SAVED = "Showcase saved."
TITLE_LABEL = "Title"
TITLE_HELP = "Up to 100 characters."
TITLE_REQUIRED = "Give your showcase a title."
TITLE_TOO_LONG = "Keep the title to 100 characters or fewer."
DESCRIPTION_LABEL = "Description"
DESCRIPTION_HELP = "What you built and how. Plain text, up to 5,000 characters."
DESCRIPTION_REQUIRED = "Describe your showcase."
DESCRIPTION_TOO_LONG = "Keep the description to 5,000 characters or fewer."
IMAGE_LABEL = "Image"
IMAGE_HELP = (
    f"PNG, JPEG or WebP, up to 8 MB, at least {images.MIN_WIDTH} × {images.MIN_HEIGHT} pixels."
)
IMAGE_HELP_EDIT = IMAGE_HELP + " Leave it empty to keep the current image."
IMAGE_REQUIRED = "Choose an image of what you built."
ALT_LABEL = "Image description"
ALT_HELP = (
    "What the image shows, for people who can't see it. Optional; the title is used without it."
)
ALT_TOO_LONG = "Keep the image description to 200 characters or fewer."
TAGS_FIELD_LABEL = "Tags"
TAGS_HELP = "Up to 5, separated by commas or spaces: terrain, luau, ray-tracing."
TAGS_TOO_MANY = "Use at most 5 tags."
TAG_INVALID = "A tag is 2 to 24 lower-case letters or digits, words joined by hyphens."
TAG_INVALID_NAMED = (
    "“{name}” can't be a tag: use 2 to 24 letters or digits, words joined by hyphens."
)
SHOWCASE_LIMIT_REACHED = "You can publish {limit} showcase a day. You can publish again in {wait}."

# Deleting.
DELETE_TITLE = "Delete showcase"
DELETE_LEDE = "This deletes the showcase, its image and its likes. It can't be undone."
DELETE_CONFIRM = "Delete showcase"
KEEP = "Keep it"
DELETED = "Showcase deleted."
