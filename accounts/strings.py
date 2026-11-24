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

# The app shell's rail: (key, label, URL name, icon), in order. Later phases add sections.
RAIL_HEADING = "Account"
RAIL_ACCOUNT = [
    ("profile", "Profile", "accounts:profile", "user"),
    ("email", "Email", "account_email", "mail"),
    ("password", "Password", "account_change_password", "lock"),
    ("two_factor", "Two-factor", "mfa_index", "shield"),
    ("connections", "Connected accounts", "socialaccount_connections", "link"),
]
# Which rail item a page belongs to, by its view name (allauth's pages included).
RAIL_PAGES = {
    "accounts:profile": "profile",
    "account_email": "email",
    "accounts:verify_email": "email",
    "account_change_password": "password",
    "account_set_password": "password",
    "socialaccount_connections": "connections",
}
SIGN_OUT = "Sign out"
APP_PLACE = "Hub"
ACCOUNT_MENU = "Account menu"

# Page copy.
PROFILE_TITLE = "Profile"
PROFILE_LEDE = "What other members see beside your posts and projects."
PROFILE_SAVE = "Save profile"
ACCOUNT_DETAILS = "Account"
USERNAME = "Username"
USERNAME_NOTE = "Usernames can't be changed yet."
EMAIL = "Email"
VERIFIED = "Verified"
NOT_VERIFIED = "Not verified"
TWO_FACTOR = "Two-factor sign-in"
MANAGE = "Manage"
EMAIL_TITLE = "Email"
EMAIL_LEDE = "Where we send sign-in links, password resets and notices."
EMAIL_ONE_ADDRESS = (
    "Each account has one email address, and no two accounts share one. "
    "Changing your address isn't available yet."
)
RESEND = "Send the verification link again"
VERIFY_TITLE = "Verify your email"
CONTINUE = "Continue"

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
