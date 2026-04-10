"""Assessment router — migration assessment pipeline for external PostgreSQL databases."""

import logging
import time
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("lakebase_ops_app.assessment")
router = APIRouter(prefix="/api/assessment", tags=["assessment"])

_agent = None

_SENSITIVE_FIELDS = {"source_password", "_password", "_token", "_secret"}
_PROFILE_TTL_SECONDS = 1800  # 30 minutes


def _get_agent():
    """Lazy-init the ProvisioningAgent with assessment capabilities."""
    global _agent
    if _agent is None:
        try:
            from agents import ProvisioningAgent
            from utils.alerting import AlertManager
            from utils.delta_writer import DeltaWriter
            from utils.lakebase_client import LakebaseClient

            client = LakebaseClient(workspace_host="", mock_mode=True)
            writer = DeltaWriter(mock_mode=True)
            alerter = AlertManager(mock_mode=True)
            _agent = ProvisioningAgent(client, writer, alerter)
        except Exception as e:
            logger.error(f"Failed to initialize ProvisioningAgent: {e}")
            raise HTTPException(status_code=500, detail="Assessment agent initialization failed") from e
    return _agent


class _ProfileCache:
    """TTL-aware profile cache that strips sensitive fields on storage."""

    def __init__(self, ttl: int = _PROFILE_TTL_SECONDS):
        self._store: dict[str, dict] = {}
        self._timestamps: dict[str, float] = {}
        self._ttl = ttl

    def get(self, key: str) -> dict:
        if key not in self._store:
            return {}
        if time.time() - self._timestamps.get(key, 0) > self._ttl:
            del self._store[key]
            del self._timestamps[key]
            return {}
        return self._store[key]

    def set(self, key: str, data: dict):
        sanitized = {k: v for k, v in data.items() if k not in _SENSITIVE_FIELDS}
        self._store[key] = sanitized
        self._timestamps[key] = time.time()
        self._evict_stale()

    def _evict_stale(self):
        now = time.time()
        expired = [k for k, ts in self._timestamps.items() if now - ts > self._ttl]
        for k in expired:
            self._store.pop(k, None)
            self._timestamps.pop(k, None)


class DiscoverRequest(BaseModel):
    endpoint: str = ""
    database: str = ""
    source_engine: str = "aurora-postgresql"
    region: str = "us-east-1"
    mock: bool = True
    source_user: str = ""
    source_password: str = ""
    subscription_id: str = ""
    resource_group: str = ""


class ProfileRequest(BaseModel):
    profile_id: str = ""
    mock: bool = True
    endpoint: str = ""
    database: str = ""
    source_user: str = ""
    source_password: str = ""


class ReadinessRequest(BaseModel):
    profile_id: str = ""
    mock: bool = True


class BlueprintRequest(BaseModel):
    profile_id: str = ""
    mock: bool = True


_profiles = _ProfileCache()
_assessment_history: list[dict] = []
_MAX_HISTORY = 50


@router.get("/history", operation_id="assessment_history")
def assessment_history():
    """Return the list of past assessment summaries (most recent first)."""
    return list(reversed(_assessment_history))


@router.post("/discover", operation_id="assessment_discover")
def discover(req: DiscoverRequest):
    """Connect to a source database and discover schema, extensions, and features."""
    agent = _get_agent()
    result = agent.connect_and_discover(
        endpoint=req.endpoint,
        database=req.database,
        source_engine=req.source_engine,
        region=req.region,
        mock=req.mock,
        source_user=req.source_user,
        source_password=req.source_password,
        subscription_id=req.subscription_id,
        resource_group=req.resource_group,
    )
    pid = result.get("profile_id", "")
    if pid:
        _profiles.set(pid, result)
    safe = {k: v for k, v in result.items() if not k.startswith("_") and k not in _SENSITIVE_FIELDS}
    return safe


@router.post("/profile", operation_id="assessment_profile")
def profile_workload(req: ProfileRequest):
    """Profile workload patterns (QPS, TPS, connections) for a discovered database."""
    agent = _get_agent()
    cached = _profiles.get(req.profile_id)

    result = agent.profile_workload(
        profile_data=cached if cached else None,
        mock=req.mock,
        source_user=req.source_user,
        source_password=req.source_password,
    )
    if req.profile_id:
        _profiles.set(req.profile_id, {**cached, **result})

    reads = result.get("reads_pct", 0)
    writes = result.get("writes_pct", 0)
    return {
        "qps": result.get("avg_qps"),
        "tps": result.get("avg_tps"),
        "active_connections": result.get("connection_count_avg"),
        "peak_connections": result.get("connection_count_peak"),
        "read_write_ratio": f"{reads:.0f}/{writes:.0f}" if reads else None,
        "p99_latency_ms": result.get("p99_latency_ms"),
        "top_queries": result.get("top_queries_count", 0),
        "hot_tables": result.get("hot_tables_count", 0),
    }


@router.post("/readiness", operation_id="assessment_readiness")
def assess_readiness(req: ReadinessRequest):
    """Compute readiness score against Lakebase constraints."""
    agent = _get_agent()
    cached = _profiles.get(req.profile_id)

    result = agent.assess_readiness(
        profile_data=cached if cached else None,
        workload_data=cached if cached else None,
    )
    if req.profile_id:
        _profiles.set(req.profile_id, {**cached, **result})

    dims = result.get("dimensions", {})
    dimension_scores = {k: v["score"] for k, v in dims.items()} if dims else {}

    return {
        "overall_score": result.get("overall_score"),
        "category": result.get("category"),
        "recommended_tier": result.get("recommended_tier"),
        "recommended_cu": result.get("recommended_cu_range"),
        "estimated_effort_days": result.get("estimated_effort_days"),
        "blocker_count": result.get("blocker_count", 0),
        "warning_count": result.get("warning_count", 0),
        "supported_extensions": result.get("supported_extensions", []),
        "unsupported_extensions": result.get("unsupported_extensions", []),
        "dimension_scores": dimension_scores,
        "blockers": result.get("blockers", []),
        "warnings": result.get("warnings", []),
        "sizing_by_env": result.get("sizing_by_env", []),
    }


@router.post("/blueprint", operation_id="assessment_blueprint")
def generate_blueprint(req: BlueprintRequest):
    """Generate a 4-phase migration blueprint."""
    agent = _get_agent()
    cached = _profiles.get(req.profile_id)

    result = agent.generate_migration_blueprint(
        profile_data=cached if cached else None,
        assessment_data=cached if cached else None,
        workload_data=cached if cached else None,
    )

    # Store blueprint result back into profile cache so timeline/cost endpoints work
    if req.profile_id:
        _profiles.set(req.profile_id, {**cached, **result})

    raw_phases = result.get("phases", [])
    phases = [
        {
            "name": p.get("name", ""),
            "duration_days": p.get("days"),
            "description": p.get("description", ""),
            "steps": p.get("steps", []),
        }
        for p in raw_phases
    ]

    response = {
        "strategy": result.get("strategy"),
        "total_effort_days": result.get("total_estimated_days"),
        "risk_level": result.get("risk_level"),
        "phases": phases,
        "prerequisite_count": result.get("prerequisite_count", 0),
        "markdown": result.get("report_markdown", ""),
    }

    _record_history(req.profile_id, cached, response)
    return response


@router.get("/timeline/{profile_id}", operation_id="assessment_timeline")
def assessment_timeline(profile_id: str):
    """Return Gantt-chart-ready phase data for a completed assessment."""
    cached = _profiles.get(profile_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Profile not found or expired")

    blueprint_obj = cached.get("_blueprint")
    if not blueprint_obj:
        raise HTTPException(status_code=404, detail="No blueprint generated for this profile")

    phases = []
    cumulative_day = 0
    for p in blueprint_obj.phases:
        phases.append(
            {
                "phase": p.phase_number,
                "name": p.name,
                "start_day": cumulative_day,
                "duration_days": p.estimated_days,
                "end_day": cumulative_day + p.estimated_days,
            }
        )
        cumulative_day += p.estimated_days

    return {
        "profile_id": profile_id,
        "total_days": cumulative_day,
        "strategy": blueprint_obj.strategy.value,
        "risk_level": blueprint_obj.risk_level,
        "phases": phases,
    }


@router.get("/extension-matrix/{profile_id}", operation_id="assessment_extension_matrix")
def assessment_extension_matrix(profile_id: str):
    """Return extension/feature compatibility matrix for a discovered database."""
    cached = _profiles.get(profile_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Profile not found or expired")

    profile_obj = cached.get("_profile")
    if not profile_obj or not profile_obj.databases:
        raise HTTPException(status_code=404, detail="No database profile found")

    db = profile_obj.databases[0]
    engine = profile_obj.source_engine.value
    from config.migration_profiles import ENGINE_KIND

    is_nosql = ENGINE_KIND.get(engine) == "nosql"

    matrix = []

    if is_nosql and engine == "cosmosdb-nosql":
        from utils.readiness_scorer import COSMOSDB_FEATURE_SUPPORT, COSMOSDB_FEATURE_WORKAROUNDS

        for feature, status in COSMOSDB_FEATURE_SUPPORT.items():
            workaround = COSMOSDB_FEATURE_WORKAROUNDS.get(feature, "")
            matrix.append(
                {
                    "name": feature,
                    "version": "",
                    "status": status,
                    "workaround": workaround,
                }
            )
    elif is_nosql:
        from utils.readiness_scorer import DYNAMODB_FEATURE_SUPPORT, DYNAMODB_FEATURE_WORKAROUNDS

        for feature, status in DYNAMODB_FEATURE_SUPPORT.items():
            workaround = DYNAMODB_FEATURE_WORKAROUNDS.get(feature, "")
            matrix.append(
                {
                    "name": feature,
                    "version": "",
                    "status": status,
                    "workaround": workaround,
                }
            )
    else:
        from utils.readiness_scorer import EXTENSION_WORKAROUNDS, LAKEBASE_SUPPORTED_EXTENSIONS

        for ext in db.extensions:
            name = ext.name.lower()
            supported = name in LAKEBASE_SUPPORTED_EXTENSIONS
            workaround = EXTENSION_WORKAROUNDS.get(name, "")
            status = "supported" if supported else ("workaround" if workaround else "unsupported")
            matrix.append(
                {
                    "name": ext.name,
                    "version": ext.version,
                    "status": status,
                    "workaround": workaround,
                }
            )

    return {
        "profile_id": profile_id,
        "database": db.name,
        "matrix_type": "feature" if is_nosql else "extension",
        "extensions": sorted(
            matrix,
            key=lambda e: (0 if e["status"] == "supported" else 1 if e["status"] == "workaround" else 2, e["name"]),
        ),
        "summary": {
            "supported": sum(1 for e in matrix if e["status"] == "supported"),
            "workaround": sum(1 for e in matrix if e["status"] == "workaround"),
            "unsupported": sum(1 for e in matrix if e["status"] == "unsupported"),
        },
    }


@router.get("/regions/{engine}", operation_id="assessment_regions")
def assessment_regions(engine: str):
    """Return available regions for a source engine's cloud provider."""
    from config.pricing import ENGINE_CLOUD_MAP, get_regions_for_engine

    cloud = ENGINE_CLOUD_MAP.get(engine, "aws")
    regions = get_regions_for_engine(engine)
    return {"engine": engine, "cloud": cloud, "regions": regions}


@router.get("/cost-estimate/{profile_id}", operation_id="assessment_cost_estimate")
def assessment_cost_estimate(profile_id: str, tier: str = "premium"):
    """Estimate monthly cost: source cloud DB vs Lakebase DBU pricing.

    Query params:
        tier: "premium" or "enterprise" (default: premium)
    """
    from config.pricing import (
        HOURS_PER_MONTH,
        LAKEBASE_COST_DISCLAIMER,
        LAKEBASE_DBU_PER_CU_HOUR,
        LAKEBASE_PRICING,
        PRICING_DISCLAIMER,
        PRICING_VERSION,
        SOURCE_ENGINES,
        get_lakebase_rates,
    )

    if tier not in ("premium", "enterprise"):
        tier = "premium"

    cached = _profiles.get(profile_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Profile not found or expired")

    profile_obj = cached.get("_profile")
    if not profile_obj or not profile_obj.databases:
        raise HTTPException(status_code=404, detail="No database profile found")

    db = profile_obj.databases[0]
    engine = profile_obj.source_engine.value
    region = profile_obj.source_region or "us-east-1"
    size_gb = db.size_gb

    engine_cfg = SOURCE_ENGINES.get(engine, SOURCE_ENGINES["aurora-postgresql"])

    src_rates, pricing_source = _get_live_rates(engine, region)

    lb_rates = get_lakebase_rates(engine, region, tier=tier)

    workload = profile_obj.workload
    avg_qps = workload.avg_qps if workload else 1000
    avg_connections = workload.connection_count_avg if workload else 50

    assessment_obj = cached.get("_assessment")
    if assessment_obj and hasattr(assessment_obj, "recommended_cu_min") and assessment_obj.recommended_cu_min > 0:
        cu_estimate = (assessment_obj.recommended_cu_min + assessment_obj.recommended_cu_max) / 2
    else:
        cu_estimate = max(1, min(128, avg_connections / 209))

    is_cosmosdb = engine == "cosmosdb-nosql"
    is_dynamodb = engine == "dynamodb"
    if is_cosmosdb:
        cosmos_cost = _estimate_cosmosdb_cost(db, src_rates, size_gb, region)
        source_compute = cosmos_cost["compute"]
        source_storage = cosmos_cost["storage"]
        source_io = cosmos_cost["backup"]
        source_total = cosmos_cost["total"]
    elif is_dynamodb:
        reads_pct = workload.reads_pct if workload and workload.reads_pct else 70.0
        writes_pct = workload.writes_pct if workload and workload.writes_pct else 30.0
        read_qps = avg_qps * (reads_pct / 100.0)
        write_qps = avg_qps * (writes_pct / 100.0)
        seconds_per_month = 2_592_000
        wru_rate = src_rates.get("wru_per_million", 1.25)
        rru_rate = src_rates.get("rru_per_million", 0.25)
        source_compute = 0.0
        source_storage = src_rates["storage_per_gb_month"] * size_gb
        source_io = (
            (write_qps * seconds_per_month / 1_000_000) * wru_rate
            + (read_qps * seconds_per_month / 1_000_000) * rru_rate
        )
        source_total = source_compute + source_storage + source_io
    else:
        source_compute = src_rates["compute_per_hour"] * HOURS_PER_MONTH
        source_storage = src_rates["storage_per_gb_month"] * size_gb
        source_io = (
            src_rates["io_per_million"] * (avg_qps * 2_592_000 / 1_000_000) if src_rates["io_per_million"] else 0
        )
        source_total = source_compute + source_storage + source_io

    lakebase_dbu_per_hour = cu_estimate * LAKEBASE_DBU_PER_CU_HOUR
    lakebase_compute = lakebase_dbu_per_hour * lb_rates["dbu_rate"] * HOURS_PER_MONTH
    lakebase_storage = lb_rates["storage_dsu_per_gb_month"] * size_gb
    lakebase_total = lakebase_compute + lakebase_storage

    savings_pct = round((1 - lakebase_total / source_total) * 100, 1) if source_total > 0 else 0

    pricing_urls = {
        "source": engine_cfg["source_url"],
        "lakebase": LAKEBASE_PRICING["source_url"],
    }

    tier_label = LAKEBASE_PRICING["tiers"][tier]["label"]
    sku_name = LAKEBASE_PRICING["sku_pattern"].replace(
        "{PREMIUM|ENTERPRISE}", tier.upper()
    ).replace("{REGION}", region.upper().replace("-", "_"))

    # --- Environment cost breakdown ---
    env_costs = []
    if assessment_obj and hasattr(assessment_obj, "sizing_by_env"):
        for es in assessment_obj.sizing_by_env:
            avg_cu = (es.cu_min + es.cu_max) / 2
            env_compute = avg_cu * LAKEBASE_DBU_PER_CU_HOUR * lb_rates["dbu_rate"] * HOURS_PER_MONTH
            env_storage = lb_rates["storage_dsu_per_gb_month"] * size_gb
            if es.scale_to_zero:
                utilization = 0.35 if es.env == "dev" else 0.60
                env_compute *= utilization
            env_total = env_compute + env_storage
            env_costs.append({
                "env": es.env,
                "cu_min": es.cu_min,
                "cu_max": es.cu_max,
                "avg_cu": round(avg_cu, 1),
                "scale_to_zero": es.scale_to_zero,
                "compute": round(env_compute, 2),
                "storage": round(env_storage, 2),
                "total": round(env_total, 2),
                "notes": es.notes,
            })

    lakebase_staleness = None
    try:
        from config.pricing_fetcher import check_lakebase_pricing_staleness
        lakebase_staleness = check_lakebase_pricing_staleness()
    except Exception:
        logger.debug("Could not check Lakebase pricing staleness", exc_info=True)

    workload_source = workload.workload_source if workload and hasattr(workload, "workload_source") else "observed"
    workload_caveat = None
    if workload_source == "heuristic":
        workload_caveat = (
            "Workload metrics are estimated from provisioned throughput, not observed usage. "
            "Actual QPS/TPS may differ significantly."
        )
    elif workload_source == "mock":
        workload_caveat = "Workload metrics are synthetic mock data for demonstration purposes."

    result = {
        "profile_id": profile_id,
        "engine": engine,
        "region": region,
        "size_gb": round(size_gb, 1),
        "cu_estimate": round(cu_estimate, 1),
        "tier": tier,
        "tier_label": tier_label,
        "sku_name": sku_name,
        "pricing_version": PRICING_VERSION,
        "pricing_source": pricing_source,
        "workload_source": workload_source,
        "disclaimer": PRICING_DISCLAIMER,
        "cost_disclaimer": LAKEBASE_COST_DISCLAIMER,
        "pricing_urls": pricing_urls,
        "source": {
            "label": engine_cfg["label"],
            "instance_ref": engine_cfg["instance_ref"],
            "source_url": engine_cfg["source_url"],
            "confidence": engine_cfg.get("confidence", "estimated"),
            "last_verified": engine_cfg.get("last_verified", PRICING_VERSION),
            "compute": round(source_compute, 2),
            "storage": round(source_storage, 2),
            "io": round(source_io, 2),
            "total": round(source_total, 2),
            "rates": _build_source_rates_dict(src_rates, engine),
            "formulas": engine_cfg["formulas"],
        },
        "lakebase": {
            "label": f"Databricks Lakebase ({tier_label})",
            "source_url": LAKEBASE_PRICING["source_url"],
            "pricing_source": "static",
            "pricing_version": PRICING_VERSION,
            "compute": round(lakebase_compute, 2),
            "storage": round(lakebase_storage, 2),
            "total": round(lakebase_total, 2),
            "rates": {
                "dbu_rate": lb_rates["dbu_rate"],
                "storage_dsu_per_gb_month": lb_rates["storage_dsu_per_gb_month"],
                "dbu_per_hour": round(lakebase_dbu_per_hour, 1),
            },
            "formulas": LAKEBASE_PRICING["formulas"],
        },
        "savings_pct": savings_pct,
        "savings_monthly": round(source_total - lakebase_total, 2),
    }

    if workload_caveat:
        result["workload_caveat"] = workload_caveat

    if env_costs:
        result["env_cost_breakdown"] = env_costs

    if is_cosmosdb:
        result["cosmos_cost_detail"] = cosmos_cost

    committed_discounts = LAKEBASE_PRICING.get("committed_use_discounts")
    if committed_discounts:
        result["committed_use_discounts"] = {
            "1_year": {
                "discount_pct": committed_discounts["1_year"]["discount_pct"],
                "label": committed_discounts["1_year"]["label"],
                "estimated_total": round(lakebase_total * (1 - committed_discounts["1_year"]["discount_pct"] / 100), 2),
            },
            "3_year": {
                "discount_pct": committed_discounts["3_year"]["discount_pct"],
                "label": committed_discounts["3_year"]["label"],
                "estimated_total": round(lakebase_total * (1 - committed_discounts["3_year"]["discount_pct"] / 100), 2),
            },
            "note": committed_discounts["note"],
        }

    if lakebase_staleness:
        result["lakebase_staleness_warning"] = lakebase_staleness

    return result


def _build_source_rates_dict(src_rates: dict, engine: str) -> dict:
    """Build the rates dict for the response, including DynamoDB-specific fields."""
    rates = {
        "compute_per_hour": src_rates.get("compute_per_hour", 0),
        "storage_per_gb_month": src_rates.get("storage_per_gb_month", 0),
        "io_per_million": src_rates.get("io_per_million", 0),
    }
    if engine == "dynamodb":
        rates["wru_per_million"] = src_rates.get("wru_per_million", 1.25)
        rates["rru_per_million"] = src_rates.get("rru_per_million", 0.25)
    return rates


def _get_live_rates(engine: str, region: str) -> tuple[dict, str]:
    """Try live/cached pricing, fall back to static for all engines."""
    try:
        from config.pricing_fetcher import get_live_source_rates
        return get_live_source_rates(engine, region)
    except Exception:
        from config.pricing import get_source_rates
        return get_source_rates(engine, region), "static"


def _estimate_cosmosdb_cost(db, src_rates: dict, size_gb: float, region: str) -> dict:
    """
    Detailed CosmosDB cost model accounting for multi-region, autoscale, and backup.
    """
    from config.pricing import HOURS_PER_MONTH

    ru_per_sec = db.cosmos_ru_per_sec or 1000
    ru_rate_per_100 = src_rates.get("compute_per_hour", 0.008)
    storage_rate = src_rates.get("storage_per_gb_month", 0.25)

    is_autoscale = db.cosmos_throughput_mode == "autoscale"
    if is_autoscale:
        max_ru = db.cosmos_autoscale_max_ru or ru_per_sec
        effective_ru = max(max_ru * 0.1, max_ru * 0.6)
    else:
        effective_ru = ru_per_sec

    base_compute = (effective_ru / 100) * ru_rate_per_100 * HOURS_PER_MONTH

    num_regions = len(db.cosmos_regions) if db.cosmos_regions else 1
    multi_write = db.cosmos_multi_region_writes or False
    if multi_write and num_regions > 1:
        region_multiplier = num_regions
    elif num_regions > 1:
        region_multiplier = 1 + (num_regions - 1) * 0.5
    else:
        region_multiplier = 1.0

    compute_total = base_compute * region_multiplier

    storage_total = storage_rate * size_gb * max(num_regions, 1)

    backup_policy = db.cosmos_backup_policy or "periodic"
    backup_cost = 0.20 * size_gb if backup_policy == "continuous" else 0.0

    total = compute_total + storage_total + backup_cost

    reserved_rate = None
    try:
        from config.pricing_fetcher import fetch_cosmosdb_reserved_rate
        reserved_rate = fetch_cosmosdb_reserved_rate(region)
    except Exception:
        logger.debug("Could not fetch CosmosDB reserved rate", exc_info=True)

    reserved_compute = None
    reserved_savings_pct = None
    if reserved_rate and reserved_rate > 0:
        reserved_compute = (effective_ru / 100) * reserved_rate * HOURS_PER_MONTH * region_multiplier
        reserved_savings_pct = round((1 - reserved_compute / compute_total) * 100, 1) if compute_total > 0 else 0

    return {
        "compute": round(compute_total, 2),
        "storage": round(storage_total, 2),
        "backup": round(backup_cost, 2),
        "total": round(total, 2),
        "effective_ru_per_sec": round(effective_ru, 0),
        "region_multiplier": region_multiplier,
        "num_regions": num_regions,
        "multi_region_writes": multi_write,
        "throughput_mode": db.cosmos_throughput_mode or "provisioned",
        "backup_policy": backup_policy,
        "reserved_1yr_compute": round(reserved_compute, 2) if reserved_compute else None,
        "reserved_1yr_savings_pct": reserved_savings_pct,
    }


def _record_history(profile_id: str, cached: dict, blueprint_resp: dict):
    """Append a summary to the in-memory assessment history."""
    entry = {
        "profile_id": profile_id,
        "source_engine": cached.get("source_engine", "unknown"),
        "database": cached.get("database", "unknown"),
        "size_gb": cached.get("size_gb", 0),
        "overall_score": cached.get("overall_score"),
        "category": cached.get("category"),
        "strategy": blueprint_resp.get("strategy"),
        "total_effort_days": blueprint_resp.get("total_effort_days"),
        "risk_level": blueprint_resp.get("risk_level"),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    _assessment_history.append(entry)
    if len(_assessment_history) > _MAX_HISTORY:
        _assessment_history.pop(0)
