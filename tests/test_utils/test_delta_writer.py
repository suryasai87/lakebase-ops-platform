"""Tests for DeltaWriter: mock_mode write operations, catalog creation, write logging."""

import pytest

from utils.delta_writer import DeltaWriter


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestDeltaWriterInit:
    def test_mock_mode_default(self):
        writer = DeltaWriter(mock_mode=True)
        assert writer.mock_mode is True
        assert writer.sql_api_mode is False

    def test_sql_api_mode_disabled_in_mock(self):
        """sql_api_mode should be False when mock_mode is True, even if requested."""
        writer = DeltaWriter(mock_mode=True, sql_api_mode=True)
        assert writer.sql_api_mode is False

    def test_write_log_starts_empty(self):
        writer = DeltaWriter(mock_mode=True)
        assert writer.get_write_log() == []


# ---------------------------------------------------------------------------
# Catalog and schema creation (mock)
# ---------------------------------------------------------------------------

class TestCreateOpsCatalog:
    def test_create_ops_catalog_mock(self, mock_writer):
        result = mock_writer.create_ops_catalog_and_schemas()
        assert "catalog" in result
        assert "schemas" in result
        assert "tables" in result
        assert result["status"].startswith("created")
        # Should list all 7 operational tables
        assert len(result["tables"]) == 7
        expected_tables = [
            "pg_stat_history",
            "index_recommendations",
            "vacuum_history",
            "lakebase_metrics",
            "sync_validation_history",
            "branch_lifecycle",
            "data_archival_history",
        ]
        for table in expected_tables:
            assert table in result["tables"], f"Missing table: {table}"


# ---------------------------------------------------------------------------
# write_metrics (mock)
# ---------------------------------------------------------------------------

class TestWriteMetrics:
    def test_write_single_record(self, mock_writer):
        result = mock_writer.write_metrics("pg_stat_history", [{"queryid": 1, "calls": 100}])
        assert result["records_written"] == 1
        assert result["status"] == "success (mock)"
        assert "pg_stat_history" in result["table"]

    def test_write_multiple_records(self, mock_writer):
        records = [{"metric_name": f"metric_{i}", "value": i} for i in range(10)]
        result = mock_writer.write_metrics("lakebase_metrics", records)
        assert result["records_written"] == 10

    def test_write_appends_to_log(self, mock_writer):
        mock_writer.write_metrics("pg_stat_history", [{"a": 1}])
        mock_writer.write_metrics("index_recommendations", [{"b": 2}])
        log = mock_writer.get_write_log()
        assert len(log) == 2
        assert log[0]["records"] == 1
        assert log[1]["records"] == 1

    def test_write_log_includes_table_name(self, mock_writer):
        mock_writer.write_metrics("vacuum_history", [{"op": "VACUUM"}])
        log = mock_writer.get_write_log()
        assert "vacuum_history" in log[0]["table"]

    def test_write_log_includes_mode(self, mock_writer):
        mock_writer.write_metrics("pg_stat_history", [{"x": 1}], mode="overwrite")
        log = mock_writer.get_write_log()
        assert log[0]["mode"] == "overwrite"

    def test_snapshot_timestamp_added_for_metrics(self, mock_writer):
        records = [{"metric_name": "test"}]
        mock_writer.write_metrics("lakebase_metrics", records)
        assert "snapshot_timestamp" in records[0]

    def test_snapshot_timestamp_added_for_pg_stat(self, mock_writer):
        records = [{"queryid": 1}]
        mock_writer.write_metrics("pg_stat_history", records)
        assert "snapshot_timestamp" in records[0]

    def test_snapshot_timestamp_not_overwritten(self, mock_writer):
        records = [{"metric_name": "test", "snapshot_timestamp": "custom-ts"}]
        mock_writer.write_metrics("lakebase_metrics", records)
        assert records[0]["snapshot_timestamp"] == "custom-ts"

    def test_snapshot_timestamp_not_added_for_other_tables(self, mock_writer):
        records = [{"event_id": "1"}]
        mock_writer.write_metrics("branch_lifecycle", records)
        assert "snapshot_timestamp" not in records[0]

    def test_write_empty_records(self, mock_writer):
        result = mock_writer.write_metrics("pg_stat_history", [])
        assert result["records_written"] == 0


# ---------------------------------------------------------------------------
# write_archive
# ---------------------------------------------------------------------------

class TestWriteArchive:
    def test_write_archive(self, mock_writer):
        result = mock_writer.write_archive("orders_cold", [{"id": 1, "data": "archived"}])
        assert result["records_written"] == 1
        assert "lakebase_archive" in result["table"]


# ---------------------------------------------------------------------------
# sql_query (mock)
# ---------------------------------------------------------------------------

class TestSqlQuery:
    def test_sql_query_mock_returns_empty(self, mock_writer):
        result = mock_writer.sql_query("SELECT * FROM something")
        assert result == []


# ---------------------------------------------------------------------------
# Write log
# ---------------------------------------------------------------------------

class TestWriteLog:
    def test_log_accumulates(self, mock_writer):
        for i in range(5):
            mock_writer.write_metrics("pg_stat_history", [{"i": i}])
        assert len(mock_writer.get_write_log()) == 5

    def test_log_entries_have_timestamp(self, mock_writer):
        mock_writer.write_metrics("pg_stat_history", [{"x": 1}])
        entry = mock_writer.get_write_log()[0]
        assert "timestamp" in entry
