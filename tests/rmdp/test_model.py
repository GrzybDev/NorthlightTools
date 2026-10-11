from datetime import UTC, datetime

from northlighttools.rmdp.model import (
    filetime_from_ns,
    filetime_to_datetime,
    filetime_to_ns,
)


def test_filetimes_convert_to_and_from_unix_time() -> None:
    nanoseconds = 1_475_837_760_123_456_700

    assert filetime_to_ns(filetime_from_ns(nanoseconds)) == nanoseconds
    assert filetime_to_datetime(filetime_from_ns(nanoseconds)) == datetime(
        2016, 10, 7, 10, 56, 0, 123456, tzinfo=UTC
    )


def test_filetimes_past_the_year_9999_are_no_date() -> None:
    assert filetime_to_datetime(2**63) is None
