"""
Live Cosmos DB Discovery Adapter

Connects to an Azure Cosmos DB (NoSQL API) account using the azure-cosmos SDK
and builds a DatabaseProfile with container metadata, throughput settings,
partition keys, indexing policies, and account-level configuration.

The azure-cosmos package is an optional dependency; when absent the caller
falls back to mock data with a logged warning.

Optional: azure-mgmt-cosmosdb + azure-identity for backup policy detection.
"""

from __future__ import annotations

import logging
import re

from config.migration_profiles import DatabaseProfile, TableProfile

logger = logging.getLogger("lakebase_ops.provisioning.cosmos")


class CosmosDiscoveryAdapter:
    """Discovers schema and configuration from a live Cosmos DB account."""

    def __init__(
        self,
        endpoint: str,
        key: str,
        database_name: str = "",
        subscription_id: str = "",
        resource_group: str = "",
    ):
        from azure.cosmos import CosmosClient

        self._client = CosmosClient(url=endpoint, credential=key)
        self._endpoint = endpoint
        self._database_name = database_name
        self._subscription_id = subscription_id
        self._resource_group = resource_group

    def discover(self) -> DatabaseProfile:
        """Connect, enumerate containers, and return a populated DatabaseProfile."""
        account = self._client.get_database_account()

        consistency_level = ""
        if hasattr(account, "ConsistencyPolicy") and account.ConsistencyPolicy:
            consistency_level = account.ConsistencyPolicy.get("defaultConsistencyLevel", "Session")

        multi_region_writes = getattr(account, "EnableMultipleWritableLocations", False) or False
        read_regions = getattr(account, "ReadableLocations", []) or []
        write_regions = getattr(account, "WritableLocations", []) or []
        region_names = list({loc.get("name", "") for loc in read_regions + write_regions if loc.get("name")})

        db_client = self._resolve_database()
        db_name = self._database_name or "default"

        containers: list[TableProfile] = []
        container_details: list[dict] = []
        partition_key_paths: list[str] = []
        total_ru = 0
        throughput_mode = "provisioned"
        autoscale_max_ru: int | None = None
        change_feed_mode = "LatestVersion"

        for container_props in db_client.list_containers():
            cid = container_props["id"]
            c_client = db_client.get_container_client(cid)
            full_props = c_client.read()

            pk_def = full_props.get("partitionKey", {})
            pk_paths = pk_def.get("paths", [])
            if pk_paths:
                partition_key_paths.append(pk_paths[0])

            indexing = full_props.get("indexingPolicy", {})
            indexing_mode = indexing.get("indexingMode", "consistent")

            cf_policy = full_props.get("changeFeedPolicy", {})
            if cf_policy.get("retentionDuration") or cf_policy.get("fullFidelityPolicy"):
                change_feed_mode = "AllVersionsAndDeletes"

            ru = 0
            c_autoscale_max: int | None = None
            try:
                offer = c_client.get_throughput()
                offer_props = offer.properties if hasattr(offer, "properties") else {}
                content = offer_props.get("content", offer_props)
                ru = content.get("offerThroughput", 0)
                autoscale_settings = content.get("offerAutopilotSettings") or content.get(
                    "offerAutoScaleSettings"
                )
                if autoscale_settings:
                    throughput_mode = "autoscale"
                    c_autoscale_max = autoscale_settings.get("maxThroughput", 0)
            except Exception:
                logger.debug("Could not read throughput for container %s", cid, exc_info=True)

            total_ru += ru

            item_count, size_bytes = self._estimate_item_count_and_size(c_client)

            containers.append(
                TableProfile(
                    schema_name="default",
                    table_name=cid,
                    row_count=item_count,
                    size_bytes=size_bytes,
                    index_count=len(indexing.get("includedPaths", [])),
                    has_triggers=False,
                    has_foreign_keys=False,
                    column_count=0,
                )
            )
            detail: dict = {
                "name": cid,
                "partition_key": pk_paths[0] if pk_paths else "",
                "ru_per_sec": ru,
                "indexing_policy": indexing_mode,
                "item_count": item_count,
                "size_bytes": size_bytes,
            }
            if c_autoscale_max:
                detail["autoscale_max_ru"] = c_autoscale_max
            container_details.append(detail)

        if not autoscale_max_ru and throughput_mode == "autoscale":
            autoscale_max_ru = max((d.get("autoscale_max_ru", 0) for d in container_details), default=None)

        total_size = sum(c.size_bytes for c in containers)
        backup_policy = self._fetch_backup_policy()

        return DatabaseProfile(
            name=db_name,
            size_bytes=total_size,
            size_gb=round(total_size / (1024**3), 2) if total_size else 0.0,
            table_count=len(containers),
            schema_count=1,
            schemas=["default"],
            tables=containers,
            extensions=[],
            functions=[],
            triggers=[],
            sequence_count=0,
            materialized_view_count=0,
            custom_type_count=0,
            foreign_key_count=0,
            has_logical_replication=False,
            replication_slots=[],
            pg_version="",
            cosmos_throughput_mode=throughput_mode,
            cosmos_ru_per_sec=total_ru,
            cosmos_partition_key_paths=partition_key_paths,
            cosmos_consistency_level=consistency_level,
            cosmos_change_feed_enabled=change_feed_mode == "AllVersionsAndDeletes",
            cosmos_change_feed_mode=change_feed_mode,
            cosmos_multi_region_writes=multi_region_writes,
            cosmos_regions=region_names,
            cosmos_container_details=container_details,
            cosmos_autoscale_max_ru=autoscale_max_ru,
            cosmos_backup_policy=backup_policy,
        )

    def _resolve_database(self):
        """Pick the target database; if none specified, use the first one found."""
        if self._database_name:
            return self._client.get_database_client(self._database_name)
        for db_props in self._client.list_databases():
            self._database_name = db_props["id"]
            return self._client.get_database_client(self._database_name)
        raise RuntimeError("No databases found in Cosmos DB account")

    def _fetch_backup_policy(self) -> str | None:
        """Detect account backup policy via the Azure Management SDK (optional)."""
        try:
            from azure.identity import DefaultAzureCredential
            from azure.mgmt.cosmosdb import CosmosDBManagementClient
        except ImportError:
            logger.debug("azure-mgmt-cosmosdb/azure-identity not installed - skipping backup policy detection")
            return None

        account_name = self._parse_account_name()
        if not account_name or not self._subscription_id or not self._resource_group:
            logger.debug("Missing subscription_id/resource_group - skipping backup policy detection")
            return None

        try:
            credential = DefaultAzureCredential()
            mgmt_client = CosmosDBManagementClient(credential, self._subscription_id)
            account = mgmt_client.database_accounts.get(self._resource_group, account_name)
            bp = getattr(account, "backup_policy", None)
            if bp is None:
                return None
            bp_type = getattr(bp, "type", None) or type(bp).__name__
            if "Continuous" in str(bp_type):
                return "continuous"
            return "periodic"
        except Exception:
            logger.debug("Could not fetch backup policy via management SDK", exc_info=True)
            return None

    def _parse_account_name(self) -> str | None:
        """Extract account name from the Cosmos DB endpoint URL."""
        match = re.match(r"https://([^.]+)\.documents\.azure\.com", self._endpoint)
        return match.group(1) if match else None

    @staticmethod
    def _estimate_item_count_and_size(container_client) -> tuple[int, int]:
        """Best-effort item count and storage size via aggregate query + response headers."""
        item_count = 0
        size_bytes = 0
        try:
            results = list(
                container_client.query_items(
                    query="SELECT VALUE COUNT(1) FROM c",
                    enable_cross_partition_query=True,
                )
            )
            item_count = int(results[0]) if results else 0

            headers = getattr(container_client.client_connection, "last_response_headers", None) or {}
            resource_usage = headers.get("x-ms-resource-usage", "")
            for part in resource_usage.split(";"):
                stripped = part.strip()
                if stripped.startswith("documentsSize="):
                    size_kb = int(stripped.split("=", 1)[1])
                    size_bytes = size_kb * 1024
                    break
        except Exception:
            logger.debug("Could not estimate count/size for container", exc_info=True)
        return item_count, size_bytes
