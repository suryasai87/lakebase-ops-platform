"""Custom exception hierarchy for LakebaseOps Platform.

Provides structured error types for agents, services, and utilities
to replace generic Exception catches with specific, actionable errors.

Usage:
    from utils.exceptions import LakebaseConnectionError, QueryError

    try:
        result = client.execute(sql)
    except QueryError as e:
        logger.error(f"Query failed: {e}")
        # handle specifically
    except LakebaseOpsError as e:
        logger.error(f"LakebaseOps error: {e}")
        # catch-all for platform errors
"""

from __future__ import annotations


class LakebaseOpsError(Exception):
    """Base exception for all LakebaseOps platform errors.

    All custom exceptions in this module inherit from this class,
    allowing callers to catch platform errors broadly when needed.
    """

    def __init__(self, message: str = "", detail: str = "") -> None:
        self.detail = detail
        super().__init__(message)


class LakebaseConnectionError(LakebaseOpsError):
    """Raised when a connection to a Lakebase PostgreSQL endpoint fails.

    Examples: OAuth token refresh failure, endpoint unreachable,
    connection pool exhausted, psycopg connection timeout.
    """

    def __init__(
        self,
        message: str = "Failed to connect to Lakebase endpoint",
        endpoint: str = "",
        detail: str = "",
    ) -> None:
        self.endpoint = endpoint
        super().__init__(message, detail=detail)


class QueryError(LakebaseOpsError):
    """Raised when a SQL query execution fails.

    Examples: syntax error in generated SQL, statement timeout,
    permission denied on a table, SQL Statement Execution API error.
    """

    def __init__(
        self,
        message: str = "Query execution failed",
        query: str = "",
        detail: str = "",
    ) -> None:
        self.query = query
        super().__init__(message, detail=detail)


class AuthError(LakebaseOpsError):
    """Raised when authentication or authorization fails.

    Examples: expired OAuth token that cannot be refreshed,
    missing Databricks CLI profile, insufficient workspace permissions,
    service principal credential error.
    """

    def __init__(
        self,
        message: str = "Authentication failed",
        detail: str = "",
    ) -> None:
        super().__init__(message, detail=detail)


class ConfigError(LakebaseOpsError):
    """Raised when required configuration is missing or invalid.

    Examples: missing environment variable (LAKEBASE_PROJECT_ID),
    invalid warehouse ID, malformed job definitions JSON.
    """

    def __init__(
        self,
        message: str = "Configuration error",
        setting: str = "",
        detail: str = "",
    ) -> None:
        self.setting = setting
        super().__init__(message, detail=detail)


class AlertDeliveryError(LakebaseOpsError):
    """Raised when an alert fails to be delivered to a channel.

    Examples: Slack webhook returns 4xx/5xx, PagerDuty API timeout,
    SMTP connection refused.
    """

    def __init__(
        self,
        message: str = "Alert delivery failed",
        channel: str = "",
        detail: str = "",
    ) -> None:
        self.channel = channel
        super().__init__(message, detail=detail)


class DeltaWriteError(LakebaseOpsError):
    """Raised when writing to a Delta Lake table fails.

    Examples: SQL Statement Execution API error, schema mismatch,
    catalog/schema not found, permission denied on table.
    """

    def __init__(
        self,
        message: str = "Delta write failed",
        table: str = "",
        detail: str = "",
    ) -> None:
        self.table = table
        super().__init__(message, detail=detail)
