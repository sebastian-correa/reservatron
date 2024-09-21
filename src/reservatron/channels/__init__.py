"""Different reservable channels like a gym."""

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from functools import wraps
from typing import Concatenate, ParamSpec, TypeVar
from zoneinfo import ZoneInfo

from pydantic import BaseModel

from reservatron.timeutils import localize


class Credentials(BaseModel):
    """Credentials to log in to a channel."""

    username: str
    password: str


class Channel(ABC):
    """Different reservable channels like a gym.

    Args:
        credentials (Credentials): The credentials to log in to the channel.

    Attributes:
        timezone (ZoneInfo): The timezone of the channel.
        credentials (Credentials): The credentials to log in to the channel.
        is_logged_in (bool): Whether the channel is logged in or not.
    """

    timezone: ZoneInfo

    def __init__(self, credentials: Credentials) -> None:
        self.credentials = credentials
        self.is_logged_in = False

    @classmethod
    def localize(cls, dt: datetime) -> datetime:
        """Use `reservatron.timeutils.localize` with the channel's timezone to localize a datetime.

        Args:
            dt (datetime): The datetime to localize. Forwarded to `reservatron.timeutils.localize`.

        Returns:
            datetime: The localized datetime.
        """
        return localize(dt, cls.timezone)

    @abstractmethod
    def login(self) -> None:
        """Login to the channel. Raises an exception if the login fails."""


ChannelT = TypeVar("ChannelT", bound=Channel)
T = TypeVar("T")
P = ParamSpec("P")


def requires_login(
    function: Callable[Concatenate[ChannelT, P], T],
) -> Callable[Concatenate[ChannelT, P], T]:
    """Decorator to ensure the channel is logged in before calling the decorated function.

    This is checked with the `is_logged_in` attribute of the `Channel`.

    Args:
        function (Callable[Concatenate[ChannelT, P], T]): The function that requires being logged
            in.

    Returns:
        Callable[Concatenate[ChannelT, P], T]: The function that checks if it's logged in before
            proceeding.
    """

    @wraps(function)
    def wrapper(self: ChannelT, *args: P.args, **kwargs: P.kwargs) -> T:
        if not self.is_logged_in:
            self.login()
        return function(self, *args, **kwargs)

    return wrapper
