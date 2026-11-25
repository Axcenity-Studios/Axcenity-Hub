"""The account pages' copy (the app shell's rail, notices and messages), as data."""

PROFILE_SAVED = "Profile saved."
VERIFICATION_SENT = "We've sent a new verification link. Check your inbox."
VERIFICATION_WAIT = (
    "A verification link was sent a moment ago. Check your inbox, or try again in a few minutes."
)
VERIFY_TO_CONTRIBUTE = (
    "Verify your email address before you post, create a project or send a report. "
    "Everything else works while you wait."
)
UNVERIFIED_NOTICE = "Your email address isn't verified yet."
TWO_FACTOR_ON = "On: an authenticator app"
TWO_FACTOR_OFF = "Off"

# The app shell's rail: sections of (key, label, URL name, icon), in order. Later phases
# add items and sections. Every account page is one rail item, "account": its pages are the
# tabs of Account settings (ACCOUNT_TABS).
RAIL_HEADING = "Account"
RAIL_HUB_HEADING = "Workspace"
RAIL_HUB = [
    ("projects", "Projects", "projects:list", "folder"),
]
RAIL_ACCOUNT = [
    ("account", "Account settings", "accounts:profile", "user"),
]
# Account settings' tabs: (key, label, URL name, icon), in order.
ACCOUNT_TABS = [
    ("profile", "Profile", "accounts:profile", "user"),
    ("email", "Email", "account_email", "mail"),
    ("password", "Password", "account_change_password", "lock"),
    ("two_factor", "Two-factor", "mfa_index", "shield"),
    ("connections", "Connected accounts", "socialaccount_connections", "link"),
]
# Which page a view is, by its view name (allauth's pages included; every mfa_* page is
# two_factor).
PAGES = {
    "accounts:profile": "profile",
    "account_email": "email",
    "accounts:verify_email": "email",
    "account_change_password": "password",
    "account_set_password": "password",
    "socialaccount_connections": "connections",
}
# Every page of these URL namespaces belongs to a rail item.
RAIL_NAMESPACES = {"projects": "projects"}
RAIL_LABEL = "Menu"
SIGN_OUT = "Sign out"
SIGN_IN = "Sign in"
APP_PLACE = "Account center"
ACCOUNT_MENU = "Account menu"
MENU_SETTINGS = "Account settings"

# Account settings' header: who's signed in and the state of their account at a glance.
SETTINGS_LABEL = "Account settings"
MEMBER_SINCE = "Member since {date}"
STATUS_EMAIL = "Email"
STATUS_TWO_FACTOR = "Two-factor"
STATUS_GITHUB = "GitHub"
GITHUB_LINKED_SHORT = "Linked"
GITHUB_NOT_LINKED_SHORT = "Not linked"
GITHUB_RECONNECT_SHORT = "Reconnect"
TWO_FACTOR_ON_SHORT = "On"
TWO_FACTOR_OFF_SHORT = "Off"
PHOTO_ALT = "Profile photo of {name}"

# Profile.
PROFILE_TITLE = "Profile"
PROFILE_LEDE = "What other members see beside your posts and projects."
PROFILE_EDIT = "Edit profile"
PROFILE_SAVE = "Save profile"
PROFILE_PREVIEW = "Preview"
PROFILE_PREVIEW_TAG = "As others see you"
PROFILE_NO_BIO = "No bio yet."
PHOTO_TITLE = "Photo"
PHOTO_NONE = "No photo yet: your initial is shown instead."
ACCOUNT_DETAILS = "Account"
USERNAME = "Username"
USERNAME_NOTE = "Usernames can't be changed yet."
JOINED = "Joined"
EMAIL = "Email"
VERIFIED = "Verified"
NOT_VERIFIED = "Not verified"
TWO_FACTOR = "Two-factor sign-in"
MANAGE = "Manage"

# Email.
EMAIL_TITLE = "Email"
EMAIL_LEDE = "Where we send verification links and password resets."
EMAIL_ADDRESS = "Your address"
EMAIL_STATUS = "Status"
EMAIL_USED_FOR = "Used for"
EMAIL_USED_FOR_VALUE = "Signing in, verification, password resets"
EMAIL_ONE_ADDRESS = (
    "Each account has one email address, and no two accounts share one. "
    "Changing your address isn't available yet."
)
EMAIL_SENDS_TITLE = "What we send"
EMAIL_SENDS = [
    (
        "mail",
        "Verification links",
        "To confirm this address is yours: when you sign up, and whenever you ask for another.",
    ),
    (
        "key",
        "Password reset links",
        "Only when someone asks to reset this account's password. Each link works once, "
        "within an hour.",
    ),
    ("check", "Nothing else", "No newsletters and no marketing."),
]
RESEND = "Send the verification link again"
VERIFY_TITLE = "Verify your email"
CONTINUE = "Continue"

# Password (templates/account/password_change.html). The rules are the validators in
# settings.AUTH_PASSWORD_VALIDATORS, in words.
PASSWORD_TITLE = "Password"
PASSWORD_LEDE = "Change the password you sign in with. You stay signed in on this browser."
PASSWORD_FORM = "Change password"
PASSWORD_SAVE = "Change password"
PASSWORD_RULES_TITLE = "A good password"
PASSWORD_RULES = [
    "At least 8 characters: a few unrelated words make a long one easy to remember.",
    "Not like your username or email address.",
    "Not a commonly used password, and not only numbers.",
    "Not one you use on another site.",
]
PASSWORD_AFTER = "Changing it signs your account out of every other browser."

# Two-factor (templates/mfa/index.html; allauth's other two-factor pages keep their words).
TWO_FACTOR_TITLE = "Two-factor sign-in"
TWO_FACTOR_LEDE = (
    "Ask for a code from your phone as well as your password, so a stolen password alone "
    "can't open your account."
)
TWO_FACTOR_METHODS = "Sign-in methods"
TOTP_TITLE = "Authenticator app"
TOTP_ON = "Active: signing in asks for the six-digit code your app shows."
TOTP_OFF = (
    "Not set up. Any authenticator app works: scan a QR code with it, then enter the code it shows."
)
TOTP_ACTIVATE = "Activate"
TOTP_DEACTIVATE = "Deactivate"
CODES_TITLE = "Recovery codes"
CODES_ON = (
    "{unused} of {total} codes left. Each one signs you in once, for when your phone isn't "
    "with you. Keep them somewhere safe."
)
CODES_OFF = "Made when you activate an authenticator app."
CODES_LEFT = "{unused} left"
CODES_NONE = "None yet"
CODES_VIEW = "View"
CODES_DOWNLOAD = "Download"
CODES_GENERATE = "Generate new codes"
STATE_ON = "On"
STATE_OFF = "Off"

# GitHub linking (socialaccount_connections, accounts.adapter.SocialAccountAdapter).
CONNECTIONS_TITLE = "Connected accounts"
CONNECTIONS_LEDE = (
    "Link your GitHub account so you can connect your engine repositories to Hub projects. "
    "GitHub is never used to sign in: you always sign in with your email."
)
GITHUB = "GitHub"
GITHUB_ACCOUNT = "Account"
GITHUB_STATUS = "Status"
GITHUB_STATE_OK = "Linked"
GITHUB_STATE_NEEDS_RECONNECT = "Needs reconnecting"
GITHUB_STATE_UNAVAILABLE = "Linked (GitHub couldn't be reached just now)"
GITHUB_RECONNECT_PROMPT = (
    "GitHub no longer accepts this link: it was revoked or has expired. Reconnect to "
    "keep using it, or unlink it."
)
GITHUB_UNAVAILABLE_NOTE = "We'll check again next time. Nothing has changed on your account."
GITHUB_NOT_LINKED = "No GitHub account is linked."
GITHUB_ACCESS_NOTE = (
    "The Hub asks GitHub for no extra permissions: only your public profile and public "
    "repositories. Your GitHub token is stored encrypted and deleted when you unlink."
)
GITHUB_WHAT_TITLE = "What linking does"
GITHUB_WHAT = [
    (
        "folder",
        "Connects repositories to projects",
        "Link a repository to a Hub project and the Hub keeps its details current.",
    ),
    (
        "shield",
        "Checks your role first",
        "Before anything that depends on a repository, the Hub asks GitHub what you may do "
        "with it.",
    ),
    (
        "lock",
        "Never a way to sign in",
        "You always sign in with your email. GitHub only links.",
    ),
]
GITHUB_CONNECT = "Link GitHub"
GITHUB_RECONNECT = "Reconnect GitHub"
GITHUB_UNLINK = "Unlink GitHub"
GITHUB_UNLINK_NOTE = "You'll be asked for your password (or two-factor code) first."
GITHUB_OFF = "GitHub linking isn't available on this server yet."
GITHUB_NOT_SIGN_IN = (
    "GitHub isn't a way to sign in to the Hub. Sign in with your email, then link GitHub "
    "from Connected accounts."
)
GITHUB_LINKED_ELSEWHERE = (
    "That GitHub account is already linked to another Hub account. Unlink it there first."
)
GITHUB_ONE_ACCOUNT = (
    "Your Hub account already has a GitHub account linked. Unlink it before linking another."
)
# allauth's pages when a link doesn't finish (templates/socialaccount/).
GITHUB_LINK_FAILED_TITLE = "GitHub wasn't linked"
GITHUB_LINK_FAILED = (
    "The link didn't finish, so nothing was linked. The request may have expired or come "
    "from another browser. Start again from Connected accounts."
)
GITHUB_LINK_CANCELLED_TITLE = "Linking cancelled"
GITHUB_LINK_CANCELLED = "You cancelled on GitHub, so nothing was linked."
GITHUB_BACK = "Back to Connected accounts"
# allauth's messages (templates/socialaccount/messages/).
GITHUB_LINKED = "GitHub account linked."
GITHUB_RECONNECTED = "GitHub account reconnected."
GITHUB_UNLINKED = "GitHub account unlinked. Its token has been deleted from the Hub."
