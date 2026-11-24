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
]
# Which rail item a page belongs to, by its view name (allauth's pages included).
RAIL_PAGES = {
    "accounts:profile": "profile",
    "account_email": "email",
    "accounts:verify_email": "email",
    "account_change_password": "password",
    "account_set_password": "password",
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
