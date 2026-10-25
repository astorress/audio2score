from datetime import (
    datetime,
    timedelta,
    timezone,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ")


def epoch(moment: datetime) -> int:
    return int(moment.timestamp())


def after(moment: datetime, hours: float) -> datetime:
    return moment + timedelta(hours=hours)
