"""Assessment router — migration assessment pipeline for external PostgreSQL databases."""

import logging
import time
from datetime import datetime, timezone
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
            from utils.lakebase_client import LakebaseClient
            from utils.delta_writer import DeltaWriter
            from utils.alerting import AlertManager

            client = LakebaseClient(workspace_host="", mock_mode=True)
            writer = DeltaWriter(mock_mode=True)
            alerter = AlertManager(mock_mode=True)
            _agent = ProvisioningAgent(client, writer, alerter)
        except Exception as e:
            logger.error(f"Failed to initialize ProvisioningAgent: {e}")
            raise HTTPException(status_code=500, detail="Assessment agent initialization failed")
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

    warnings = result.get("unsupported_extensions", [])

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
        "warnings": warnings,
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
        phases.append({
            "phase": p.phase_number,
            "name": p.name,
            "start_day": cumulative_day,
            "duration_days": p.estimated_days,
            "end_day": cumulative_day + p.estimated_days,
        })
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

    if is_nosql:
        from utils.readiness_scorer import DYNAMODB_FEATURE_SUPPORT, DYNAMODB_FEATURE_WORKAROUNDS
        for feature, status in DYNAMODB_FEATURE_SUPPORT.items():
            workaround = DYNAMODB_FEATURE_WORKAROUNDS.get(feature, "")
            matrix.append({
                "name": feature,
                "version": "",
                "status": status,
                "workaround": workaround,
            })
    else:
        from utils.readiness_scorer import LAKEBASE_SUPPORTED_EXTENSIONS, EXTENSION_WORKAROUNDS
        for ext in db.extensions:
            name = ext.name.lower()
            supported = name in LAKEBASE_SUPPORTED_EXTENSIONS
            workaround = EXTENSION_WORKAROUNDS.get(name, "")
            status = "supported" if supported else ("workaround" if workaround else "unsupported")
            matrix.append({
                "name": ext.name,
                "version": ext.version,
                "status": status,
                "workaround": workaround,
            })

    return {
        "profile_id": profile_id,
        "database": db.name,
        "matrix_type": "feature" if is_nosql else "extension",
        "extensions": sorted(matrix, key=lambda e: (0 if e["status"] == "supported" else 1 if e["status"] == "workaround" else 2, e["name"])),
        "summary": {
            "supported": sum(1 for e in matrix if e["status"] == "supported"),
            "workaround": sum(1 for e in matrix if e["status"] == "workaround"),
            "unsupported": sum(1 for e in matrix if e["status"] == "unsupported"),
        },
    }


@router.get("/regions/{engine}", operation_id="assessment_regions")
def assessment_regions(engine: str):
    """Return available regions for a source engine's cloud provider."""
    from config.pricing import get_regions_for_engine, ENGINE_CLOUD_MAP
    cloud = ENGINE_CLOUD_MAP.get(engine, "aws")
    regions = get_regions_for_engine(engine)
    return {"engine": engine, "cloud": cloud, "regions": regions}


@router.get("/cost-estimate/{profile_id}", operation_id="assessment_cost_estimate")
def assessment_cost_estimate(profile_id: str):
    """Estimate monthly cost: source cloud DB vs Lakebase DBU pricing."""
    from config.pricing import (
        SOURCE_ENGINES,
        LAKEBASE_PRICING,
        PRICING_DISCLAIMER,
        PRICING_VERSION,
        HOURS_PER_MONTH,
        get_source_rates,
        get_lakebase_rates,
    )

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
    src_rates = get_source_rates(engine, region)
    lb_rates = get_lakebase_rates(engine, region)

    workload = profile_obj.workload
    avg_qps = workload.avg_qps if workload else 1000
    avg_connections = workload.connection_count_avg if workload else 50

    cu_estimate = max(1, min(32, avg_connections / 50))

    source_compute = src_rates["compute_per_hour"] * HOURS_PER_MONTH
    source_storage = src_rates["storage_per_gb_month"] * size_gb
    source_io = (
        src_rates["io_per_million"] * (avg_qps * 2_592_000 / 1_000_000)
        if src_rates["io_per_million"]
        else 0
    )
    source_total = source_compute + source_storage + source_io

    lakebase_dbu_per_hour = cu_estimate * 2
    lakebase_compute = lakebase_dbu_per_hour * lb_rates["dbu_rate"] * HOURS_PER_MONTH
    lakebase_storage = lb_rates["storage_dsu_per_gb_month"] * size_gb
    lakebase_total = lakebase_compute + lakebase_storage

    savings_pct = round((1 - lakebase_total / source_total) * 100, 1) if source_total > 0 else 0

    return {
        "profile_id": profile_id,
        "engine": engine,
        "region": region,
        "size_gb": round(size_gb, 1),
        "cu_estimate": round(cu_estimate, 1),
        "pricing_version": PRICING_VERSION,
        "disclaimer": PRICING_DISCLAIMER,
        "source": {
            "label": engine_cfg["label"],
            "instance_ref": engine_cfg["instance_ref"],
            "source_url": engine_cfg["source_url"],
            "compute": round(source_compute, 2),
            "storage": round(source_storage, 2),
            "io": round(source_io, 2),
            "total": round(source_total, 2),
            "rates": {
                "compute_per_hour": src_rates["compute_per_hour"],
                "storage_per_gb_month": src_rates["storage_per_gb_month"],
                "io_per_million": src_rates["io_per_million"],
            },
            "formulas": engine_cfg["formulas"],
        },
        "lakebase": {
            "label": "Databricks Lakebase",
            "source_url": LAKEBASE_PRICING["source_url"],
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _assessment_history.append(entry)
    if len(_assessment_history) > _MAX_HISTORY:
        _assessment_history.pop(0)
