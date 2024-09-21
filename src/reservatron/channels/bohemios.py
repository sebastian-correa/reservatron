"""Implementation for Bohemios channel.

See more at https://bohemios.uy/.
"""

import logging
from datetime import date, datetime, time
from functools import cache
from typing import cast
from zoneinfo import ZoneInfo

from fake_useragent import FakeUserAgent
from pydantic import BaseModel
from requests import Session

from reservatron.channels import Channel, Credentials, requires_login

logger = logging.getLogger(__name__)


class ActivityCategory(BaseModel):
    """Category with activities. It's an umbrella entity for activities."""

    id: int
    """Unique ID of the category."""
    name: str
    """Name of the category."""
    description: str | None
    """Description of the category, if available."""


class Activity(BaseModel):
    """Activity that can be reserved."""

    id: int
    """Unique ID of the activity."""
    name: str
    """Name of the activity."""
    description: str | None
    """Category of the activity."""


class ActivityTimeSlot(BaseModel):
    """A specific time when an activity can be reserved."""

    activity: Activity
    """Activity that can be reserved."""
    time_slot_id: int
    """Unique ID of the time slot."""
    starts_at: datetime
    """Moment when the activity starts."""
    ends_at: datetime
    """Moment when the activity ends."""
    location: str
    """Location where the activity takes place."""
    max_reservations: int  # TODO: inf or None?
    """Maximum number of reservations allowed."""
    current_reservations: int
    """Current number of reservations."""
    reservation_id: int | None
    """Unique ID of the reservation, if any."""


class InvalidActivityError(ValueError):
    """Raised when an activity with the given bounds (time, name, category) is not found."""


@cache
def _get_all_activity_categories(session: Session) -> list[ActivityCategory]:
    """See usage for docs. Module level to avoid cache memory leaks."""
    all_categories = session.get(
        "https://api-agenda.bohemios.uy/activitycategory/?from=FRONTEND"
    ).json()
    return [
        ActivityCategory(
            id=activity["id"], name=activity["name"], description=activity["description"]
        )
        for activity in all_categories["description"]
    ]


@cache
def _get_category_time_slots(
    session: Session, in_day: date, category_id: int, user_id: int
) -> list[ActivityTimeSlot]:
    """See usage for docs. Module level to avoid cache memory leaks."""
    options = session.get(
        (
            "https://api-agenda.bohemios.uy/activitytime/"
            f"?id={category_id}&dow={in_day.isoweekday()}&userId={user_id}"
        ),
    ).json()

    return [
        ActivityTimeSlot(
            activity=Activity(
                id=option["activityId"], name=option["name"], description=option["activityDesc"]
            ),
            time_slot_id=option["id"],
            starts_at=datetime.combine(
                in_day, time.fromisoformat(option["starttime"]), tzinfo=Bohemios.timezone
            ),
            ends_at=datetime.combine(
                in_day, time.fromisoformat(option["endtime"]), tzinfo=Bohemios.timezone
            ),
            location=option["location"],
            max_reservations=option["maxoccupancy"],
            current_reservations=option["TotalReservations"],
            reservation_id=option["reservationId"],
        )
        for option in options["description"]
    ]


class Bohemios(Channel):
    """Make reservations to Club Atletico Bohemios.

    You will need an account with the channel. For more, see https://bohemios.uy/.
    """

    timezone = ZoneInfo("America/Montevideo")

    def __init__(self, credentials: Credentials) -> None:
        super().__init__(credentials)

        self._session = Session()
        self._is_logged_in = False
        self._user_id = ""

        _user_agent_generator = FakeUserAgent()
        self._session.headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "Content-Type": "application/json",
                "User-Agent": cast(str, _user_agent_generator.random),
            }
        )

    def login(self) -> None:
        """Login to the channel. Raises an exception if the login fails."""
        self.is_logged_in = False
        login = self._session.put(
            "https://api-agenda.bohemios.uy/signin",
            json={"user": self.credentials.username, "password": self.credentials.password},
        ).json()
        bearer_token, self._user_id = login["token"], login["description"]["id"]

        self._session.headers.update({"Authorization": f"Bearer {bearer_token}"})
        self.is_logged_in = True

    @requires_login
    def get_all_activity_categories(self) -> list[ActivityCategory]:
        """Find all activity categories.

        Returns:
            list[ActivityCategory]: Found activity categories.
        """
        return _get_all_activity_categories(self._session)

    def get_category_time_slots(
        self, in_day: date, category: ActivityCategory
    ) -> list[ActivityTimeSlot]:
        """Find all time slots for a category in a given day.

        Args:
            in_day (date): The day to look for time slots.
            category (ActivityCategory): The category to look for time slots.

        Returns:
            list[ActivityTimeSlot]: Found time slots.
        """
        return _get_category_time_slots(self._session, in_day, category.id, self._user_id)

    @requires_login
    def book_activity(
        self, category_name: str, activity_name: str, when: datetime
    ) -> ActivityTimeSlot:
        """Reserve an activity that starts before or at the given moment and ends after.

        Args:
            category_name (str): The name of the category of the activity.
            activity_name (str): The name of the activity within the category.
            when (datetime): The moment when the activity should start. Localized using
                `self.localize`.

        Raises:
            InvalidActivityError: If the category or activity is not found.
            RuntimeError: If no activity with free spots is found.

        Returns:
            ActivityTimeSlot: The reserved activity.
        """
        when = self.localize(when)
        all_categories = self.get_all_activity_categories()
        for category in all_categories:
            if category.name.casefold() == category_name.casefold():
                break
        else:
            msg = f"Category {category_name} not found."
            raise InvalidActivityError(msg)

        all_category_timeslots = self.get_category_time_slots(when.date(), category)
        given_activity_slots = [
            time_slot
            for time_slot in all_category_timeslots
            if time_slot.activity.name.casefold() == activity_name.casefold()
        ]
        if not given_activity_slots:
            msg = f"No slots for activity {activity_name} found in category {category_name}."
            raise InvalidActivityError(msg)

        for time_slot in given_activity_slots:
            free_spots = time_slot.max_reservations - time_slot.current_reservations
            if time_slot.starts_at <= when < time_slot.ends_at and free_spots:
                # < ends_at so that we prefer stuff that finishes after the given time. Otherwise,
                # we might reserve activities that finish exactly at the given time.
                break
        else:
            msg = f"No activity with free spots in found for {when.isoformat()}."
            raise RuntimeError(msg)

        if time_slot.reservation_id is not None:
            logger.info("Matching activity already reserved, so no extra reservation is needed.")
            return time_slot

        logger.info("Reserving activity.")
        reservation_response = self._session.post(
            "https://api-agenda.bohemios.uy/reservation/",
            json={
                "usr": self._user_id,
                "at": time_slot.time_slot_id,
                "day": 0,  # They require 0 for all days, as the "day" is implicit in the time slot.
                "description": "",
            },
        ).json()

        time_slot.reservation_id = int(reservation_response["description"]["id"])
        return time_slot
