"""The login stage that makes the Hub's email-verification policy.

allauth runs ACCOUNT_EMAIL_VERIFICATION = "mandatory", because only that mode keeps
signup both enumeration-safe and email-unique: a signup with a taken address creates
no account, gets the same "check your inbox" response as a new one, and the owner is
emailed instead. But mandatory also blocks an unverified user's password login, and
the Hub's policy is that they may sign in (the contribution gate in accounts.access
stops them posting, creating or reporting until they verify).

So this stage replaces allauth's EmailVerificationStage through the adapter's
documented `get_login_stages()` hook: a signup gets allauth's mandatory handling
unchanged; any other login (password, after a reset, after confirming the email)
continues without the verification block. Nothing else in allauth changes.
"""

from allauth.account.stages import EmailVerificationStage


class SignupVerificationStage(EmailVerificationStage):
    """allauth's mandatory email verification, applied at signup only."""

    def handle(self):
        if self.login.signup:
            return super().handle()
        return None, True
