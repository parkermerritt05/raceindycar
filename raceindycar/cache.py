import os
import pickle
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

import requests
import requests_cache

from raceindycar.exceptions import RateLimitExceededError
from raceindycar.logging import LOGGER

DEFAULT_CACHE_DIR = Path(".cache/fastindycar")
CACHE_DIR_ENV_VAR = "FASTINDYCAR_CACHE"
SCHEDULE_TTL_SECONDS = 12 * 60 * 60
CHALLENGE_MARK = "just a moment"

HTTP_CACHE_BASENAME = "fastindycar_http_cache.sqlite"
HTTP_CACHE_FALLBACK_EXPIRE_SECONDS = 7 * 24 * 60 * 60

PICKLE_FORMAT_VERSION = 1

RATE_LIMIT_WINDOW_SECONDS = 60
SOFT_RATE_LIMIT = 40
HARD_RATE_LIMIT = 60
SOFT_RATE_LIMIT_DELAY_SECONDS = 1.0


class Cache:
    directory = DEFAULT_CACHE_DIR
    enabled = True
    offline = False
    force_renew = False
    ignore_version = False
    use_requests_cache = True
    ci = False

    _http_session = None
    _http_session_key = None
    _plain_http_session = None
    _request_times = []

    @classmethod
    def enable_cache(cls, cache_dir=None, ignore_version=False, force_renew=False,
                      use_requests_cache=True):
        cls.directory = Path(cache_dir) if cache_dir else default_cache_dir()
        cls.directory.mkdir(parents=True, exist_ok=True)
        cls.enabled = True
        cls.force_renew = force_renew
        cls.ignore_version = ignore_version
        cls.use_requests_cache = use_requests_cache
        cls._http_session = None
        cls._http_session_key = None

    @classmethod
    def path(cls, *parts):
        return cls.directory.joinpath(*parts)

    @classmethod
    def should_read(cls, path, ttl=None):
        if not cls.enabled or cls.force_renew:
            return False
        if not path.exists() or path.stat().st_size == 0:
            return False
        if ttl is None or cls.ci:
            return True
        return time.time() - path.stat().st_mtime <= ttl

    @classmethod
    def should_write(cls):
        return cls.enabled and not cls.offline

    @classmethod
    def write_text(cls, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    @classmethod
    def write_bytes(cls, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    @classmethod
    def load_pickle(cls, *parts):
        if cls.ci:
            return None
        path = cls.path(*parts)
        if not cls.should_read(path):
            return None
        with path.open("rb") as handle:
            envelope = pickle.load(handle)
        if not isinstance(envelope, dict) or "version" not in envelope:
            return None
        if envelope["version"] != PICKLE_FORMAT_VERSION and not cls.ignore_version:
            LOGGER.warning("cached data at %s was written by an older/newer "
                            "format version; ignoring", path)
            return None
        return envelope["payload"]

    @classmethod
    def save_pickle(cls, payload, *parts):
        if cls.ci or not cls.should_write():
            return
        path = cls.path(*parts)
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {"version": PICKLE_FORMAT_VERSION, "payload": payload}
        with path.open("wb") as handle:
            pickle.dump(envelope, handle, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def requests_get(cls, url, **kwargs):
        return cls._request("get", url, **kwargs)

    @classmethod
    def requests_post(cls, url, **kwargs):
        return cls._request("post", url, **kwargs)

    @classmethod
    def delete_response(cls, url):
        if not (cls.enabled and cls.use_requests_cache):
            return
        cls._cached_session().cache.delete(urls=[url])

    @classmethod
    def get_cache_info(cls):
        if not cls.directory.exists():
            return None, None
        return str(cls.directory), cache_size(cls.directory)

    @classmethod
    def clear_cache(cls, cache_dir=None, deep=False):
        root = Path(cache_dir) if cache_dir else cls.directory
        clear_cache_dir(root, keep_http_cache=not deep)

    @classmethod
    def offline_mode(cls, enabled=True):
        cls.offline = bool(enabled)

    @classmethod
    def ci_mode(cls, enabled=True):
        cls.ci = bool(enabled)
        cls._http_session = None
        cls._http_session_key = None

    @classmethod
    def set_disabled(cls):
        cls.enabled = False

    @classmethod
    def set_enabled(cls):
        cls.enabled = True

    @classmethod
    @contextmanager
    def disabled(cls):
        previous = cls.enabled
        cls.enabled = False
        try:
            yield
        finally:
            cls.enabled = previous

    @classmethod
    def _request(cls, method, url, **kwargs):
        session = cls._session_for_request()
        is_cached_session = isinstance(session, requests_cache.CachedSession)

        if cls.offline:
            if not is_cached_session:
                raise FileNotFoundError(f"Offline mode: no cached copy of {url}")
            kwargs = {**kwargs, "only_if_cached": True}

        will_hit_cache = is_cached_session and cls._is_cached(session, url)
        if not will_hit_cache and not cls.offline:
            cls._enforce_rate_limit()

        kwargs.setdefault("timeout", 60)
        response = getattr(session, method)(url, **kwargs)

        if cls.offline and response.status_code == 504 and response.reason == "Not Cached":
            raise FileNotFoundError(f"Offline mode: no cached copy of {url}")

        response.raise_for_status()
        if not getattr(response, "from_cache", False):
            cls._request_times.append(time.monotonic())
        return response

    @classmethod
    def _is_cached(cls, session, url):
        try:
            return session.cache.contains(url=url)
        except Exception:
            return False

    @classmethod
    def _enforce_rate_limit(cls):
        now = time.monotonic()
        cutoff = now - RATE_LIMIT_WINDOW_SECONDS
        cls._request_times = [t for t in cls._request_times if t > cutoff]
        if len(cls._request_times) >= HARD_RATE_LIMIT:
            raise RateLimitExceededError(
                f"Hard rate limit exceeded: more than {HARD_RATE_LIMIT} requests "
                f"in the last {RATE_LIMIT_WINDOW_SECONDS} seconds"
            )
        if len(cls._request_times) >= SOFT_RATE_LIMIT:
            time.sleep(SOFT_RATE_LIMIT_DELAY_SECONDS)

    @classmethod
    def _session_for_request(cls):
        if cls.enabled and cls.use_requests_cache:
            return cls._cached_session()
        return cls._plain_session()

    @classmethod
    def _plain_session(cls):
        if cls._plain_http_session is None:
            cls._plain_http_session = requests.Session()
        return cls._plain_http_session

    @classmethod
    def _cached_session(cls):
        key = (str(cls.directory), cls.ci)
        if cls._http_session is None or cls._http_session_key != key:
            cls.directory.mkdir(parents=True, exist_ok=True)
            db_path = cls.directory / HTTP_CACHE_BASENAME
            cls._http_session = requests_cache.CachedSession(
                cache_name=str(db_path.with_suffix("")),
                backend="sqlite",
                cache_control=not cls.ci,
                expire_after=(
                    requests_cache.NEVER_EXPIRE if cls.ci
                    else HTTP_CACHE_FALLBACK_EXPIRE_SECONDS
                ),
                stale_if_error=cls.ci,
            )
            cls._http_session_key = key
        return cls._http_session


def default_cache_dir():
    env_dir = os.environ.get(CACHE_DIR_ENV_VAR)
    if env_dir:
        return Path(env_dir)
    return DEFAULT_CACHE_DIR


def enable_cache(cache_dir=None, ignore_version=False, force_renew=False,
                  use_requests_cache=True):
    Cache.enable_cache(cache_dir, ignore_version=ignore_version, force_renew=force_renew,
                        use_requests_cache=use_requests_cache)


def is_challenge_page(text):
    return CHALLENGE_MARK in (text or "")[:2000].casefold()


def cache_size(root):
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def clear_cache_dir(root, keep_http_cache=True):
    if not root.exists():
        return
    if not keep_http_cache:
        shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        return
    for path in root.rglob("*"):
        if path.is_dir() or path.name.startswith(HTTP_CACHE_BASENAME):
            continue
        path.unlink()
    for path in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        try:
            path.rmdir()
        except OSError:
            pass
