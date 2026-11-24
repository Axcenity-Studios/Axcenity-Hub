"""The project pages' copy and messages, as data."""

# Names and the limit.
NAME_TAKEN = "A project with this name already exists."
NAME_REQUIRED = "Give the project a name."
NAME_UNUSABLE = "Use at least one letter or digit, and not just “new”, “guide” or “hooks”."
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
    "Create a project, then connect its GitHub repository in four short steps. The setup "
    "guide walks through each one."
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
GUIDE_LINK = "Setup guide"

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
SETUP_DONE_NOTE_OFF = "Its details refresh from GitHub when you open the project."
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
            "This Hub has no webhook secret set, so webhooks are off. The repository's details "
            "refresh when you open the project instead."
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
            "This Hub is running on your own computer ({host}), so GitHub can't reach this "
            "address. To try webhooks, put the Hub behind a tunnel first: see the guide's "
            "“Testing on your own computer”."
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
        "off": "Needs webhooks, which are off on this Hub.",
        "trouble": (
            "Nothing yet? On GitHub, open the webhook's Recent Deliveries tab: the guide "
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

# The setup guide (/projects/guide/): public, so it can be shared and read before signing up.
GUIDE_TITLE = "Connect a GitHub repository"
GUIDE_LEDE = (
    "Link a Hub project to its repository on GitHub, and the Hub keeps the repository's "
    "details current as you push, rename or archive it. It takes four steps and a couple of "
    "minutes."
)
GUIDE_START = "Go to your projects"
GUIDE_SIGN_IN = "Sign in to start"
GUIDE_BEFORE_TITLE = "Before you start"
GUIDE_BEFORE = [
    "A Hub account with a verified email address.",
    "A GitHub account.",
    "A public repository on GitHub that you're an admin of (you created it, or its owner made "
    "you an admin).",
    "A Hub project to connect it to: create one from Projects.",
]
GUIDE_STEPS_TITLE = "The four steps"
GUIDE_STEPS = {
    "account": [
        "In the Hub, open Connected accounts (in the menu under Account) and press Link GitHub.",
        "GitHub asks you to authorise Axcenity Hub. It asks for no extra permissions: the Hub "
        "can read only public information, and it can never change anything on GitHub.",
        "You come back to Connected accounts, showing your GitHub username.",
    ],
    "repository": [
        "Open your project and enter the repository as owner/name (for example "
        "axcenity-studios/space-game), or paste its github.com address.",
        "The Hub asks GitHub whether you're an admin of it. If you're not, or it's private, "
        "the Hub says so and links nothing.",
        "Each repository can belong to one Hub project, and each project has one repository.",
    ],
    "webhook": [
        "On your project, press Show webhook settings. The Hub shows a payload URL and a secret "
        "made for this repository alone.",
        "Press Open GitHub's Add webhook page (or go to the repository's Settings, then "
        "Webhooks, then Add webhook).",
        "Copy the payload URL and the secret across, set Content type to application/json, "
        "choose “Let me select individual events”, tick Pushes and Repositories, and press "
        "Add webhook.",
    ],
    "delivery": [
        "GitHub sends a ping straight away. Reload your project: the last step turns Done and "
        "the repository shows Live updates.",
        "From then on, pushes, renames, archiving and deletion reach the Hub within seconds.",
    ],
}
GUIDE_ACCESS_TITLE = "What the Hub can and can't do"
GUIDE_ACCESS = [
    "It reads the repository's public details: its name, description, default branch, "
    "visibility and when it was last pushed to.",
    "It checks your role on the repository with GitHub before anything that depends on it. "
    "If an owner removes you, the Hub stops letting you act within a minute.",
    "It never writes to GitHub, never reads private repositories, and never sees your GitHub "
    "password. Your GitHub token is stored encrypted and deleted when you unlink.",
    "Without a webhook, the details refresh from GitHub when you open the project (at most "
    "hourly).",
]
GUIDE_TROUBLE_TITLE = "If a delivery fails"
GUIDE_TROUBLE_LEDE = (
    "On GitHub, open the repository's Settings, then Webhooks, choose the Hub's webhook and "
    "open Recent Deliveries. Each delivery shows the Hub's response:"
)
GUIDE_TROUBLE_HEAD = ("Response", "What it means", "What to do")
GUIDE_TROUBLE = [
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
        "Check the payload URL. A Hub running on your own computer needs a tunnel (below).",
    ),
]
GUIDE_UNLINK_TITLE = "Unlinking"
GUIDE_UNLINK = (
    "Unlink from the repository panel on your project. The Hub forgets the repository at once, "
    "and asks GitHub nothing, so it works even if you've lost access. Then delete the webhook on "
    "GitHub (Settings, Webhooks), since the Hub can't."
)
GUIDE_LOCAL_TITLE = "Testing on your own computer"
GUIDE_LOCAL = [
    "GitHub can only deliver to an address on the internet, not to localhost or 127.0.0.1.",
    "Start a tunnel to the Hub, for example Cloudflare's (the command below). It prints an "
    "https://….trycloudflare.com address.",
    "Allow that address: add .trycloudflare.com to DJANGO_ALLOWED_HOSTS, and set "
    "GITHUB_WEBHOOK_SECRET, in the Hub's .env, then restart it.",
    "Use the payload URL the Hub shows with the tunnel's https:// address in place of "
    "http://127.0.0.1:8000. A new tunnel gets a new address: edit the webhook to match.",
]
GUIDE_LOCAL_COMMAND = "cloudflared tunnel --url http://127.0.0.1:8000"
GUIDE_LOCAL_NOTE = "Only for running the Hub yourself: members of a hosted Hub never need this."
