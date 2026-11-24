"""A project's repository setup as four steps, each with its state, from the real records.

1. **Link your GitHub account** (Connected accounts): done when the member has a working
   GitHub link; needs attention when GitHub refused its token.
2. **Link a repository**: done when the project has one; needs attention when GitHub reports
   it deleted.
3. **Add the webhook on GitHub**: done once the owner has opened the webhook's settings
   (or a delivery has arrived).
4. **Wait for GitHub's first delivery**: done when one has arrived (GitHub pings at once).

Steps 3 and 4 are "off" when this server has no webhook secret: the repository is linked, but
GitHub can't send live updates, so the setup isn't complete (it never claims to be). A step
after an unfinished one waits. The project page shows the first step that isn't done as the
current one.
"""

from dataclasses import dataclass
from enum import StrEnum

from . import github, webhooks
from .models import RepositoryLink


class State(StrEnum):
    DONE = "done"
    CURRENT = "current"  # the step to do now
    ATTENTION = "attention"  # was done, now needs the member (a refused token, a deleted repo)
    WAITING = "waiting"  # an earlier step comes first
    OFF = "off"  # not available on this server


@dataclass(frozen=True)
class Step:
    key: str
    number: str
    state: State

    @property
    def open(self) -> bool:
        """Whether the page shows this step's instructions and action."""
        return self.state in (State.CURRENT, State.ATTENTION)


@dataclass(frozen=True)
class Setup:
    steps: tuple[Step, ...]

    @property
    def done(self) -> int:
        return sum(step.state is State.DONE for step in self.steps)

    @property
    def total(self) -> int:
        return len(self.steps)

    @property
    def complete(self) -> bool:
        return self.done == self.total

    @property
    def live_updates_off(self) -> bool:
        """The server has webhooks off: steps 3 and 4 can't be done here."""
        return any(step.state is State.OFF for step in self.steps)

    def step(self, key: str) -> Step:
        return next(step for step in self.steps if step.key == key)


def setup_for(user, link: RepositoryLink | None) -> Setup:
    """The setup steps for `user`'s project whose repository link is `link` (or None)."""
    account = github.member_link(user)
    states: dict[str, State] = {}
    if account is None:
        states["account"] = State.CURRENT
    else:
        states["account"] = State.ATTENTION if account.needs_reconnect else State.DONE

    if link is not None:
        states["repository"] = State.ATTENTION if link.deleted_on_github else State.DONE
    else:
        states["repository"] = State.CURRENT if states["account"] is State.DONE else State.WAITING

    if not webhooks.webhooks_on():
        states["webhook"] = states["delivery"] = State.OFF
    else:
        delivered = link is not None and link.first_webhook_at is not None
        shown = link is not None and (link.webhook_shown_at is not None or delivered)
        ready = link is not None and states["repository"] is State.DONE
        if shown:
            states["webhook"] = State.DONE
        else:
            states["webhook"] = State.CURRENT if ready else State.WAITING
        if delivered:
            states["delivery"] = State.DONE
        else:
            states["delivery"] = State.CURRENT if shown else State.WAITING
    # Only the first unfinished step is current; later ones wait behind it.
    seen_open = False
    steps = []
    for number, key in enumerate(("account", "repository", "webhook", "delivery"), start=1):
        state = states[key]
        if state is State.CURRENT and seen_open:
            state = State.WAITING
        if state in (State.CURRENT, State.ATTENTION):
            seen_open = True
        steps.append(Step(key, f"{number:02d}", state))
    return Setup(tuple(steps))
