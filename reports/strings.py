"""The report pages' copy and messages, as data."""

# Reasons.
REASON_SPAM = "Spam or advertising"
REASON_ABUSE = "Harassment or abuse"
REASON_OFF_TOPIC = "Off-topic"
REASON_OTHER = "Something else"

# The report form.
TITLE = "Report {label}"
LEDE = (
    "Tell the moderators what's wrong. They see your report and the {label}; the author "
    "isn't told who reported it."
)
REASON_LABEL = "What's wrong?"
REASON_REQUIRED = "Choose what's wrong."
DETAILS_LABEL = "Details"
DETAILS_HELP = "Optional, unless you chose “Something else”. Plain text."
DETAILS_REQUIRED = "Say what's wrong, since you chose “Something else”."
DETAILS_TOO_LONG = "Keep the details to %(limit_value)d characters (it has %(show_value)d)."
SUBMIT = "Send report"
CANCEL = "Cancel"
REPORTING = "Reporting"

# Answers.
THANKS = "Thanks for the report. A moderator will look at this {label}."
ALREADY_TITLE = "Already reported"
ALREADY = "You've already reported this {label}. A moderator will look at it."
BACK = "Back to the {label}"
