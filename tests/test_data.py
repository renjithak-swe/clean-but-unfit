from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from clean_unfit.data import (
    DataAcquisitionError,
    compute_sha256,
    download_archive,
    load_table,
    parse_rows,
)
from tests.helpers import write_archive


class ParseRowsTest(unittest.TestCase):
    def test_parses_valid_rows_into_columns(self) -> None:
        table = parse_rows(["1,2,3,4,5,6,7,8,9", "10,20,30,40,50,60,70,80,90"])
        self.assertEqual(table.row_count, 2)
        self.assertEqual(table.columns["median_house_value"], [9.0, 90.0])
        self.assertEqual(table.unparsed_rows, [])

    def test_keeps_malformed_rows_instead_of_dropping_them(self) -> None:
        table = parse_rows(["1,2,3,4,5,6,7,8,9", "1,2,3", "1,2,3,4,5,6,7,8,abc"])
        self.assertEqual(table.row_count, 1)
        self.assertEqual(table.unparsed_rows, [["1", "2", "3"], ["1", "2", "3", "4", "5", "6", "7", "8", "abc"]])

    def test_skips_blank_lines(self) -> None:
        self.assertEqual(parse_rows(["", "1,2,3,4,5,6,7,8,9", ""]).row_count, 1)

    def test_empty_input_gives_empty_table(self) -> None:
        self.assertEqual(parse_rows([]).row_count, 0)


class DownloadArchiveTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())

    def test_downloads_once_and_verifies_checksum(self) -> None:
        source = write_archive(self.temp_dir / "source.tgz", "1,2,3,4,5,6,7,8,9\n")
        expected = compute_sha256(source)
        calls: list[str] = []

        def fake_fetch(url: str) -> bytes:
            calls.append(url)
            return source.read_bytes()

        destination = self.temp_dir / "cache" / "data.tgz"
        download_archive(destination, url="https://example.test/a", expected_sha256=expected, fetch_bytes=fake_fetch)
        download_archive(destination, url="https://example.test/a", expected_sha256=expected, fetch_bytes=fake_fetch)
        self.assertEqual(calls, ["https://example.test/a"])
        self.assertFalse(destination.with_suffix(".tgz.part").exists())

    def test_rejects_checksum_mismatch(self) -> None:
        destination = self.temp_dir / "data.tgz"
        destination.write_bytes(b"tampered")
        with self.assertRaisesRegex(DataAcquisitionError, "checksum mismatch"):
            download_archive(destination, expected_sha256="0" * 64)

    def test_wraps_network_errors(self) -> None:
        def failing_fetch(_url: str) -> bytes:
            raise OSError("connection refused")

        with self.assertRaisesRegex(DataAcquisitionError, "download failed"):
            download_archive(self.temp_dir / "data.tgz", fetch_bytes=failing_fetch)


class LoadTableTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = Path(tempfile.mkdtemp())

    def test_loads_member_from_archive(self) -> None:
        archive = write_archive(self.temp_dir / "a.tgz", "1,2,3,4,5,6,7,8,9\n")
        self.assertEqual(load_table(archive).row_count, 1)

    def test_missing_member_raises_data_error(self) -> None:
        archive = write_archive(self.temp_dir / "a.tgz", "1,2,3,4,5,6,7,8,9\n", member_name="other.csv")
        with self.assertRaisesRegex(DataAcquisitionError, "not found"):
            load_table(archive)

    def test_non_archive_raises_data_error(self) -> None:
        not_an_archive = self.temp_dir / "a.tgz"
        not_an_archive.write_bytes(b"plain text")
        with self.assertRaisesRegex(DataAcquisitionError, "not a readable"):
            load_table(not_an_archive)


if __name__ == "__main__":
    unittest.main()
