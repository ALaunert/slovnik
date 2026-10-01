"""Calendar boundaries and deferred timezone changes; all stored instants stay UTC."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

UTC = timezone.utc


def as_utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def validate_zone(value: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 80:
        raise ValueError("Choose an IANA timezone")
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise ValueError("Unknown IANA timezone") from None
    return value


def first_day_instant(day: date, zone: str) -> datetime:
    tz = ZoneInfo(validate_zone(zone))
    midnight = datetime.combine(day, time.min)
    candidates = tuple(midnight.replace(tzinfo=tz, fold=fold).astimezone(UTC) for fold in (0, 1))
    exact = [candidate for candidate in candidates
             if candidate.astimezone(tz).replace(tzinfo=None) == midnight]
    if exact:
        return min(exact)
    # Midnight lies inside an IANA gap. Normalizing midnight alone can overshoot
    # the first existing instant (Toronto 1919); find the transition in UTC.
    low, high = min(candidates), max(candidates)
    if low.astimezone(tz).date() >= day:
        low -= timedelta(days=2)
    if high.astimezone(tz).date() < day:
        high += timedelta(days=2)
    while high-low > timedelta(seconds=1):
        middle = low + timedelta(seconds=int((high-low).total_seconds())//2)
        if middle.astimezone(tz).date() >= day:
            high = middle
        else:
            low = middle
    return high


@dataclass(frozen=True)
class DayWindow:
    start: datetime
    end: datetime
    zone: str
    transition: bool = False

    def payload(self):
        return {"start": self.start.isoformat(), "end": self.end.isoformat(),
                "timezone": self.zone, "transition": self.transition,
                "calendar_policy_version": "learner-local-days-v1"}


def day_window(now: datetime, zone: str) -> DayWindow:
    local = as_utc(now).astimezone(ZoneInfo(validate_zone(zone)))
    return DayWindow(first_day_instant(local.date(), zone),
                     first_day_instant(local.date()+timedelta(days=1), zone), zone)


def allocation_window(profile, now: datetime) -> DayWindow:
    now = as_utc(now)
    change_at = getattr(profile, "timezone_change_at", None)
    if change_at is not None and now < as_utc(change_at):
        return DayWindow(as_utc(profile.timezone_window_start), as_utc(change_at),
                         profile.previous_timezone, True)
    return day_window(now, getattr(profile, "timezone", None) or "UTC")


def request_timezone(profile, zone: str, now: datetime) -> None:
    validate_zone(zone)
    if zone == profile.timezone:
        return
    current = allocation_window(profile, now)
    local_end = current.end.astimezone(ZoneInfo(zone)).date()
    boundary = first_day_instant(local_end, zone)
    while boundary < current.end:
        local_end += timedelta(days=1)
        boundary = first_day_instant(local_end, zone)
    profile.previous_timezone = current.zone
    profile.timezone = zone
    profile.timezone_window_start = current.start
    profile.timezone_change_at = boundary


def calendar_window(profile, now: datetime) -> DayWindow:
    return day_window(now, allocation_window(profile, now).zone)


def week_start(profile, now: datetime) -> datetime:
    zone = allocation_window(profile, now).zone
    local_day = as_utc(now).astimezone(ZoneInfo(zone)).date()
    return first_day_instant(local_day-timedelta(days=local_day.weekday()), zone)
