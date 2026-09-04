import contextlib
from io import BytesIO, StringIO
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch

from bcsfe import core
import editor_metadata as metadata


PRIMARY = "https://metadata.example/metadata.json"
INDEX = {"base_url": "https://assets.example", "versions": {"kr": {"9.9.0": "/9.tar.xz", "10.0.0": "/10.tar.xz", "15.5.0": "/15.tar.xz"}, "en": {"15.5.0": "/en.tar.xz"}}}


def archive(items=None):
    data = BytesIO()
    with tarfile.open(fileobj=data, mode="w:xz") as handle:
        for name, value, kind in items or [("DataLocal/unitbuy.csv", b"1,2,3\n", None)]:
            info = tarfile.TarInfo(name)
            if kind is not None:
                info.type = kind
                if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                    info.linkname = "../../escape"
            else:
                info.size = len(value)
            handle.addfile(info, BytesIO(value) if kind is None else None)
    return data.getvalue()


class Response:
    def __init__(self, body=b"", status=200, headers=None):
        self.body = body
        self.status_code = status
        self.headers = headers or {}
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def iter_content(self, chunk_size):
        for offset in range(0, len(self.body), chunk_size):
            yield self.body[offset:offset + chunk_size]


class MetadataTests(unittest.TestCase):
    def setUp(self):
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.root = Path(self.stack.enter_context(tempfile.TemporaryDirectory()))
        config = NS(get_game_data_repo=lambda: PRIMARY, get_default=lambda key: PRIMARY,
                    get_bool=lambda key: False, get_str=lambda key: "en")
        self.stack.enter_context(patch.object(core.core_data, "config", config, create=True))
        metadata.install_headless_metadata()
        self.stack.enter_context(patch.object(core.GameDataGetter, "get_game_data_dir", return_value=core.Path(str(self.root))))
        self.stack.enter_context(patch("builtins.input", side_effect=AssertionError("Interactive input forbidden")))
        self.stack.enter_context(patch("socket.socket.connect", side_effect=AssertionError("External network forbidden")))
        self.output = StringIO()
        self.stack.enter_context(contextlib.redirect_stdout(self.output))
        self.transport = self.stack.enter_context(patch.object(metadata.requests, "get"))
        self.transport.side_effect = self.respond

    def respond(self, url, **kwargs):
        if url == PRIMARY:
            return Response(json.dumps(INDEX).encode())
        return Response(archive())

    def marker(self):
        return {"format": metadata.MARKER_FORMAT, "country_code": "kr", "version": "15.5.0", "source": PRIMARY, "archive_source": "https://assets.example/15.tar.xz"}

    def test_prepare_downloads_extracts_and_reports_actual_source(self):
        result = metadata.prepare_metadata("kr", 150500)
        self.assertTrue(result["downloaded"])
        self.assertTrue(result["exact_match"])
        self.assertEqual(result["requested_version"], "15.5.0")
        self.assertEqual(result["source"], PRIMARY)
        self.assertEqual((self.root / "kr/15.5.0/DataLocal/unitbuy.csv").read_bytes(), b"1,2,3\n")
        self.assertEqual(json.loads((self.root / "kr/15.5.0/downloaded").read_text()), self.marker())
        self.assertEqual(self.output.getvalue(), "")

    def test_exact_cached_version_works_without_network(self):
        metadata.prepare_metadata("kr", 150500)
        self.transport.reset_mock()
        self.transport.side_effect = AssertionError("No network needed for an exact cache hit")
        result = metadata.prepare_metadata("kr", 150500)
        self.assertTrue(result["downloaded"])
        self.assertEqual(result["source"], PRIMARY)
        self.transport.assert_not_called()

    def test_numeric_version_policy_selects_nearest_greater_then_latest(self):
        result = metadata.prepare_metadata("kr", 100001)
        self.assertEqual(result["resolved_version"], "15.5.0")
        self.assertFalse(result["exact_match"])
        getter = core.GameDataGetter.__new__(core.GameDataGetter)
        for requested, expected in [(90000, "9.9.0"), (99900, "10.0.0"), (100000, "10.0.0"), (990000, "15.5.0")]:
            getter.gv = core.GameVersion(requested)
            resolved, _ = metadata._get_version(getter, INDEX["versions"], core.CountryCode.from_code("kr"))
            self.assertEqual(resolved, expected)

    def test_metadata_versions_returns_countries_and_numeric_order(self):
        self.assertEqual(metadata.metadata_versions()["kr"], ["9.9.0", "10.0.0", "15.5.0"])

    def test_alternative_source_is_automatic_and_reported_without_prompt(self):
        def respond(url, **kwargs):
            if url == PRIMARY:
                return Response(b"SECRET BODY", 503)
            if url == metadata.ALTERNATIVE_REPO:
                return Response(json.dumps(INDEX).encode())
            return Response(archive())
        self.transport.side_effect = respond
        result = metadata.prepare_metadata("kr", 150500)
        self.assertEqual(result["source"], metadata.ALTERNATIVE_REPO)
        self.assertEqual(self.output.getvalue(), "")

    def test_failure_is_headless_and_does_not_include_response_body(self):
        self.transport.return_value = Response(b"SECRET TOKEN RESPONSE", 500)
        self.transport.side_effect = None
        with self.assertRaises(metadata.MetadataError) as caught:
            metadata.metadata_versions()
        self.assertNotIn("SECRET", str(caught.exception))
        self.assertEqual(self.output.getvalue(), "")

    def test_corrupt_metadata_is_not_treated_as_an_empty_success(self):
        for body in (b"not json", b"[]", b'{"versions":{}}'):
            self.transport.side_effect = None
            self.transport.return_value = Response(body)
            with self.subTest(body=body), self.assertRaises(metadata.MetadataError):
                metadata.metadata_versions()

    def test_metadata_oversize_is_rejected_with_or_without_length_header(self):
        with patch.object(metadata, "MAX_METADATA_BYTES", 12):
            for response in (Response(b"1234567890123"), Response(b"", headers={"Content-Length": "13"})):
                self.transport.side_effect = None
                self.transport.return_value = response
                with self.assertRaises(metadata.MetadataError):
                    metadata.metadata_versions()

    def test_archive_traversal_links_devices_and_windows_paths_are_rejected_before_writing(self):
        malicious = [("../escape", None), ("/escape", None), ("C:/escape", None), ("dir\\escape", None), ("file:stream", None), ("DataLocal/CON.csv", None), ("DataLocal/space ", None), ("downloaded", None), ("link", tarfile.SYMTYPE), ("hard", tarfile.LNKTYPE), ("device", tarfile.CHRTYPE), ("fifo", tarfile.FIFOTYPE)]
        for name, kind in malicious:
            with self.subTest(name=name, kind=kind), tempfile.TemporaryDirectory(dir=self.root) as destination:
                data = archive([("DataLocal/safe.csv", b"safe", None), (name, b"bad", kind)])
                with self.assertRaises(metadata.MetadataError):
                    metadata._extract_archive(data, destination, self.marker())
                self.assertEqual(list(Path(destination).iterdir()), [])

    def test_archive_duplicate_and_size_limits_reject_without_marker(self):
        scenarios = [(archive([("DataLocal/A.csv", b"a", None), ("datalocal/a.csv", b"b", None)]), {}), (archive([("DataLocal/big.csv", b"12345", None)]), {"MAX_FILE_BYTES": 4}), (archive([("DataLocal/a.csv", b"123", None), ("DataLocal/b.csv", b"123", None)]), {"MAX_EXPANDED_BYTES": 5}), (archive([("DataLocal/a.csv", b"1", None), ("DataLocal/b.csv", b"1", None)]), {"MAX_ARCHIVE_MEMBERS": 1})]
        for data, limits in scenarios:
            with tempfile.TemporaryDirectory(dir=self.root) as destination, contextlib.ExitStack() as stack:
                for key, value in limits.items():
                    stack.enter_context(patch.object(metadata, key, value))
                with self.assertRaises(metadata.MetadataError):
                    metadata._extract_archive(data, destination, self.marker())
                self.assertFalse((Path(destination) / "downloaded").exists())
                self.assertEqual(list(Path(destination).iterdir()), [])

    def test_bad_archive_does_not_leave_completion_marker_or_staging_directory(self):
        def respond(url, **kwargs):
            return Response(json.dumps(INDEX).encode()) if url == PRIMARY else Response(b"bad archive")
        self.transport.side_effect = respond
        with self.assertRaises(metadata.MetadataError):
            metadata.prepare_metadata("kr", 150500)
        self.assertFalse(any(self.root.rglob("downloaded")))
        self.assertFalse(any(self.root.rglob(".bcsfe-metadata-*")))

    def test_original_download_returns_core_data_and_missing_files_raise_without_print(self):
        metadata.prepare_metadata("kr", 150500)
        getter = core.GameDataGetter(core.CountryCode.from_code("kr"), core.GameVersion(150500))
        value = getter.download("DataLocal", "unitbuy.csv")
        self.assertIsInstance(value, core.Data)
        self.assertEqual(value.data, b"1,2,3\n")
        with self.assertRaises(metadata.MetadataError):
            getter.download("DataLocal", "missing.csv")
        self.assertEqual(self.output.getvalue(), "")

    def test_cached_version_search_ignores_unfinished_and_staging_entries(self):
        metadata.prepare_metadata("kr", 150500)
        bad = self.root / "kr/10.0.0"
        bad.mkdir()
        (bad / "downloaded").write_bytes(b"")
        staging = self.root / "kr/.bcsfe-metadata-staging"
        staging.mkdir()
        (staging / "downloaded").write_text(json.dumps(self.marker()))
        found = core.GameDataGetter.get_downloaded_versions_region(core.CountryCode.from_code("kr"))
        self.assertEqual([str(version) for version in found], ["15.5.0"])

    def test_outside_cache_path_is_rejected_before_move(self):
        with self.assertRaises(metadata.MetadataError):
            metadata._within(self.root, self.root.parent)
        with self.assertRaises(metadata.MetadataError):
            metadata._within(self.root, self.root)

    def test_redirect_to_http_or_too_many_redirects_is_rejected(self):
        self.transport.side_effect = None
        for location in ("http://unsafe.example/data", PRIMARY):
            self.transport.return_value = Response(status=302, headers={"Location": location})
            with self.assertRaises(metadata.MetadataError):
                metadata._read_url(PRIMARY, 10)

    def test_delete_exact_verified_version_and_preserve_other_versions(self):
        owned = self.root / "owned"
        cache = owned / "game_data"
        with patch.object(core, "data_dir_path", core.Path(str(owned))), patch.object(core.GameDataGetter, "get_game_data_dir", return_value=core.Path(str(cache))):
            metadata.prepare_metadata("kr", 150500)
            metadata.prepare_metadata("kr", 100000)
            result = metadata.delete_metadata("kr", 150500)
            self.assertEqual(result["deleted_versions"], ["15.5.0"])
            self.assertFalse((cache / "kr/15.5.0").exists())
            self.assertTrue((cache / "kr/10.0.0/downloaded").exists())
            self.assertEqual(metadata.delete_metadata("kr", 150500)["deleted_versions"], [])

    def test_delete_region_skips_unverified_entries(self):
        owned = self.root / "owned"
        cache = owned / "game_data"
        with patch.object(core, "data_dir_path", core.Path(str(owned))), patch.object(core.GameDataGetter, "get_game_data_dir", return_value=core.Path(str(cache))):
            metadata.prepare_metadata("kr", 150500)
            unknown = cache / "kr/10.0.0"
            unknown.mkdir()
            (unknown / "downloaded").write_bytes(b"")
            with self.assertRaisesRegex(metadata.MetadataError, "verified"):
                metadata.delete_metadata("kr", 100000)
            result = metadata.delete_metadata("kr")
            self.assertEqual(result["deleted_versions"], ["15.5.0"])
            self.assertEqual(result["skipped_entries"], 1)
            self.assertTrue(unknown.exists())

    def test_delete_rejects_unowned_root_and_invalid_inputs_before_filesystem_changes(self):
        with patch.object(core, "data_dir_path", core.Path(str(self.root / "other"))):
            with self.assertRaises(metadata.MetadataError):
                metadata.delete_metadata("kr")
        for country, version in [("../kr", None), ("kr", True), ("kr", "150500")]:
            with self.assertRaises(metadata.MetadataError):
                metadata.delete_metadata(country, version)

    def test_explicit_inputs_and_archive_urls_are_validated(self):
        for cc, gv in [("xx", 150500), ("kr", True), ("kr", "150500"), ("kr", -1)]:
            with self.subTest(cc=cc, gv=gv), self.assertRaises(metadata.MetadataError):
                metadata.prepare_metadata(cc, gv)
        for path in ("https://other.example/file", "//other.example/file", "../file", "x\\file"):
            bad = {"base_url": INDEX["base_url"], "versions": {"kr": {"15.5.0": path}}}
            with self.assertRaises(metadata.MetadataError):
                metadata._validated_metadata(bad, PRIMARY)


if __name__ == "__main__":
    unittest.main()
