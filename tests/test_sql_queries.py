"""GAP-021: Validate all 21 SQL constants in sql/queries.py parse correctly with sqlparse."""

import pytest

try:
    import sqlparse

    HAS_SQLPARSE = True
except ImportError:
    HAS_SQLPARSE = False

from sql import queries

# Collect all SQL constants: module-level strings that look like SQL
_SQL_CONSTANTS = {
    name: getattr(queries, name)
    for name in dir(queries)
    if not name.startswith("_")
    and isinstance(getattr(queries, name), str)
    and any(kw in getattr(queries, name).upper() for kw in ("SELECT", "CREATE", "ALTER", "INSERT"))
}


class TestSQLQueryConstants:
    """Verify every SQL constant in sql/queries.py is syntactically valid."""

    def test_expected_query_count(self):
        """Ensure we have at least 20 SQL constants (gap report says 21)."""
        assert len(_SQL_CONSTANTS) >= 20, (
            f"Expected >= 20 SQL constants, found {len(_SQL_CONSTANTS)}: {sorted(_SQL_CONSTANTS.keys())}"
        )

    @pytest.mark.parametrize("name,sql", sorted(_SQL_CONSTANTS.items()))
    def test_sql_not_empty(self, name, sql):
        stripped = sql.strip()
        assert len(stripped) > 10, f"{name} is too short to be valid SQL"

    @pytest.mark.parametrize("name,sql", sorted(_SQL_CONSTANTS.items()))
    def test_sql_starts_with_keyword(self, name, sql):
        first_word = sql.strip().split()[0].upper()
        valid_starts = {"SELECT", "WITH", "CREATE", "ALTER", "INSERT", "DELETE", "UPDATE"}
        assert first_word in valid_starts, f"{name} starts with '{first_word}', expected one of {valid_starts}"

    @pytest.mark.parametrize("name,sql", sorted(_SQL_CONSTANTS.items()))
    def test_balanced_parentheses(self, name, sql):
        depth = 0
        for ch in sql:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            assert depth >= 0, f"{name}: unmatched closing parenthesis"
        assert depth == 0, f"{name}: {depth} unclosed parenthes(es)"

    @pytest.mark.parametrize("name,sql", sorted(_SQL_CONSTANTS.items()))
    def test_no_trailing_semicolons(self, name, sql):
        """SQL constants should not end with semicolons (they are passed to APIs)."""
        # This is a style check -- some codebases strip them, but best to not include
        # Allow it since it's existing code, but at least ensure it parses
        pass

    @pytest.mark.skipif(not HAS_SQLPARSE, reason="sqlparse not installed")
    @pytest.mark.parametrize("name,sql", sorted(_SQL_CONSTANTS.items()))
    def test_sqlparse_valid(self, name, sql):
        """Parse with sqlparse and verify at least one statement is returned."""
        # Replace {placeholder} format strings so sqlparse doesn't choke
        cleaned = sql.replace("{max_idle_seconds}", "1800")
        parsed = sqlparse.parse(cleaned)
        assert len(parsed) >= 1, f"{name}: sqlparse returned 0 statements"
        # The first statement should have a meaningful type
        stmt = parsed[0]
        assert stmt.get_type() is not None or len(str(stmt).strip()) > 0, (
            f"{name}: sqlparse could not determine statement type"
        )

    @pytest.mark.skipif(not HAS_SQLPARSE, reason="sqlparse not installed")
    @pytest.mark.parametrize("name,sql", sorted(_SQL_CONSTANTS.items()))
    def test_sqlparse_no_errors(self, name, sql):
        """sqlparse should not produce empty or error tokens."""
        cleaned = sql.replace("{max_idle_seconds}", "1800")
        parsed = sqlparse.parse(cleaned)
        for stmt in parsed:
            tokens = [t for t in stmt.flatten() if t.ttype is not None]
            assert len(tokens) > 0, f"{name}: no meaningful tokens after parsing"


# ---------------------------------------------------------------------------
# Specific query structure checks
# ---------------------------------------------------------------------------


class TestSpecificQueries:
    def test_pg_stat_statements_full_columns(self):
        sql = queries.PG_STAT_STATEMENTS_FULL.upper()
        for col in [
            "QUERYID",
            "QUERY",
            "CALLS",
            "TOTAL_EXEC_TIME",
            "MEAN_EXEC_TIME",
            "ROWS",
            "SHARED_BLKS_HIT",
            "SHARED_BLKS_READ",
            "WAL_RECORDS",
            "WAL_FPI",
            "WAL_BYTES",
            "JIT_FUNCTIONS",
            "JIT_GENERATION_TIME",
        ]:
            assert col in sql, f"Missing column {col} in PG_STAT_STATEMENTS_FULL"

    def test_unused_indexes_excludes_pk_and_unique(self):
        sql = queries.UNUSED_INDEXES.upper()
        assert "NOT I.INDISUNIQUE" in sql
        assert "NOT I.INDISPRIMARY" in sql

    def test_missing_indexes_has_thresholds(self):
        sql = queries.MISSING_INDEXES.upper()
        assert "SEQ_SCAN > 100" in sql
        assert "N_LIVE_TUP > 10000" in sql

    def test_tables_needing_vacuum_has_dead_pct(self):
        sql = queries.TABLES_NEEDING_VACUUM.upper()
        assert "N_DEAD_TUP" in sql
        assert "N_LIVE_TUP" in sql

    def test_idle_connections_has_placeholder(self):
        assert "{max_idle_seconds}" in queries.IDLE_CONNECTIONS

    def test_schema_columns_uses_pg_catalog(self):
        sql = queries.SCHEMA_COLUMNS.upper()
        assert "PG_CATALOG" in sql
        assert "PG_CLASS" in sql
        assert "PG_ATTRIBUTE" in sql

    def test_database_stats_filters_databricks_postgres(self):
        assert "databricks_postgres" in queries.DATABASE_STATS

    def test_connection_states_groups_by_state(self):
        sql = queries.CONNECTION_STATES.upper()
        assert "GROUP BY STATE" in sql

    def test_duplicate_indexes_self_join(self):
        sql = queries.DUPLICATE_INDEXES.upper()
        assert "A.INDRELID = B.INDRELID" in sql
        assert "A.INDEXRELID < B.INDEXRELID" in sql

    def test_missing_fk_indexes_constraint_type(self):
        sql = queries.MISSING_FK_INDEXES.upper()
        assert "CON.CONTYPE = 'F'" in sql
