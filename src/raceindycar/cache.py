import csv
import json
import pickle
import random
import shutil
import time
from contextlib import contextmanager
from pathlib import Path

import requests
import requests_cache

from raceindycar.exceptions import RateLimitExceededError
from raceindycar.logging import LOGGER

SCHEDULE_TTL_SECONDS = 12 * 60 * 60
CHALLENGE_MARK = "just a moment"

HTTP_CACHE_BASENAME = "fastindycar_http_cache.sqlite"
HTTP_CACHE_FALLBACK_EXPIRE_SECONDS = 7 * 24 * 60 * 60

PAYLOAD_FORMAT_VERSION = 1
CACHE_FORMATS = ("pickle", "csv")
CSV_DIR_SUFFIX = "_csv"
CSV_META_FILENAME = "_meta.json"

RATE_LIMIT_WINDOW_SECONDS = 60
SOFT_RATE_LIMIT = 40
HARD_RATE_LIMIT = 60
SOFT_RATE_LIMIT_DELAY_SECONDS = 1.0

MIN_REQUEST_INTERVAL_SECONDS = 2.0
MIN_REQUEST_INTERVAL_JITTER_SECONDS = 1.0


class Cache:
    directory = None
    enabled = True
    offline = False
    force_renew = False
    ignore_version = False
    use_requests_cache = True
    cache_format = "pickle"
    ci = False

    _http_session = None
    _http_session_key = None
    _plain_http_session = None
    _request_times = []
    _last_request_time = None

    @classmethod
    def enable_cache(cls, cache_dir, ignore_version=False, force_renew=False,
                      use_requests_cache=True, cache_format="pickle"):
        if cache_format not in CACHE_FORMATS:
            raise ValueError(
                f"cache_format must be one of {CACHE_FORMATS!r}, got {cache_format!r}"
            )
        path = Path(cache_dir)
        if path.exists() and not path.is_dir():
            raise NotADirectoryError(f"cache_dir {path} is not a directory")
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ValueError(f"cache_dir {path} is not usable: {exc}") from exc
        cls.directory = path
        cls.enabled = True
        cls.force_renew = force_renew
        cls.ignore_version = ignore_version
        cls.use_requests_cache = use_requests_cache
        cls.cache_format = cache_format
        cls._http_session = None
        cls._http_session_key = None

    @classmethod
    def requests_get(cls, url, **kwargs):
        return cls._request("get", url, **kwargs)

    @classmethod
    def requests_post(cls, url, **kwargs):
        return cls._request("post", url, **kwargs)

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
            cls._enforce_min_interval()

        kwargs.setdefault("timeout", 60)
        response = getattr(session, method)(url, **kwargs)

        if cls.offline and response.status_code == 504 and response.reason == "Not Cached":
            raise FileNotFoundError(f"Offline mode: no cached copy of {url}")

        response.raise_for_status()
        if not getattr(response, "from_cache", False):
            now = time.monotonic()
            cls._request_times.append(now)
            cls._last_request_time = now
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
    def _enforce_min_interval(cls):
        if cls._last_request_time is None:
            return
        jitter = random.uniform(
            -MIN_REQUEST_INTERVAL_JITTER_SECONDS, MIN_REQUEST_INTERVAL_JITTER_SECONDS,
        )
        target = MIN_REQUEST_INTERVAL_SECONDS + jitter
        remaining = target - (time.monotonic() - cls._last_request_time)
        if remaining > 0:
            time.sleep(remaining)

    @classmethod
    def _session_for_request(cls):
        if cls.enabled and cls.use_requests_cache and cls.directory is not None:
            return cls._cached_session()
        return cls._plain_session()

    @classmethod
    def _plain_session(cls):
        if cls._plain_http_session is None:
            cls._plain_http_session = requests.Session()
        return cls._plain_http_session

    @classmethod
    def _cached_session(cls):
        if cls.directory is None:
            raise RuntimeError(
                "No cache directory configured - call "
                "raceindycar.enable_cache(cache_dir=...) first."
            )
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

    @classmethod
    def load_payload(cls, *parts):
        if cls.directory is None:
            return None
        path = cls.path(*parts)
        if cls.cache_format == "csv":
            return cls._load_csv(cls._csv_dir(path))
        return cls._load_pickle(path)

    @classmethod
    def save_payload(cls, payload, *parts):
        if cls.directory is None:
            return
        path = cls.path(*parts)
        if cls.cache_format == "csv":
            cls._save_csv(payload, cls._csv_dir(path))
        else:
            cls._save_pickle(payload, path)

    @classmethod
    def _csv_dir(cls, path):
        return path.with_name(path.stem + CSV_DIR_SUFFIX)

    @classmethod
    def _load_pickle(cls, path):
        if cls.ci:
            return None
        if not cls.should_read(path):
            return None
        with path.open("rb") as handle:
            envelope = pickle.load(handle)
        if not isinstance(envelope, dict) or "version" not in envelope:
            return None
        if envelope["version"] != PAYLOAD_FORMAT_VERSION and not cls.ignore_version:
            LOGGER.warning("cached data at %s was written by an older/newer "
                            "format version; ignoring", path)
            return None
        return envelope["payload"]

    @classmethod
    def _save_pickle(cls, payload, path):
        if cls.ci or not cls.should_write():
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        envelope = {"version": PAYLOAD_FORMAT_VERSION, "payload": payload}
        with path.open("wb") as handle:
            pickle.dump(envelope, handle, protocol=pickle.HIGHEST_PROTOCOL)

    @classmethod
    def _load_csv(cls, directory):
        if cls.ci:
            return None
        meta_path = directory / CSV_META_FILENAME
        if not cls.should_read(meta_path):
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("version") != PAYLOAD_FORMAT_VERSION and not cls.ignore_version:
            LOGGER.warning("cached data at %s was written by an older/newer "
                            "format version; ignoring", directory)
            return None
        payload = {}
        for key, kind in meta["kinds"].items():
            rows = read_csv_rows(directory / f"{key}.csv")
            payload[key] = (rows[0] if rows else {}) if kind == "dict" else rows
        return payload

    @classmethod
    def _save_csv(cls, payload, directory):
        if cls.ci or not cls.should_write():
            return
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True, exist_ok=True)
        kinds = {}
        for key, value in payload.items():
            if isinstance(value, dict):
                kinds[key] = "dict"
                write_csv_rows(directory / f"{key}.csv", [value])
            else:
                kinds[key] = "list"
                write_csv_rows(directory / f"{key}.csv", list(value or []))
        meta = {"version": PAYLOAD_FORMAT_VERSION, "kinds": kinds}
        (directory / CSV_META_FILENAME).write_text(json.dumps(meta), encoding="utf-8")

    @classmethod
    def path(cls, *parts):
        if cls.directory is None:
            return None
        return cls.directory.joinpath(*parts)

    @classmethod
    def should_read(cls, path, ttl=None):
        if path is None or cls.directory is None:
            return False
        if not cls.enabled or cls.force_renew:
            return False
        if not path.exists() or path.stat().st_size == 0:
            return False
        if ttl is None or cls.ci:
            return True
        return time.time() - path.stat().st_mtime <= ttl

    @classmethod
    def should_write(cls):
        return cls.directory is not None and cls.enabled and not cls.offline

    @classmethod
    def write_text(cls, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    @classmethod
    def write_bytes(cls, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    @classmethod
    def delete_response(cls, url):
        if not (cls.enabled and cls.use_requests_cache) or cls.directory is None:
            return
        cls._cached_session().cache.delete(urls=[url])

    @classmethod
    def get_cache_info(cls):
        if cls.directory is None or not cls.directory.exists():
            return None, None
        return str(cls.directory), cache_size(cls.directory)

    @classmethod
    def clear_cache(cls, cache_dir=None, deep=False):
        root = Path(cache_dir) if cache_dir else cls.directory
        if root is None:
            return
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


def enable_cache(cache_dir, ignore_version=False, force_renew=False,
                  use_requests_cache=True, cache_format="pickle"):
    Cache.enable_cache(cache_dir, ignore_version=ignore_version, force_renew=force_renew,
                        use_requests_cache=use_requests_cache, cache_format=cache_format)


def cache_size(root):
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def encode_csv_cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def decode_csv_cell(text):
    if text == "":
        return ""
    if text == "true":
        return True
    if text == "false":
        return False
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def csv_fieldnames(rows):
    fields = []
    seen = set()
    for row in rows:
        for key in row:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    return fields


def write_csv_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = csv_fieldnames(rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: encode_csv_cell(row.get(key)) for key in fieldnames})


def read_csv_rows(path):
    if not path.exists() or not path.read_text(encoding="utf-8").strip():
        return []
    with path.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [
            {key: decode_csv_cell(value) for key, value in row.items()}
            for row in reader
        ]


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


def is_challenge_page(text):
    return CHALLENGE_MARK in (text or "")[:2000].casefold()
