"""
DeltaWriter: Writes operational data to Delta Lake tables in Unity Catalog.

Handles:
- Spark DataFrame creation from agent results
- Append/overwrite modes with partition management
- 90-day retention with automatic cleanup
- Schema evolution
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config.settings import DELTA_TABLES, OPS_CATALOG, OPS_SCHEMA, ARCHIVE_SCHEMA

logger = logging.getLogger("lakebase_ops.delta_writer")


class DeltaWriter:
    """
    Mock-capable Delta Lake writer for operational data.
    In production, uses PySpark to write to Unity Catalog tables.
    """

    def __init__(self, mock_mode: bool = True):
        self.mock_mode = mock_mode
        self._spark = None
        self._write_log: list[dict] = []

        if not mock_mode:
            try:
                from pyspark.sql import SparkSession
                self._spark = SparkSession.builder.getOrCreate()
            except ImportError:
                logger.warning("PySpark not available, falling back to mock mode")
                self.mock_mode = True

    def create_ops_catalog_and_schemas(self) -> dict:
        """
        Create the ops_catalog, lakebase_ops schema, and all operational tables.
        PRD Phase 1, Task 1.1.
        """
        ddl_statements = [
            f"CREATE CATALOG IF NOT EXISTS {OPS_CATALOG}",
            f"CREATE SCHEMA IF NOT EXISTS {OPS_CATALOG}.{OPS_SCHEMA}",
            f"CREATE SCHEMA IF NOT EXISTS {OPS_CATALOG}.{ARCHIVE_SCHEMA}",
        ]

        table_definitions = {
            "pg_stat_history": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.pg_stat_history (
                    snapshot_id STRING,
                    project_id STRING,
                    branch_id STRING,
                    queryid BIGINT,
                    query STRING,
                    calls BIGINT,
                    total_exec_time DOUBLE,
                    mean_exec_time DOUBLE,
                    rows BIGINT,
                    shared_blks_hit BIGINT,
                    shared_blks_read BIGINT,
                    temp_blks_written BIGINT,
                    snapshot_timestamp TIMESTAMP,
                    compute_status STRING
                )
                USING DELTA
                PARTITIONED BY (project_id, branch_id)
                TBLPROPERTIES (
                    'delta.autoOptimize.optimizeWrite' = 'true',
                    'delta.autoOptimize.autoCompact' = 'true',
                    'delta.logRetentionDuration' = 'interval 90 days'
                )
            """,
            "index_recommendations": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.index_recommendations (
                    recommendation_id STRING,
                    project_id STRING,
                    branch_id STRING,
                    table_name STRING,
                    schema_name STRING,
                    recommendation_type STRING,
                    index_name STRING,
                    suggested_columns STRING,
                    confidence STRING,
                    estimated_impact STRING,
                    ddl_statement STRING,
                    status STRING,
                    created_at TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewed_by STRING
                )
                USING DELTA
            """,
            "vacuum_history": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.vacuum_history (
                    operation_id STRING,
                    project_id STRING,
                    branch_id STRING,
                    table_name STRING,
                    schema_name STRING,
                    operation_type STRING,
                    dead_tuples_before BIGINT,
                    dead_tuples_after BIGINT,
                    duration_seconds DOUBLE,
                    executed_at TIMESTAMP,
                    status STRING
                )
                USING DELTA
            """,
            "lakebase_metrics": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.lakebase_metrics (
                    metric_id STRING,
                    project_id STRING,
                    branch_id STRING,
                    metric_name STRING,
                    metric_value DOUBLE,
                    threshold_level STRING,
                    snapshot_timestamp TIMESTAMP
                )
                USING DELTA
                PARTITIONED BY (project_id, metric_name)
            """,
            "sync_validation_history": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.sync_validation_history (
                    validation_id STRING,
                    source_table STRING,
                    target_table STRING,
                    source_count BIGINT,
                    target_count BIGINT,
                    count_drift BIGINT,
                    source_max_ts TIMESTAMP,
                    target_max_ts TIMESTAMP,
                    freshness_lag_seconds DOUBLE,
                    checksum_match BOOLEAN,
                    status STRING,
                    validated_at TIMESTAMP
                )
                USING DELTA
            """,
            "branch_lifecycle": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.branch_lifecycle (
                    event_id STRING,
                    project_id STRING,
                    branch_id STRING,
                    event_type STRING,
                    source_branch STRING,
                    ttl_seconds INT,
                    is_protected BOOLEAN,
                    actor STRING,
                    reason STRING,
                    event_timestamp TIMESTAMP
                )
                USING DELTA
            """,
            "data_archival_history": """
                CREATE TABLE IF NOT EXISTS {catalog}.{schema}.data_archival_history (
                    archival_id STRING,
                    project_id STRING,
                    branch_id STRING,
                    source_table STRING,
                    archive_delta_table STRING,
                    rows_archived BIGINT,
                    bytes_reclaimed BIGINT,
                    cold_threshold_days INT,
                    archived_at TIMESTAMP,
                    status STRING
                )
                USING DELTA
            """,
        }

        if self.mock_mode:
            for stmt in ddl_statements:
                logger.info(f"[MOCK DDL] {stmt}")
            for table_name, ddl in table_definitions.items():
                formatted = ddl.format(catalog=OPS_CATALOG, schema=OPS_SCHEMA)
                logger.info(f"[MOCK DDL] Creating table: {OPS_CATALOG}.{OPS_SCHEMA}.{table_name}")
            return {
                "catalog": OPS_CATALOG,
                "schemas": [OPS_SCHEMA, ARCHIVE_SCHEMA],
                "tables": list(table_definitions.keys()),
                "status": "created (mock)",
            }

        for stmt in ddl_statements:
            self._spark.sql(stmt)
        for table_name, ddl in table_definitions.items():
            self._spark.sql(ddl.format(catalog=OPS_CATALOG, schema=OPS_SCHEMA))
        return {
            "catalog": OPS_CATALOG,
            "schemas": [OPS_SCHEMA, ARCHIVE_SCHEMA],
            "tables": list(table_definitions.keys()),
            "status": "created",
        }

    def write_metrics(self, table_key: str, records: list[dict], mode: str = "append") -> dict:
        """Write records to a Delta table."""
        table_name = DELTA_TABLES.get(table_key, f"{OPS_CATALOG}.{OPS_SCHEMA}.{table_key}")
        now = datetime.now(timezone.utc).isoformat()

        # Add timestamp to each record
        for record in records:
            if "snapshot_timestamp" not in record:
                record["snapshot_timestamp"] = now

        write_entry = {
            "table": table_name,
            "records": len(records),
            "mode": mode,
            "timestamp": now,
        }
        self._write_log.append(write_entry)

        if self.mock_mode:
            logger.info(f"[MOCK WRITE] {len(records)} records -> {table_name} ({mode})")
            return {"table": table_name, "records_written": len(records), "status": "success (mock)"}

        from pyspark.sql import Row
        rows = [Row(**r) for r in records]
        df = self._spark.createDataFrame(rows)
        df.write.mode(mode).saveAsTable(table_name)
        return {"table": table_name, "records_written": len(records), "status": "success"}

    def write_archive(self, archive_table: str, records: list[dict]) -> dict:
        """Write cold data to archive Delta table."""
        full_table = f"{OPS_CATALOG}.{ARCHIVE_SCHEMA}.{archive_table}"
        return self.write_metrics(full_table, records, mode="append")

    def get_write_log(self) -> list[dict]:
        """Return the write log for audit."""
        return self._write_log
