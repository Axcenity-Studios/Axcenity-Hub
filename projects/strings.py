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
LIST_LEDE = (
    "Your engine projects in the Hub. Link each one to its GitHub repository and the Hub keeps "
    "the repository's details current."
)
LIST_COUNT = "{count} of {limit} projects"
NEW_PROJECT = "New project"
EMPTY_TITLE = "Start your first project."
EMPTY_LEDE = (
    "Create a project, then connect its GitHub repository in four short steps. Each step "
    "explains what to do as you reach it."
)
SETUP_LABEL = "Repository setup"
SETUP_COMPLETE = "Connected"
SETUP_PROGRESS = "{done} of {total}"
NO_REPOSITORY_YET = "No repository yet"
CREATE_TITLE = "New project"
CREATE_LEDE = "Give it a name. Next you'll connect its GitHub repository, step by step."
CREATE = "Create project"
EDIT_TITLE = "Edit project"
EDIT = "Edit"
SAVE = "Save changes"
CANCEL = "Cancel"
DELETE = "Delete project"
DELETE_TITLE = "Delete this project?"
DELETE_LEDE = (
    "This removes the project and its repository link from the Hub. Nothing on GitHub changes: "
    "remove the repository's webhook there yourself."
)
NO_DESCRIPTION = "No description yet."
CREATED = "Project created. Next, connect its GitHub repository."
SAVED = "Project saved."
DELETED = "Project deleted."

# The repository panel.
REPOSITORY = "Repository"
REPOSITORY_LINKED = "Repository linked. Next, add its webhook on GitHub."
REPOSITORY_UNLINKED = "Repository unlinked. Remove its webhook on GitHub too."
REPOSITORY_REFRESHED = "Repository details updated from GitHub."
REPOSITORY_UNLINK = "Unlink"
REPOSITORY_REFRESH = "Refresh from GitHub"
REPOSITORY_ON_GITHUB = "View on GitHub"
REPOSITORY_ARCHIVED = "Archived"
REPOSITORY_PRIVATE = "Private"
REPOSITORY_PUBLIC = "Public"
REPOSITORY_LIVE = "Live updates"
REPOSITORY_POLLED = "Hourly updates"
VISIBILITY = "Visibility"
DEFAULT_BRANCH = "Default branch"
LAST_PUSH = "Last push"
UPDATED = "Updated"
NEVER = "Never"
STALE_NOTICE = "Showing the details GitHub gave on {when}. {reason}"
RETRY_AFTER = "Try again after {when}."

# The setup checklist on a project's page (projects.setup). {placeholders} are filled in by
# the view.
SETUP_TITLE = "Set up your repository"
SETUP_DONE_TITLE = "Repository connected"
SETUP_DONE_NOTE = "GitHub tells the Hub about pushes, renames and deletions as they happen."
SETUP_OFF_NOTE = "Live updates aren't available on this Hub yet."
SETUP_SHOW = "Show steps"
SETUP_HIDE = "Hide steps"
STEP_STATES = {
    "done": "Done",
    "current": "Next",
    "attention": "Needs attention",
    "waiting": "Waiting",
    "off": "Not available",
}
STEPS = {
    "account": {
        "title": "Link your GitHub account",
        "icon": "chain",
        "current": (
            "The Hub checks your role on a repository with your own GitHub account. Linking "
            "asks GitHub for no extra permissions: only your public profile and public "
            "repositories."
        ),
        "attention": (
            "GitHub no longer accepts your linked account: it was revoked or has expired. "
            "Reconnect it to keep managing this repository."
        ),
        "done": "Linked as {login}.",
        "action": "Go to Connected accounts",
        "attention_action": "Reconnect on Connected accounts",
    },
    "repository": {
        "title": "Link a repository",
        "icon": "repo",
        "current": (
            "Choose a public repository you're an admin of on GitHub. A repository can belong "
            "to one Hub project."
        ),
        "waiting": "Link your GitHub account first.",
        "attention": "GitHub reports this repository was deleted. Unlink it, then link another.",
        "done": "{full_name} on GitHub.",
        "field": "GitHub repository",
        "placeholder": "owner/name",
        "help": "owner/name, or the repository's github.com address.",
        "action": "Link repository",
    },
    "webhook": {
        "title": "Add the webhook on GitHub",
        "icon": "hook",
        "current": (
            "A webhook makes GitHub tell the Hub about pushes, renames and deletions as they "
            "happen. Show this repository's settings, then add them on GitHub. The Hub checks "
            "you're still an admin of the repository first."
        ),
        "waiting": "Link a repository first.",
        "done": "Settings shown. You can show them again at any time.",
        "off": (
            "Live updates aren't turned on for this Hub yet, so GitHub can't send them. Your "
            "repository is still linked: its details refresh from GitHub when you open the "
            "project (at most hourly), or when you press Refresh from GitHub."
        ),
        "off_operator": (
            "Running this Hub yourself? Set GITHUB_WEBHOOK_SECRET in its .env and restart it to "
            "turn webhooks on."
        ),
        "show": "Show webhook settings",
        "show_again": "Show settings again",
        "hide": "Hide settings",
        "open_github": "Open GitHub's Add webhook page",
        "instructions": (
            "On GitHub, open the repository's Settings, then Webhooks, then Add webhook. Fill "
            "in these four fields, leave the rest as they are, and press Add webhook."
        ),
        "secret_note": (
            "This secret is for this repository's link only: don't share it. Unlinking and "
            "linking again gives a new address and secret."
        ),
        "local": (
            "GitHub can't reach {host}: it's this computer. Set HUB_PUBLIC_URL in the Hub's .env "
            "to an https:// address GitHub can reach, then restart it: the payload URL here "
            "will use that address."
        ),
    },
    "delivery": {
        "title": "Wait for GitHub's first delivery",
        "icon": "ping",
        "current": (
            "GitHub sends a ping as soon as the webhook is added. Reload this page to see "
            "whether it arrived."
        ),
        "waiting": "Add the webhook first.",
        "done": "First delivery {first}. Latest {last}.",
        "off": "Comes after the webhook, once live updates are turned on for this Hub.",
        "trouble": (
            "Nothing yet? On GitHub, open the webhook's Recent Deliveries tab. This step's help "
            "explains each response."
        ),
        "action": "Check again",
    },
}
# GitHub's Add webhook form, field by field: (GitHub's label, what to enter, copyable). The
# payload URL and secret come from the link (projects.services.webhook_settings).
WEBHOOK_FIELDS = [
    ("Payload URL", "{payload_url}", True),
    ("Content type", "application/json", False),
    ("Secret", "{secret}", True),
    ("Which events?", "Let me select individual events: Pushes and Repositories", False),
]
COPY = "Copy"
COPIED = "Copied"
COPY_FAILED = "Press Ctrl+C"
COPY_LABEL = "Copy {field}"

# Help on the setup checklist: each step's own (folded, unless it's the member's first
# repository and the step is current), and what to have ready before starting.
HELP_LABEL = "Help with this step"
HELP_BEFORE_TITLE = "Before you start"
HELP_BEFORE = [
    "A Hub account with a verified email address.",
    "A GitHub account.",
    "A public repository on GitHub that you're an admin of (you created it, or its owner made "
    "you an admin).",
]
HELP_STEPS = {
    "account": [
        "Press Go to Connected accounts (it's also a tab of Account settings), then Link GitHub.",
        "GitHub asks you to authorise Axcenity Hub. It asks for no extra permissions: the Hub "
        "can read only public information, and it can never change anything on GitHub.",
        "You come back to Connected accounts, showing your GitHub username.",
    ],
    "repository": [
        "Enter the repository as owner/name (for example "
        "axcenity-studios/space-game), or paste its github.com address.",
        "The Hub asks GitHub whether you're an admin of it. If you're not, or it's private, "
        "the Hub says so and links nothing.",
        "Each repository can belong to one Hub project, and each project has one repository.",
    ],
    "webhook": [
        "Press Show webhook settings. The Hub shows a payload URL and a secret "
        "made for this repository alone.",
        "Press Open GitHub's Add webhook page (or go to the repository's Settings, then "
        "Webhooks, then Add webhook).",
        "Copy the payload URL and the secret across, set Content type to application/json, "
        "choose “Let me select individual events”, tick Pushes and Repositories, and press "
        "Add webhook.",
    ],
    "delivery": [
        "GitHub sends a ping straight away. Reload this page: the last step turns Done and "
        "the repository shows Live updates.",
        "From then on, pushes, renames, archiving and deletion reach the Hub within seconds.",
    ],
}
HELP_ACCESS_TITLE = "What the Hub can and can't do"
HELP_ACCESS = [
    "It reads the repository's public details: its name, description, default branch, "
    "visibility and when it was last pushed to.",
    "It checks your role on the repository with GitHub before anything that depends on it. "
    "If an owner removes you, the Hub stops letting you act within a minute.",
    "It never writes to GitHub, never reads private repositories, and never sees your GitHub "
    "password. Your GitHub token is stored encrypted and deleted when you unlink.",
    "Without a webhook, the details refresh from GitHub when you open the project (at most "
    "hourly).",
]
HELP_TROUBLE_TITLE = "If a delivery fails"
HELP_TROUBLE_LEDE = (
    "On GitHub, open the repository's Settings, then Webhooks, choose the Hub's webhook and "
    "open Recent Deliveries. Each delivery shows the Hub's response:"
)
HELP_TROUBLE_HEAD = ("Response", "What it means", "What to do")
HELP_TROUBLE = [
    ("200 ok", "Received and applied.", "Nothing: it works."),
    (
        "202 ignored",
        "An event the Hub doesn't use.",
        "Nothing. Only Pushes and Repositories are needed.",
    ),
    (
        "400 malformed delivery",
        "The content type isn't JSON.",
        "Edit the webhook and set Content type to application/json.",
    ),
    (
        "403 signature missing or invalid",
        "The secret doesn't match.",
        "Show the webhook settings in the Hub again and paste the secret exactly. Relinking "
        "the repository gives a new secret.",
    ),
    (
        "404",
        "The payload URL isn't this repository's link.",
        "The repository was unlinked and linked again: paste the new payload URL.",
    ),
    (
        "409 delivery already received",
        "GitHub sent a delivery the Hub already has (Redeliver does this).",
        "Nothing: the Hub refuses repeats on purpose.",
    ),
    (
        "Couldn't connect",
        "GitHub couldn't reach the Hub.",
        "Check the payload URL: it must be the Hub's address on the internet.",
    ),
]
HELP_UNLINK = (
    "Unlinking makes the Hub forget the repository at once. It asks GitHub nothing, so it works "
    "even if you've lost access. Then delete the webhook on GitHub (Settings, Webhooks), since "
    "the Hub can't."
)
