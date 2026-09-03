"""Headless, bounded metadata reads for the unchanged vendored BCSFE runtime."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.parse import urljoin, urlsplit, urlunsplit
import json
import os
import re
import shutil
import tarfile
import tempfile
import uuid

import requests
from bcsfe import core

MAX_METADATA_BYTES = 2 * 1024 * 1024
MAX_ARCHIVE_BYTES = 64 * 1024 * 1024
MAX_EXPANDED_BYTES = 256 * 1024 * 1024
MAX_FILE_BYTES = 16 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 50000
ALTERNATIVE_REPO = "https://gitlab.com/fieryhenry/bcdata/-/raw/main/metadata.json"
MARKER_FORMAT = "bcsfe-api-metadata-v1"


class MetadataError(ValueError):
    """A metadata operation failed without asking for terminal input."""


def _https_url(url):
    if not isinstance(url, str):
        raise MetadataError("Metadata source URL must be a string")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise MetadataError("Metadata source must be an HTTPS URL without embedded credentials")
    return url


def _public_source(url):
    parsed = urlsplit(url)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def _read_url(url, maximum):
    """Follow bounded HTTPS redirects; never log bodies, credentials or URLs."""
    url = _https_url(url)
    try:
        for redirect in range(4):
            with requests.get(url, stream=True, timeout=(5, 30), allow_redirects=False, headers={"Accept-Encoding": "identity"}) as response:
                if response.status_code in (301, 302, 303, 307, 308):
                    if redirect == 3 or not response.headers.get("Location"):
                        raise MetadataError("Metadata download redirected too many times")
                    url = _https_url(urljoin(url, response.headers["Location"]))
                    continue
                if response.status_code != 200:
                    raise MetadataError(f"Metadata download failed with HTTP {response.status_code}")
                length = response.headers.get("Content-Length")
                if length is not None and (not length.isdecimal() or int(length) > maximum):
                    raise MetadataError("Metadata download exceeds its size limit")
                chunks, total = [], 0
                for chunk in response.iter_content(chunk_size=65536):
                    total += len(chunk)
                    if total > maximum:
                        raise MetadataError("Metadata download exceeds its size limit")
                    chunks.append(chunk)
                return b"".join(chunks), _public_source(url)
    except requests.RequestException:
        raise MetadataError("Metadata source could not be reached") from None
    raise MetadataError("Metadata download failed")


def _version_number(version):
    if not isinstance(version, str) or not re.fullmatch(r"[0-9]{1,4}\.[0-9]{1,2}\.[0-9]{1,2}", version):
        raise MetadataError("Metadata contains an invalid version")
    return core.GameVersion.from_string(version).game_version


def _validated_metadata(data, source):
    if not isinstance(data, dict) or not isinstance(data.get("versions"), dict):
        raise MetadataError("Metadata version index is invalid")
    _https_url(data.get("base_url"))
    if len(data["versions"]) > 32:
        raise MetadataError("Metadata version index is too large")
    for country, versions in data["versions"].items():
        if not isinstance(country, str) or not re.fullmatch(r"[a-z]{2}", country) or not isinstance(versions, dict) or len(versions) > 5000:
            raise MetadataError("Metadata country/version index is invalid")
        for version, archive_path in versions.items():
            _version_number(version)
            if not isinstance(archive_path, str) or not archive_path or len(archive_path) > 2048:
                raise MetadataError("Metadata archive path is invalid")
            # Archives must stay under the declared base URL. No alternate host,
            # traversal, query, backslash or fragment is accepted from the index.
            parsed = urlsplit(archive_path)
            if parsed.scheme or parsed.netloc or parsed.query or parsed.fragment or "\\" in archive_path or ".." in PurePosixPath(archive_path).parts:
                raise MetadataError("Metadata archive path escapes its source")
    result = dict(data)
    result["_bcsfe_api_source"] = source
    return result


def _get_metadata(show_alt=True):
    primary = core.GameDataGetter.repo_url()
    sources = [primary]
    if show_alt and primary == core.core_data.config.get_default(core.ConfigKey.GAME_DATA_REPO) and primary != ALTERNATIVE_REPO:
        sources.append(ALTERNATIVE_REPO)
    for source in sources:
        try:
            raw, actual_source = _read_url(source, MAX_METADATA_BYTES)
            data = json.loads(raw.decode("utf-8-sig"))
            return _validated_metadata(data, actual_source)
        except (MetadataError, ValueError, UnicodeError):
            continue
    raise MetadataError("Game metadata is unavailable from the configured sources") from None


def _get_version(self, versions, cc):
    available = versions.get(cc.get_code(), {})
    if not available:
        raise MetadataError(f"No game metadata is available for country {cc.get_code()}")
    ordered = sorted(available, key=_version_number)
    requested = self.gv.game_version
    selected = next((v for v in ordered if _version_number(v) >= requested), ordered[-1])
    return selected, available[selected]


def _within(root, path):
    """Resolve the final absolute Windows/Unix path before any move/removal."""
    root = Path(root).resolve()
    path = Path(path).resolve()
    if path == root or not path.is_relative_to(root):
        raise MetadataError("Metadata path escapes its cache directory")
    return path


def _region_root(getter):
    cache = Path(core.GameDataGetter.get_game_data_dir().path).resolve()
    country = getter.cc.get_code()
    if not re.fullmatch(r"[a-z]{2}", country):
        raise MetadataError("Invalid metadata country code")
    region = _within(cache, cache / country)
    region.mkdir(parents=True, exist_ok=True)
    return region


def _target(getter):
    if getter.version is None:
        raise MetadataError("No metadata version was selected")
    _version_number(getter.version)
    root = _region_root(getter)
    return _within(root, root / getter.version)


def _marker(getter):
    target = _target(getter)
    marker = target / "downloaded"
    if not marker.is_file() or marker.is_symlink() or marker.stat().st_size > MAX_METADATA_BYTES:
        return None
    try:
        content = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return None
    if not isinstance(content, dict) or content.get("format") != MARKER_FORMAT or content.get("version") != getter.version or content.get("country_code") != getter.cc.get_code():
        return None
    return content


def _has_downloaded(self):
    return self.version is not None and _marker(self) is not None


def _member_path(name):
    if not isinstance(name, str) or not name or "\\" in name or ":" in name or PureWindowsPath(name).drive or name.startswith("/"):
        raise MetadataError("Archive contains an unsafe path")
    pure = PurePosixPath(name)
    if ".." in pure.parts:
        raise MetadataError("Archive contains path traversal")
    parts = pure.parts
    if not parts:
        return None
    reserved = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
    if any(part.endswith((".", " ")) or part.split(".")[0].upper() in reserved for part in parts):
        raise MetadataError("Archive contains an unsafe Windows filename")
    if parts[0].casefold() == "downloaded":
        raise MetadataError("Archive may not supply its completion marker")
    return Path(*parts)


def _validated_members(archive):
    members, seen, total = [], set(), 0
    for member in archive:
        if len(members) >= MAX_ARCHIVE_MEMBERS:
            raise MetadataError("Archive contains too many entries")
        if not member.isfile() and not member.isdir():
            raise MetadataError("Archive links and special files are not allowed")
        relative = _member_path(member.name)
        if relative is None:
            if member.isdir():
                continue
            raise MetadataError("Archive file has no name")
        key = relative.as_posix().casefold()
        if key in seen:
            raise MetadataError("Archive contains duplicate paths")
        seen.add(key)
        if member.size < 0 or member.size > MAX_FILE_BYTES:
            raise MetadataError("Archive file exceeds its size limit")
        total += member.size
        if total > MAX_EXPANDED_BYTES:
            raise MetadataError("Archive exceeds its expanded size limit")
        members.append((member, relative))
    if not any(member.isfile() for member, relative in members):
        raise MetadataError("Archive contains no metadata files")
    return members


def _extract_archive(data, destination, marker):
    root = Path(destination).resolve()
    try:
        with tarfile.open(fileobj=BytesIO(data), mode="r:xz") as archive:
            members = _validated_members(archive)
            for member, relative in members:
                path = _within(root, root / relative)
                if member.isdir():
                    path.mkdir(parents=True, exist_ok=True)
                    continue
                path.parent.mkdir(parents=True, exist_ok=True)
                handle = archive.extractfile(member)
                if handle is None:
                    raise MetadataError("Archive metadata file is unreadable")
                with handle, path.open("xb") as output:
                    remaining = member.size
                    while remaining:
                        chunk = handle.read(min(65536, remaining))
                        if not chunk:
                            raise MetadataError("Archive metadata file is truncated")
                        output.write(chunk)
                        remaining -= len(chunk)
            (root / "downloaded").write_text(json.dumps(marker, ensure_ascii=True), encoding="utf-8")
    except (tarfile.TarError, EOFError, OSError):
        raise MetadataError("Metadata archive could not be safely extracted") from None


def _download_version_data(self):
    if _has_downloaded(self):
        return True
    # A cached exact version may have left the upstream constructor without a
    # URL. Resolve it again if its API completion marker is absent or invalid.
    if self.url is None or self.filepath is None:
        self.metadata = _get_metadata()
        self.all_versions = core.GameDataGetter.get_versions(self.metadata)
        self.url = self.metadata["base_url"]
        self.version, self.filepath = _get_version(self, self.all_versions, self.cc)
    metadata = getattr(self, "metadata", {})
    archive_url = _https_url(self.url + self.filepath)
    data, actual_archive = _read_url(archive_url, MAX_ARCHIVE_BYTES)
    target = _target(self)
    region = target.parent.resolve()
    staging = _within(region, Path(tempfile.mkdtemp(prefix=".bcsfe-metadata-", dir=region)))
    previous = None
    published = False
    try:
        marker = {"format": MARKER_FORMAT, "country_code": self.cc.get_code(), "version": self.version,
                  "source": metadata.get("_bcsfe_api_source", _public_source(core.GameDataGetter.repo_url())), "archive_source": actual_archive}
        _extract_archive(data, staging, marker)
        if target.exists():
            previous = _within(region, region / (".bcsfe-previous-" + uuid.uuid4().hex))
            os.replace(_within(region, target), previous)
        try:
            os.replace(_within(region, staging), _within(region, target))
        except OSError:
            if previous is not None and previous.exists() and not target.exists():
                os.replace(_within(region, previous), _within(region, target))
                previous = None
            raise MetadataError("Metadata cache could not be published") from None
        published = True
        return True
    finally:
        if staging.exists():
            shutil.rmtree(_within(region, staging))
        if published and previous is not None and previous.exists():
            shutil.rmtree(_within(region, previous))


def _download(self, pack_name, file_name, retries=2, display_text=True):
    for label, value in (("pack", pack_name), ("file", file_name)):
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", value) or value in (".", ".."):
            raise MetadataError(f"Invalid metadata {label} name")
    if not _has_downloaded(self):
        _download_version_data(self)
    target = _target(self)
    pack = self.get_packname(pack_name)
    relative = _member_path(pack + "/" + file_name)
    path = _within(target, target / relative)
    if not path.is_file() or path.is_symlink():
        raise MetadataError(f"Required metadata file is unavailable: {pack_name}/{file_name}")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise MetadataError("Cached metadata file exceeds its size limit")
    try:
        return core.Data(path.read_bytes())
    except OSError:
        raise MetadataError("Cached metadata file could not be read") from None


def _download_all(self, pack_name, file_names, display_text=True):
    return [(name, _download(self, pack_name, name)) for name in file_names]


def _print_no_file(self, packname, filename):
    raise MetadataError("Required game metadata is unavailable")


def _downloaded_versions_region(cc):
    cache = Path(core.GameDataGetter.get_game_data_dir().path).resolve()
    country = cc.get_code()
    if not re.fullmatch(r"[a-z]{2}", country):
        raise MetadataError("Invalid metadata country code")
    region = _within(cache, cache / country)
    if not region.is_dir():
        return []
    found = []
    for entry in region.iterdir():
        if not entry.is_dir() or not re.fullmatch(r"[0-9]{1,4}\.[0-9]{1,2}\.[0-9]{1,2}", entry.name):
            continue
        _within(region, entry)
        getter = core.GameDataGetter.__new__(core.GameDataGetter)
        getter.version, getter.cc = entry.name, cc
        if _marker(getter) is not None:
            found.append(core.GameVersion.from_string(entry.name))
    return found


def install_headless_metadata():
    """Install once after CoreData initialization; never edit the vendor files."""
    cls = core.GameDataGetter
    if getattr(cls, "_api_headless_installed", False):
        return
    cls.get_metadata = staticmethod(_get_metadata)
    cls.get_version = _get_version
    cls.get_downloaded_versions_region = staticmethod(_downloaded_versions_region)
    cls.has_downloaded = _has_downloaded
    cls.download_version_data = _download_version_data
    cls.download = _download
    cls.download_all = _download_all
    cls.get_file = _download
    cls.try_download = _download_version_data
    cls.print_no_file = _print_no_file
    cls._api_headless_installed = True


def metadata_versions():
    metadata = core.GameDataGetter.get_metadata()
    return {country: sorted(versions, key=_version_number) for country, versions in metadata["versions"].items()}


def prepare_metadata(country_code: str, game_version: int):
    if type(country_code) is not str or country_code not in core.CountryCode.get_all_str():
        raise MetadataError("country_code must be en, jp, kr or tw")
    if type(game_version) is not int or not 1 <= game_version <= 999999:
        raise MetadataError("game_version must be an integer save version")
    gv = core.GameVersion(game_version)
    getter = core.GameDataGetter(core.CountryCode.from_code(country_code), gv, do_print=False)
    _download_version_data(getter)
    marker = _marker(getter)
    return {"country_code": country_code, "requested_version": gv.to_string(), "resolved_version": getter.version,
            "exact_match": _version_number(getter.version) == game_version, "downloaded": marker is not None,
            "source": marker["source"] if marker else None, "archive_source": marker["archive_source"] if marker else None}


def delete_metadata(country_code: str, game_version: int | None = None):
    """Delete only verified API-owned cached versions; preserve unknown entries."""
    if type(country_code) is not str or country_code not in core.CountryCode.get_all_str():
        raise MetadataError("country_code must be en, jp, kr or tw")
    if game_version is not None and (type(game_version) is not int or not 1 <= game_version <= 999999):
        raise MetadataError("game_version must be an integer save version")
    if core.data_dir_path is None:
        raise MetadataError("API-owned metadata cache root is not configured")
    owned = Path(core.data_dir_path.path).resolve()
    cache = _within(owned, Path(core.GameDataGetter.get_game_data_dir().path))
    region = _within(cache, cache / country_code)
    if not region.exists():
        return {"country_code": country_code, "deleted_versions": [], "skipped_entries": 0}
    if not region.is_dir():
        raise MetadataError("Metadata region cache is not a directory")
    explicit = core.GameVersion(game_version).to_string() if game_version is not None else None
    candidates = [region / explicit] if explicit is not None else list(region.iterdir())
    planned, skipped = [], 0
    for entry in candidates:
        if not entry.exists():
            continue
        if not entry.is_dir() or not re.fullmatch(r"[0-9]{1,4}\.[0-9]{1,2}\.[0-9]{1,2}", entry.name):
            if explicit is not None:
                raise MetadataError("Requested metadata cache directory is invalid")
            skipped += 1
            continue
        resolved = _within(region, entry)
        getter = core.GameDataGetter.__new__(core.GameDataGetter)
        getter.version, getter.cc = entry.name, core.CountryCode.from_code(country_code)
        if _marker(getter) is None:
            if explicit is not None:
                raise MetadataError("Requested cache has no verified API completion marker")
            skipped += 1
            continue
        planned.append((entry.name, resolved))
    deleted = []
    for version, path in planned:
        # Validate both ownership boundaries again immediately before recursion.
        _within(owned, path)
        resolved = _within(region, path)
        try:
            shutil.rmtree(resolved)
        except OSError:
            raise MetadataError("Metadata cache could not be deleted") from None
        deleted.append(version)
    return {"country_code": country_code, "deleted_versions": sorted(deleted, key=_version_number), "skipped_entries": skipped}
