"""The forum pages' copy and messages, as data."""

# The list.
TITLE = "Forums"
LEDE = "Ask, answer and share what you know about Axcenity Engine."
NEW_POST = "New post"
SIGN_IN_TO_POST = "Sign in to post"
EMPTY_TITLE = "No posts yet"
EMPTY_TEXT = "Start the first conversation: a question, a tip or something you built."
POSTS_LABEL = "Posts"
BY = "by {author}"
EDITED = "Edited"

# A post.
BACK = "All posts"
POSTED = "Posted {when}"
EDITED_AT = "Edited {when}"
YOURS = "Your post"
EDIT = "Edit"
DELETE = "Delete"
POST_ACTIONS = "Post actions"

# The form.
CREATE_TITLE = "New post"
CREATE_LEDE = "Posts are public: anyone can read them. Only you can edit or delete yours."
EDIT_TITLE = "Edit post"
PUBLISH = "Publish"
SAVE = "Save changes"
CANCEL = "Cancel"
TITLE_LABEL = "Title"
TITLE_HELP = "A short summary of the question or topic."
BODY_LABEL = "Post"
BODY_HELP = "Plain text. Line breaks are kept."
TITLE_REQUIRED = "Give the post a title."
BODY_REQUIRED = "Write something in the post."
TITLE_TOO_LONG = "Keep the title to %(limit_value)d characters (it has %(show_value)d)."
BODY_TOO_LONG = "Keep the post to %(limit_value)d characters (it has %(show_value)d)."

# Deleting.
DELETE_TITLE = "Delete this post?"
DELETE_LEDE = "It's removed for everyone, and it can't be undone."
DELETE_CONFIRM = "Delete post"
KEEP = "Keep it"
DELETED_TITLE = "Post deleted"
DELETED_TEXT = "“{title}” is gone."

# Messages.
CREATED = "Your post is published."
SAVED = "Your changes are saved."
DELETED = "Your post was deleted."

# Limits.
COMMENT_LIMIT_REACHED = (
    "You've posted {limit} comments in the last minute. You can comment again in {wait}."
)
POST_LIMIT_REACHED = (
    "You've published {limit} posts in the last 24 hours. You can post again in {wait}."
)

# Comments.
COMMENTS_TITLE = "Comments"
NO_COMMENTS = "No comments yet."
COMMENT_LABEL = "Add a comment"
COMMENT_HELP = "Plain text. Line breaks are kept."
COMMENT_SUBMIT = "Comment"
COMMENT_REQUIRED = "Write something in the comment."
COMMENT_TOO_LONG = "Keep the comment to %(limit_value)d characters (it has %(show_value)d)."
SIGN_IN_TO_COMMENT = "Sign in to comment"
YOUR_COMMENT = "Your comment"
COMMENT_ACTIONS = "Comment actions"
COMMENTED = "Your comment is posted."
DELETE_COMMENT_TITLE = "Delete this comment?"
DELETE_COMMENT_LEDE = "It's removed for everyone, and it can't be undone."
DELETE_COMMENT_CONFIRM = "Delete comment"
COMMENT_DELETED = "Your comment was deleted."
COMMENT_BY = "Comment by {author}"
COMMENTS_COUNT = "{count} comment"
COMMENTS_COUNT_PLURAL = "{count} comments"

# Ratings.
RATING_TITLE = "Rating"
RATING_AVERAGE = "{average} out of 5"
RATING_COUNT = "{count} rating"
RATING_COUNT_PLURAL = "{count} ratings"
NO_RATINGS = "No ratings yet"
RATE_LABEL = "Rate this post"
RATE_STAR = "Rate {score} out of 5"
YOUR_RATING = "You rated it {score} out of 5."
CLEAR_RATING = "Clear my rating"
SIGN_IN_TO_RATE = "Sign in to rate"
RATE_OWN_POST = "You can't rate your own post."
RATING_OUT_OF_RANGE = "Choose from 1 to 5 stars."
RATED = "Your rating is saved."
RATING_CLEARED = "Your rating is cleared."

# Moderation, as staff see it.
STATE_HIDDEN = "Hidden"
STATE_REMOVED = "Removed"
STAFF_ONLY = "Only staff can see this."

# Reporting.
REPORT = "Report"
REPORTED = "Reported"
