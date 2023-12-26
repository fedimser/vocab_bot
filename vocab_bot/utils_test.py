from .utils import secs_to_interval


def test_secs_to_interval():
    assert secs_to_interval(110) == "2 minutes"
    assert secs_to_interval(3599) == "60 minutes"
    assert secs_to_interval(3600) == "1 hours"
    assert secs_to_interval(19 * 3600 + 200) == "19 hours"
    assert secs_to_interval(24 * 3600 + 1) == "24 hours"
    assert secs_to_interval((2 * 24 + 5) * 3600) == "2 days 5 hours"
    assert secs_to_interval((10 * 24 + 15) * 3600) == "10 days 15 hours"
