"""The project pages' copy and messages, as data."""

# Names and the limit.
NAME_TAKEN = "A project with this name already exists."
NAME_REQUIRED = "Give the project a name."
NAME_UNUSABLE = "Use at least one letter or digit, and not just “new” or “hooks”."
LIMIT_REACHED = "You already own 5 projects, the most one member can. Delete one to create another."

# Repository actions refused by the Hub's own rules.
PROJECT_HAS_REPOSITORY = "This project already has a repository. Unlink it to link another."
REPOSITORY_NAME_INVALID = (
    "Enter the repository as owner/name (for example axcenity-studios/space-game) or its "
    "GitHub address."
)
REPOSITORY_TAKEN = "This repository is already linked to a Hub project."
NO_REPOSITORY = "This project has no linked repository."
REPOSITORY_REPLACED = (
    "The name now belongs to a different repository on GitHub. Unlink it, then link the "
    "repository you mean."
)
WEBHOOKS_OFF = (
    "Webhooks aren't set up on this server, so details refresh when you open the project."
)

# Repository actions refused by what GitHub said, by projects.github.Reason.
REFUSED = {
    "no_github": "Link your GitHub account first, under Connected accounts.",
    "reconnect": (
        "GitHub no longer accepts your linked account. Reconnect it under Connected accounts."
    ),
    "insufficient": "GitHub says you don't have the permission this needs on the repository.",
    "no_access": (
        "GitHub didn't show you this repository: it doesn't exist, it's private, or your "
        "access was removed."
    ),
    "unverifiable": (
        "GitHub didn't report your permission on this repository, so the Hub can't allow this."
    ),
    "rate_limited": "GitHub's request limit for your account was reached. Try again later.",
    "unavailable": "GitHub couldn't be reached just now. Try again in a few minutes.",
}

# Pages.
LIST_TITLE = "Projects"
LIST_LEDE = "Your engine projects, each with an optional GitHub repository."
LIST_EMPTY = "You don't have any projects yet."
LIST_COUNT = "{count} of {limit} projects"
NEW_PROJECT = "New project"
CREATE_TITLE = "New project"
CREATE_LEDE = "Give it a name; you can link a GitHub repository once it exists."
CREATE = "Create project"
EDIT_TITLE = "Edit project"
EDIT = "Edit"
SAVE = "Save changes"
CANCEL = "Cancel"
DELETE = "Delete project"
DELETE_TITLE = "Delete this project?"
DELETE_LEDE = (
    "This removes the project and its repository link from the Hub. Nothing on GitHub changes."
)
NO_DESCRIPTION = "No description."
CREATED = "Project created."
SAVED = "Project saved."
DELETED = "Project deleted."

REPOSITORY = "Repository"
REPOSITORY_NONE = "No repository is linked."
REPOSITORY_LINK = "Link repository"
REPOSITORY_LINK_NOTE = (
    "The Hub checks with GitHub that you're an admin of the repository. It asks GitHub for no "
    "extra permissions, so only public repositories can be linked."
)
REPOSITORY_NEEDS_GITHUB = "Link your GitHub account first, under Connected accounts."
CONNECTED_ACCOUNTS = "Connected accounts"
REPOSITORY_LINKED = "Repository linked."
REPOSITORY_UNLINKED = "Repository unlinked. Remove its webhook on GitHub too."
REPOSITORY_REFRESHED = "Repository details updated from GitHub."
REPOSITORY_UNLINK = "Unlink"
REPOSITORY_REFRESH = "Refresh from GitHub"
REPOSITORY_WEBHOOK = "Set up webhook"
REPOSITORY_DELETED = "GitHub reports this repository was deleted. Unlink it, or link another."
REPOSITORY_ARCHIVED = "Archived"
REPOSITORY_PRIVATE = "Private"
REPOSITORY_PUBLIC = "Public"
DEFAULT_BRANCH = "Default branch"
LAST_PUSH = "Last push"
DETAILS_FROM = "Details from"
NEVER = "Never"
VIA_WEBHOOK = "Last webhook"
STALE_NOTICE = "Showing the details GitHub gave on {when}. {reason}"
RETRY_AFTER = "Try again after {when}."
VISIBILITY = "Visibility"

WEBHOOK_TITLE = "Set up the repository's webhook"
WEBHOOK_LEDE = (
    "Add a webhook in the repository on GitHub (Settings → Webhooks → Add webhook) with these "
    "values, so the Hub hears about renames, pushes and deletions as they happen."
)
WEBHOOK_URL = "Payload URL"
WEBHOOK_CONTENT_TYPE = "Content type"
WEBHOOK_SECRET = "Secret"
WEBHOOK_EVENTS = "Events"
WEBHOOK_EVENTS_VALUE = "Let me select individual events: Pushes and Repositories"
WEBHOOK_SECRET_NOTE = (
    "This secret belongs to this repository's link only. Don't share it; unlinking and linking "
    "again gives a new one."
)
BACK_TO_PROJECT = "Back to the project"
GITHUB_DESCRIPTION = "Description on GitHub"
