import pytz

def local_to_utc(date_time, timezone):
    tz = pytz.timezone(timezone)
    localized = tz.localize(date_time)
    return localized.astimezone(pytz.utc)