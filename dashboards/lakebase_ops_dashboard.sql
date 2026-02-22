-- ============================================================================
-- LakebaseOps AI/BI Dashboard SQL Queries
-- PRD Phase 1.3: Monitoring Dashboard
-- Deploy these as Databricks SQL queries for the AI/BI Dashboard (Lakeview)
-- ============================================================================

-- ============================================================================
-- 1. Performance Trending: pg_stat_statements History
-- ============================================================================

-- Top 10 Slowest Queries (Last 24 Hours)
SELECT
    query,
    queryid,
    SUM(calls) AS total_calls,
    ROUND(AVG(mean_exec_time), 2) AS avg_exec_time_ms,
    ROUND(SUM(total_exec_time), 2) AS total_time_ms,
    SUM(rows) AS total_rows,
    ROUND(SUM(shared_blks_read) * 8.0 / 1024, 2) AS total_read_mb,
    MAX(snapshot_timestamp) AS last_seen
FROM ops_catalog.lakebase_ops.pg_stat_history
WHERE snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 24 HOURS
GROUP BY query, queryid
ORDER BY total_time_ms DESC
LIMIT 10;

-- Query Performance Regression Detection (Compare Last 2 Hours vs Previous Day)
WITH recent AS (
    SELECT queryid, AVG(mean_exec_time) AS recent_avg
    FROM ops_catalog.lakebase_ops.pg_stat_history
    WHERE snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 2 HOURS
    GROUP BY queryid
),
baseline AS (
    SELECT queryid, AVG(mean_exec_time) AS baseline_avg
    FROM ops_catalog.lakebase_ops.pg_stat_history
    WHERE snapshot_timestamp BETWEEN CURRENT_TIMESTAMP - INTERVAL 25 HOURS
                                    AND CURRENT_TIMESTAMP - INTERVAL 1 HOUR
    GROUP BY queryid
)
SELECT
    r.queryid,
    ROUND(b.baseline_avg, 2) AS baseline_ms,
    ROUND(r.recent_avg, 2) AS recent_ms,
    ROUND((r.recent_avg - b.baseline_avg) / NULLIF(b.baseline_avg, 0) * 100, 1) AS pct_change,
    CASE
        WHEN r.recent_avg > b.baseline_avg * 2 THEN 'REGRESSION'
        WHEN r.recent_avg > b.baseline_avg * 1.5 THEN 'WARNING'
        ELSE 'STABLE'
    END AS status
FROM recent r
JOIN baseline b ON r.queryid = b.queryid
WHERE b.baseline_avg > 0
ORDER BY pct_change DESC
LIMIT 20;

-- ============================================================================
-- 2. Index Health Scorecard
-- ============================================================================

-- Index Recommendation Summary
SELECT
    recommendation_type,
    confidence,
    COUNT(*) AS count,
    SUM(CASE WHEN status = 'pending_review' THEN 1 ELSE 0 END) AS pending_review,
    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved,
    SUM(CASE WHEN status = 'executed' THEN 1 ELSE 0 END) AS executed,
    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected
FROM ops_catalog.lakebase_ops.index_recommendations
WHERE created_at > CURRENT_TIMESTAMP - INTERVAL 30 DAYS
GROUP BY recommendation_type, confidence
ORDER BY count DESC;

-- Pending Index Actions Requiring Review
SELECT
    recommendation_id,
    project_id,
    table_name,
    recommendation_type,
    index_name,
    confidence,
    estimated_impact,
    ddl_statement,
    created_at
FROM ops_catalog.lakebase_ops.index_recommendations
WHERE status = 'pending_review'
ORDER BY
    CASE confidence WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
    created_at DESC;

-- ============================================================================
-- 3. Vacuum Operations History
-- ============================================================================

-- Vacuum Operations (Last 7 Days)
SELECT
    DATE(executed_at) AS vacuum_date,
    operation_type,
    COUNT(*) AS operations,
    COUNT(CASE WHEN status = 'success' THEN 1 END) AS successful,
    COUNT(CASE WHEN status = 'failed' THEN 1 END) AS failed,
    ROUND(AVG(duration_seconds), 2) AS avg_duration_s
FROM ops_catalog.lakebase_ops.vacuum_history
WHERE executed_at > CURRENT_TIMESTAMP - INTERVAL 7 DAYS
GROUP BY DATE(executed_at), operation_type
ORDER BY vacuum_date DESC;

-- ============================================================================
-- 4. Sync Freshness Monitor
-- ============================================================================

-- Current Sync Status (All Table Pairs)
SELECT
    source_table,
    target_table,
    source_count,
    target_count,
    count_drift,
    ROUND(freshness_lag_seconds / 60.0, 1) AS lag_minutes,
    checksum_match,
    status,
    validated_at
FROM ops_catalog.lakebase_ops.sync_validation_history
WHERE validated_at = (
    SELECT MAX(validated_at)
    FROM ops_catalog.lakebase_ops.sync_validation_history sv2
    WHERE sv2.source_table = sync_validation_history.source_table
);

-- Sync Freshness Trend (Last 24 Hours)
SELECT
    source_table,
    DATE_TRUNC('hour', validated_at) AS hour,
    ROUND(AVG(freshness_lag_seconds), 0) AS avg_lag_seconds,
    MAX(freshness_lag_seconds) AS max_lag_seconds,
    AVG(count_drift) AS avg_count_drift
FROM ops_catalog.lakebase_ops.sync_validation_history
WHERE validated_at > CURRENT_TIMESTAMP - INTERVAL 24 HOURS
GROUP BY source_table, DATE_TRUNC('hour', validated_at)
ORDER BY source_table, hour;

-- ============================================================================
-- 5. Branch Utilization Dashboard
-- ============================================================================

-- Branch Lifecycle Events (Last 30 Days)
SELECT
    DATE(event_timestamp) AS event_date,
    event_type,
    COUNT(*) AS events,
    COUNT(DISTINCT branch_id) AS unique_branches
FROM ops_catalog.lakebase_ops.branch_lifecycle
WHERE event_timestamp > CURRENT_TIMESTAMP - INTERVAL 30 DAYS
GROUP BY DATE(event_timestamp), event_type
ORDER BY event_date DESC, event_type;

-- Active Branches by Project
SELECT
    project_id,
    COUNT(DISTINCT CASE WHEN event_type = 'created' THEN branch_id END)
    - COUNT(DISTINCT CASE WHEN event_type = 'deleted' THEN branch_id END) AS active_branches,
    COUNT(DISTINCT CASE WHEN is_protected THEN branch_id END) AS protected_branches,
    MAX(event_timestamp) AS last_activity
FROM ops_catalog.lakebase_ops.branch_lifecycle
GROUP BY project_id;

-- ============================================================================
-- 6. Health Metrics Dashboard
-- ============================================================================

-- Current Health Metrics (Latest Snapshot)
SELECT
    project_id,
    branch_id,
    metric_name,
    metric_value,
    threshold_level,
    snapshot_timestamp
FROM ops_catalog.lakebase_ops.lakebase_metrics
WHERE snapshot_timestamp = (
    SELECT MAX(snapshot_timestamp)
    FROM ops_catalog.lakebase_ops.lakebase_metrics m2
    WHERE m2.project_id = lakebase_metrics.project_id
      AND m2.branch_id = lakebase_metrics.branch_id
      AND m2.metric_name = lakebase_metrics.metric_name
)
ORDER BY project_id, branch_id, metric_name;

-- Health Metric Trends (Last 24 Hours, Hourly)
SELECT
    metric_name,
    DATE_TRUNC('hour', snapshot_timestamp) AS hour,
    ROUND(AVG(metric_value), 4) AS avg_value,
    ROUND(MIN(metric_value), 4) AS min_value,
    ROUND(MAX(metric_value), 4) AS max_value
FROM ops_catalog.lakebase_ops.lakebase_metrics
WHERE snapshot_timestamp > CURRENT_TIMESTAMP - INTERVAL 24 HOURS
  AND metric_name IN ('cache_hit_ratio', 'connection_utilization', 'max_dead_tuple_ratio')
GROUP BY metric_name, DATE_TRUNC('hour', snapshot_timestamp)
ORDER BY metric_name, hour;

-- ============================================================================
-- 7. Cost Attribution
-- ============================================================================

-- Lakebase Cost by Project and Branch (Last 30 Days)
SELECT
    usage_date,
    sku_name,
    usage_type,
    usage_metadata.database_instance_id AS instance_id,
    SUM(usage_quantity) AS total_dbus,
    ROUND(SUM(usage_quantity) * 0.07, 2) AS estimated_cost_usd
FROM system.billing.usage
WHERE billing_origin_product = 'DATABASE'
  AND usage_date > CURRENT_DATE - INTERVAL 30 DAYS
GROUP BY 1, 2, 3, 4
ORDER BY usage_date DESC, total_dbus DESC;

-- ============================================================================
-- 8. Cold Data Archival Tracking
-- ============================================================================

-- Archival Operations Summary
SELECT
    DATE(archived_at) AS archive_date,
    source_table,
    SUM(rows_archived) AS total_rows_archived,
    SUM(bytes_reclaimed) AS total_bytes_reclaimed,
    ROUND(SUM(bytes_reclaimed) / 1024.0 / 1024.0, 2) AS mb_reclaimed,
    COUNT(*) AS operations
FROM ops_catalog.lakebase_ops.data_archival_history
WHERE status = 'success'
GROUP BY DATE(archived_at), source_table
ORDER BY archive_date DESC;
