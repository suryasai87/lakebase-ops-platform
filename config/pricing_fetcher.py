"""
Live Pricing Fetcher with Cache & Static Fallback

3-tier pricing architecture for source engine rates:
  1. Live fetch from Azure Retail Prices API / AWS Price List Bulk API
  2. File cache (~/.lakebase-ops/pricing_cache.json, 24h TTL)
  3. Static fallback from config/pricing.py

Databricks Lakebase does not publish a public pricing API, so Lakebase
rates always come from the static registry (config/pricing.py) with a
90-day staleness check.  This is by design - Lakebase pricing is stable
and updated manually when Databricks publishes new list prices.  The cost
estimate API response includes pricing_source="static" for Lakebase to
make this transparent to consumers.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger("lakebase_ops.pricing_fetcher")

_CACHE_DIR = Path.home() / ".lakebase-ops"
_CACHE_FILE = _CACHE_DIR / "pricing_cache.json"
_CACHE_TTL_SECONDS = 86400  # 24 hours
_API_TIMEOUT = 15

_AZURE_RETAIL_API = "https://prices.azure.com/api/retail/prices"

_REGION_MAP = {
    "eastus": "eastus",
    "westus2": "westus2",
    "westeurope": "westeurope",
    "southeastasia": "southeastasia",
}


def _load_cache() -> dict:
    """Load cached pricing data if fresh enough."""
    try:
        if not _CACHE_FILE.exists():
            return {}
        data = json.loads(_CACHE_FILE.read_text())
        ts = data.get("_timestamp", 0)
        if time.time() - ts > _CACHE_TTL_SECONDS:
            return {}
        return data
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    """Persist pricing data to disk."""
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        data["_timestamp"] = time.time()
        _CACHE_FILE.write_text(json.dumps(data, indent=2))
    except Exception as e:
        logger.warning(f"Failed to write pricing cache: {e}")


def fetch_cosmosdb_pricing(region: str = "eastus") -> dict | None:
    """
    Fetch current Cosmos DB pricing from the Azure Retail Prices API.

    Returns a dict with keys: compute_per_hour, storage_per_gb_month, io_per_million
    matching the static registry format, or None on failure.
    """
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed - cannot fetch live pricing")
        return None

    arm_region = _REGION_MAP.get(region, region)

    cache = _load_cache()
    cache_key = f"cosmosdb-nosql:{arm_region}"
    if cache_key in cache:
        logger.info("Using cached CosmosDB pricing for %s", arm_region)
        return cache[cache_key]

    try:
        ru_rate = _fetch_ru_rate(requests, arm_region)
        storage_rate = _fetch_storage_rate(requests, arm_region)

        if ru_rate is None and storage_rate is None:
            return None

        rates = {
            "compute_per_hour": ru_rate or 0.008,
            "storage_per_gb_month": storage_rate or 0.25,
            "io_per_million": 0.0,
        }

        cache[cache_key] = rates
        _save_cache(cache)

        logger.info(
            "Fetched live CosmosDB pricing for %s: RU=$%.4f/100RU/hr, storage=$%.3f/GB/mo",
            arm_region,
            rates["compute_per_hour"],
            rates["storage_per_gb_month"],
        )
        return rates
    except Exception as e:
        logger.warning(f"Live pricing fetch failed: {e}")
        return None


def _fetch_ru_rate(requests_mod, arm_region: str) -> float | None:
    """Fetch the per-100-RU/hour rate for provisioned throughput."""
    odata_filter = (
        f"serviceName eq 'Azure Cosmos DB' "
        f"and armRegionName eq '{arm_region}' "
        f"and skuName eq 'D1' "
        f"and meterName eq '100 RUs'"
    )
    resp = requests_mod.get(
        _AZURE_RETAIL_API,
        params={"api-version": "2023-01-01-preview", "$filter": odata_filter},
        timeout=_API_TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json().get("Items", [])

    for item in items:
        if item.get("type") == "Consumption" and "Reserved" not in item.get("skuName", ""):
            return item.get("retailPrice", 0.008)
    return None


def _fetch_storage_rate(requests_mod, arm_region: str) -> float | None:
    """Fetch the per-GB/month storage rate."""
    odata_filter = (
        f"serviceName eq 'Azure Cosmos DB' "
        f"and armRegionName eq '{arm_region}' "
        f"and meterName eq 'Data Stored'"
    )
    resp = requests_mod.get(
        _AZURE_RETAIL_API,
        params={"api-version": "2023-01-01-preview", "$filter": odata_filter},
        timeout=_API_TIMEOUT,
    )
    resp.raise_for_status()
    items = resp.json().get("Items", [])

    for item in items:
        if item.get("type") == "Consumption":
            return item.get("retailPrice", 0.25)
    return None


def fetch_cosmosdb_reserved_rate(region: str = "eastus") -> float | None:
    """Fetch the 1-year reserved capacity discount rate for 100 RU/s."""
    try:
        import requests
    except ImportError:
        return None

    arm_region = _REGION_MAP.get(region, region)
    odata_filter = (
        f"serviceName eq 'Azure Cosmos DB' "
        f"and armRegionName eq '{arm_region}' "
        f"and skuName eq 'D1' "
        f"and meterName eq '100 RUs' "
        f"and reservationTerm eq '1 Year'"
    )
    try:
        resp = requests.get(
            _AZURE_RETAIL_API,
            params={"api-version": "2023-01-01-preview", "$filter": odata_filter},
            timeout=_API_TIMEOUT,
        )
        resp.raise_for_status()
        items = resp.json().get("Items", [])
        for item in items:
            hourly = item.get("retailPrice", 0) / 8760
            if hourly > 0:
                return round(hourly, 6)
    except Exception:
        logger.debug("Could not fetch CosmosDB reserved rate", exc_info=True)
    return None


_AWS_REGION_LABEL = {
    "us-east-1": "US East (N. Virginia)",
    "us-west-2": "US West (Oregon)",
    "eu-west-1": "EU (Ireland)",
    "ap-southeast-1": "Asia Pacific (Singapore)",
}

_AWS_PRICING_API = "https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws"

_AWS_ENGINES = {"aurora-postgresql", "aurora-postgresql-io", "rds-postgresql", "dynamodb"}


def fetch_aws_rds_pricing(engine: str, region: str) -> dict | None:
    """
    Fetch Aurora/RDS PostgreSQL pricing from the AWS Price List Bulk JSON API.

    Uses the /AmazonRDS/current/region_index.json endpoint which is public
    and unauthenticated.  Parses the per-region JSON to find the matching
    instance type hourly rate.
    """
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed - cannot fetch AWS live pricing")
        return None

    cache = _load_cache()
    cache_key = f"{engine}:{region}"
    if cache_key in cache:
        logger.info("Using cached AWS pricing for %s:%s", engine, region)
        return cache[cache_key]

    region_label = _AWS_REGION_LABEL.get(region)
    if not region_label:
        return None

    try:
        url = f"{_AWS_PRICING_API}/AmazonRDS/current/{region}/index.json"
        resp = requests.get(url, timeout=_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        is_aurora = engine.startswith("aurora-postgresql")
        is_io_optimized = engine == "aurora-postgresql-io"
        target_instance = "db.r6g.xlarge"

        for product_sku, product in data.get("products", {}).items():
            attrs = product.get("attributes", {})
            if attrs.get("instanceType") != target_instance:
                continue
            if is_aurora and "Aurora" not in attrs.get("databaseEngine", ""):
                continue
            if not is_aurora and "Aurora" in attrs.get("databaseEngine", ""):
                continue
            if attrs.get("databaseEngine", "") and "PostgreSQL" not in attrs.get("databaseEngine", ""):
                continue

            sku_terms = data.get("terms", {}).get("OnDemand", {}).get(product_sku, {})
            for term in sku_terms.values():
                for dim in term.get("priceDimensions", {}).values():
                    price_str = dim.get("pricePerUnit", {}).get("USD", "0")
                    price = float(price_str)
                    if price > 0:
                        storage_rate = 0.225 if is_io_optimized else 0.10
                        io_rate = 0.0 if is_io_optimized else 0.20
                        rates = {
                            "compute_per_hour": price,
                            "storage_per_gb_month": storage_rate,
                            "io_per_million": io_rate,
                        }
                        cache[cache_key] = rates
                        _save_cache(cache)
                        logger.info("Fetched live AWS %s pricing for %s: $%.3f/hr", engine, region, price)
                        return rates
    except Exception as e:
        logger.warning("AWS RDS live pricing fetch failed for %s/%s: %s", engine, region, e)

    return None


def fetch_aws_dynamodb_pricing(region: str) -> dict | None:
    """
    Fetch DynamoDB on-demand pricing from the AWS Price List Bulk JSON API.

    Extracts WRU (WriteRequestUnits) and RRU (ReadRequestUnits) per-million
    rates from the /AmazonDynamoDB/current/{region}/index.json endpoint.
    """
    try:
        import requests
    except ImportError:
        logger.warning("requests not installed - cannot fetch AWS live pricing")
        return None

    cache = _load_cache()
    cache_key = f"dynamodb:{region}"
    if cache_key in cache:
        logger.info("Using cached DynamoDB pricing for %s", region)
        return cache[cache_key]

    try:
        url = f"{_AWS_PRICING_API}/AmazonDynamoDB/current/{region}/index.json"
        resp = requests.get(url, timeout=_API_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        wru_rate = None
        rru_rate = None
        storage_rate = None

        for product_sku, product in data.get("products", {}).items():
            attrs = product.get("attributes", {})
            usage_type = attrs.get("usagetype", "")
            group = attrs.get("group", "")

            sku_terms = data.get("terms", {}).get("OnDemand", {}).get(product_sku, {})
            for term in sku_terms.values():
                for dim in term.get("priceDimensions", {}).values():
                    price_str = dim.get("pricePerUnit", {}).get("USD", "0")
                    price = float(price_str)
                    if price <= 0:
                        continue

                    if "WriteRequestUnits" in usage_type:
                        wru_rate = price * 1_000_000
                    elif "ReadRequestUnits" in usage_type:
                        rru_rate = price * 1_000_000
                    elif group == "DDB-Storage" or "TimedStorage" in usage_type:
                        storage_rate = price

        if wru_rate or rru_rate:
            rates = {
                "compute_per_hour": 0.0,
                "storage_per_gb_month": storage_rate or 0.25,
                "io_per_million": 0.0,
                "wru_per_million": wru_rate or 1.25,
                "rru_per_million": rru_rate or 0.25,
            }
            cache[cache_key] = rates
            _save_cache(cache)
            logger.info(
                "Fetched live DynamoDB pricing for %s: WRU=$%.3f/M, RRU=$%.3f/M",
                region, rates["wru_per_million"], rates["rru_per_million"],
            )
            return rates
    except Exception as e:
        logger.warning("AWS DynamoDB live pricing fetch failed for %s: %s", region, e)

    return None


def get_live_source_rates(engine: str, region: str) -> tuple[dict, str]:
    """
    Try live pricing first, then cache, then static fallback.

    Returns (rates_dict, source) where source is "live", "cached", or "static".

    Supported live engines:
      - cosmosdb-nosql (Azure Retail Prices API)
      - aurora-postgresql, aurora-postgresql-io, rds-postgresql (AWS Price List API)
      - dynamodb (AWS Price List API)
    """
    from config.pricing import get_source_rates

    if engine == "cosmosdb-nosql":
        cache = _load_cache()
        cache_key = f"cosmosdb-nosql:{_REGION_MAP.get(region, region)}"
        if cache_key in cache:
            return cache[cache_key], "cached"
        live_rates = fetch_cosmosdb_pricing(region)
        if live_rates:
            return live_rates, "live"
        return get_source_rates(engine, region), "static"

    if engine in ("aurora-postgresql", "aurora-postgresql-io", "rds-postgresql"):
        cache = _load_cache()
        cache_key = f"{engine}:{region}"
        if cache_key in cache:
            return cache[cache_key], "cached"
        live_rates = fetch_aws_rds_pricing(engine, region)
        if live_rates:
            return live_rates, "live"
        return get_source_rates(engine, region), "static"

    if engine == "dynamodb":
        cache = _load_cache()
        cache_key = f"dynamodb:{region}"
        if cache_key in cache:
            return cache[cache_key], "cached"
        live_rates = fetch_aws_dynamodb_pricing(region)
        if live_rates:
            return live_rates, "live"
        return get_source_rates(engine, region), "static"

    return get_source_rates(engine, region), "static"


def check_lakebase_pricing_staleness() -> str | None:
    """
    Check if static Lakebase pricing is older than 90 days from PRICING_VERSION.

    Returns a warning string if stale, None otherwise.
    """
    from config.pricing import PRICING_VERSION

    try:
        from datetime import UTC, datetime

        version_date = datetime.strptime(PRICING_VERSION, "%Y-%m")
        now = datetime.now(UTC)
        days_old = (now - version_date.replace(tzinfo=UTC)).days
        if days_old > 90:
            return (
                f"Lakebase pricing data is {days_old} days old (version {PRICING_VERSION}). "
                "Rates may have changed; contact your Databricks account team for current pricing."
            )
    except Exception:
        logger.debug("Could not check Lakebase pricing staleness", exc_info=True)
    return None
