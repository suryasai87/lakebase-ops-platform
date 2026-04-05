"""
SQL queries for source database assessment and profiling.
Used by the AssessmentMixin to discover and profile Aurora/RDS/Cloud SQL instances.
All queries are read-only and use native PostgreSQL catalogs.
"""

# =============================================================================
# Schema Discovery — read-only introspection of source database
# =============================================================================

DISCOVER_SCHEMAS = """
    SELECT schema_name
    FROM information_schema.schemata
    WHERE schema_name NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
    ORDER BY schema_name
"""

DISCOVER_TABLES = """
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           c.relkind AS table_type,
           c.reltuples::bigint AS estimated_rows,
           pg_total_relation_size(c.oid) AS total_size_bytes,
           pg_relation_size(c.oid) AS table_size_bytes,
           (SELECT count(*) FROM pg_catalog.pg_index i WHERE i.indrelid = c.oid) AS index_count,
           (SELECT count(*) FROM pg_catalog.pg_attribute a
            WHERE a.attrelid = c.oid AND a.attnum > 0 AND NOT a.attisdropped) AS column_count
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema', 'pg_toast')
      AND c.relkind IN ('r', 'p')
    ORDER BY pg_total_relation_size(c.oid) DESC
"""

DISCOVER_EXTENSIONS = """
    SELECT extname AS name,
           extversion AS version
    FROM pg_catalog.pg_extension
    WHERE extname != 'plpgsql'
    ORDER BY extname
"""

DISCOVER_FUNCTIONS = """
    SELECT n.nspname AS schema_name,
           p.proname AS function_name,
           l.lanname AS language,
           pg_get_functiondef(p.oid) AS definition
    FROM pg_catalog.pg_proc p
    JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
    JOIN pg_catalog.pg_language l ON l.oid = p.prolang
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
      AND l.lanname != 'internal'
    ORDER BY n.nspname, p.proname
"""

DISCOVER_TRIGGERS = """
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           t.tgname AS trigger_name,
           pg_get_triggerdef(t.oid) AS definition
    FROM pg_catalog.pg_trigger t
    JOIN pg_catalog.pg_class c ON c.oid = t.tgrelid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE NOT t.tgisinternal
    ORDER BY n.nspname, c.relname, t.tgname
"""

DISCOVER_SEQUENCES = """
    SELECT n.nspname AS schema_name,
           c.relname AS sequence_name
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'S'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n.nspname, c.relname
"""

DISCOVER_CUSTOM_TYPES = """
    SELECT n.nspname AS schema_name,
           t.typname AS type_name,
           t.typtype AS type_kind
    FROM pg_catalog.pg_type t
    JOIN pg_catalog.pg_namespace n ON n.oid = t.typnamespace
    WHERE t.typtype IN ('e', 'c', 'd')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n.nspname, t.typname
"""

DISCOVER_FOREIGN_KEYS = """
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           con.conname AS constraint_name,
           confrelid::regclass AS referenced_table
    FROM pg_catalog.pg_constraint con
    JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE con.contype = 'f'
    ORDER BY n.nspname, c.relname
"""

DISCOVER_MATERIALIZED_VIEWS = """
    SELECT n.nspname AS schema_name,
           c.relname AS view_name,
           pg_total_relation_size(c.oid) AS size_bytes
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE c.relkind = 'm'
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n.nspname, c.relname
"""

DISCOVER_REPLICATION_SLOTS = """
    SELECT slot_name, plugin, slot_type, active
    FROM pg_catalog.pg_replication_slots
"""

DISCOVER_PUBLICATIONS = """
    SELECT pubname, puballtables
    FROM pg_catalog.pg_publication
"""

DISCOVER_RLS_POLICIES = """
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           p.polname AS policy_name,
           p.polcmd AS command,
           p.polpermissive AS permissive
    FROM pg_catalog.pg_policy p
    JOIN pg_catalog.pg_class c ON c.oid = p.polrelid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n.nspname, c.relname, p.polname
"""

DISCOVER_PARTITIONED_TABLES = """
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           pt.partstrat AS strategy
    FROM pg_catalog.pg_partitioned_table pt
    JOIN pg_catalog.pg_class c ON c.oid = pt.partrelid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n.nspname, c.relname
"""

DISCOVER_EVENT_TRIGGERS = """
    SELECT evtname AS trigger_name,
           evtevent AS event,
           evtenabled AS enabled
    FROM pg_catalog.pg_event_trigger
    ORDER BY evtname
"""

DISCOVER_LARGE_OBJECTS = """
    SELECT count(*) AS lo_count
    FROM pg_catalog.pg_largeobject_metadata
"""

DISCOVER_EXCLUSION_CONSTRAINTS = """
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           con.conname AS constraint_name
    FROM pg_catalog.pg_constraint con
    JOIN pg_catalog.pg_class c ON c.oid = con.conrelid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    WHERE con.contype = 'x'
    ORDER BY n.nspname, c.relname
"""

DISCOVER_CUSTOM_AGGREGATES = """
    SELECT n.nspname AS schema_name,
           p.proname AS aggregate_name
    FROM pg_catalog.pg_aggregate a
    JOIN pg_catalog.pg_proc p ON p.oid = a.aggfnoid
    JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
    WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n.nspname, p.proname
"""

DISCOVER_NON_DEFAULT_COLLATION = """
    SELECT n.nspname AS schema_name,
           c.relname AS table_name,
           a.attname AS column_name,
           col.collname AS collation_name
    FROM pg_catalog.pg_attribute a
    JOIN pg_catalog.pg_class c ON c.oid = a.attrelid
    JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
    JOIN pg_catalog.pg_collation col ON col.oid = a.attcollation
    WHERE a.attnum > 0
      AND NOT a.attisdropped
      AND a.attcollation != 0
      AND col.collname NOT IN ('default', 'C', 'POSIX', 'C.UTF-8', 'en_US.UTF-8')
      AND n.nspname NOT IN ('pg_catalog', 'information_schema')
    ORDER BY n.nspname, c.relname, a.attname
"""

# =============================================================================
# Workload Profiling — read-only performance analysis
# =============================================================================

WORKLOAD_TOP_QUERIES = """
    SELECT queryid, query, calls, total_exec_time, mean_exec_time,
           rows, shared_blks_hit, shared_blks_read
    FROM pg_stat_statements
    ORDER BY total_exec_time DESC
    LIMIT 20
"""

WORKLOAD_TABLE_STATS = """
    SELECT schemaname, relname,
           seq_scan, seq_tup_read, idx_scan, idx_tup_fetch,
           n_tup_ins, n_tup_upd, n_tup_del, n_live_tup, n_dead_tup,
           pg_total_relation_size(relid) AS total_size_bytes
    FROM pg_stat_user_tables
    ORDER BY (n_tup_ins + n_tup_upd + n_tup_del) DESC
"""

WORKLOAD_CONNECTION_STATS = """
    SELECT state, count(*) AS count
    FROM pg_stat_activity
    WHERE backend_type = 'client backend'
    GROUP BY state
"""

WORKLOAD_INDEX_USAGE = """
    SELECT schemaname, relname, indexrelname,
           idx_scan, idx_tup_read, idx_tup_fetch,
           pg_relation_size(indexrelid) AS index_size_bytes
    FROM pg_stat_user_indexes
    ORDER BY idx_scan DESC
"""

WORKLOAD_DATABASE_SIZE = """
    SELECT pg_database_size(current_database()) AS db_size_bytes
"""

# =============================================================================
# Profiling Queries — used by _live_workload in AssessmentMixin
# =============================================================================

PROFILE_WORKLOAD = """
    SELECT count(DISTINCT queryid) AS total_queries,
           sum(calls) AS total_calls,
           round(sum(CASE WHEN query ~* '^(SELECT|WITH)' THEN calls ELSE 0 END)::numeric
                 / NULLIF(sum(calls), 0) * 100, 1) AS reads_pct,
           round(sum(CASE WHEN query ~* '^(INSERT|UPDATE|DELETE)' THEN calls ELSE 0 END)::numeric
                 / NULLIF(sum(calls), 0) * 100, 1) AS writes_pct,
           round(sum(calls)::numeric
                 / NULLIF(EXTRACT(epoch FROM now() - pg_postmaster_start_time()), 0), 1) AS avg_qps,
           max(calls) AS peak_qps,
           round(sum(CASE WHEN query ~* '^(INSERT|UPDATE|DELETE)' THEN calls ELSE 0 END)::numeric
                 / NULLIF(EXTRACT(epoch FROM now() - pg_postmaster_start_time()), 0), 1) AS avg_tps,
           percentile_cont(0.99) WITHIN GROUP (ORDER BY mean_exec_time) AS p99_latency_ms
    FROM pg_stat_statements
    WHERE queryid IS NOT NULL
"""

PROFILE_TOP_QUERIES = """
    SELECT query, calls, round(mean_exec_time::numeric, 2) AS mean_ms
    FROM pg_stat_statements
    WHERE queryid IS NOT NULL
    ORDER BY total_exec_time DESC
    LIMIT 10
"""

PROFILE_HOT_TABLES = """
    SELECT relname
    FROM pg_stat_user_tables
    ORDER BY (n_tup_ins + n_tup_upd + n_tup_del) DESC
    LIMIT 10
"""

PROFILE_CONNECTIONS = """
    SELECT count(*) AS current_connections,
           count(*) AS peak_connections
    FROM pg_stat_activity
    WHERE backend_type = 'client backend'
"""

# Aliases for backward compatibility
DISCOVER_MATVIEWS = DISCOVER_MATERIALIZED_VIEWS
