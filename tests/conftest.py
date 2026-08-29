import pytest

from raceindycar.cache import Cache


@pytest.fixture(autouse=True)
def reset_cache_state():
    saved = (
        Cache.directory, Cache.enabled, Cache.offline, Cache.force_renew,
        Cache.ignore_version, Cache.use_requests_cache, Cache.cache_format, Cache.ci,
        Cache._http_session, Cache._http_session_key, Cache._plain_http_session,
        list(Cache._request_times), Cache._last_request_time,
    )
    yield
    (
        Cache.directory, Cache.enabled, Cache.offline, Cache.force_renew,
        Cache.ignore_version, Cache.use_requests_cache, Cache.cache_format, Cache.ci,
        Cache._http_session, Cache._http_session_key, Cache._plain_http_session,
        Cache._request_times, Cache._last_request_time,
    ) = saved
