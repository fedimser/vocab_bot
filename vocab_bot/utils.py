from datetime import datetime, timezone


def get_cur_time() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def secs_to_interval(secs: int) -> str:
    if secs < 3600:
        return "%d minutes" % round(secs / 60)
    hours = round(secs / 3600)
    if hours <= 24:
        return "%d hours" % hours
    else:
        return "%d days %d hours" % (hours // 24, hours % 24)
