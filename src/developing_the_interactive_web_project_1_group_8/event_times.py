from datetime import datetime, timezone
from zoneinfo import ZoneInfo


# https://docs.python.org/3.14/library/zoneinfo.html
CENTRAL = ZoneInfo("America/Chicago")


# https://docs.python.org/3/library/datetime.html#datetime.datetime.fromisoformat
def parse_utc_time(value, current_time=None):
    if not value:
        return None
    if current_time is not None:
        current_value = current_time.astimezone(CENTRAL).strftime("%Y-%m-%dT%H:%M")
        if value == current_value:
            return current_time.astimezone(timezone.utc)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        local_time = parsed.replace(tzinfo=CENTRAL)
        parsed_utc = local_time.astimezone(timezone.utc)
        if parsed_utc.astimezone(CENTRAL).replace(tzinfo=None) != parsed:
            raise ValueError
        return parsed_utc
    return parsed.astimezone(timezone.utc)


def is_event_completed(event):
    if event["status"] == "Canceled" or event["time"] is None:
        return False
    return event["time"] <= datetime.now(timezone.utc)


def is_event_time_completed(time):
    if time is None:
        return False
    return time <= datetime.now(timezone.utc)
