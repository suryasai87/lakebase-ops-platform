"""Jobs router — trigger LakebaseOps sync jobs and poll run status."""

import logging
from fastapi import APIRouter
from ..services.sql_service import get_client

logger = logging.getLogger("lakebase_ops_app.jobs")
router = APIRouter(prefix="/api/jobs", tags=["jobs"])

# All 7 LakebaseOps job IDs
LAKEBASE_JOBS = {
    "metric_collector": {"job_id": 205010800477517, "name": "Metric Collector"},
    "index_analyzer": {"job_id": 405039178411009, "name": "Index Analyzer"},
    "vacuum_scheduler": {"job_id": 594266613956568, "name": "Vacuum Scheduler"},
    "sync_validator": {"job_id": 462158184008431, "name": "Sync Validator"},
    "branch_manager": {"job_id": 676577590162017, "name": "Branch Manager"},
    "cold_archiver": {"job_id": 120897564762964, "name": "Cold Data Archiver"},
    "cost_tracker": {"job_id": 1114339309161416, "name": "Cost Tracker"},
}


@router.get("/list")
def list_jobs():
    """List all LakebaseOps jobs with their current status."""
    results = []
    try:
        client = get_client()
        for key, info in LAKEBASE_JOBS.items():
            try:
                job = client.jobs.get(info["job_id"])
                results.append({
                    "key": key,
                    "job_id": info["job_id"],
                    "name": info["name"],
                    "status": "configured",
                })
            except Exception:
                results.append({
                    "key": key,
                    "job_id": info["job_id"],
                    "name": info["name"],
                    "status": "not_found",
                })
    except Exception as e:
        logger.error(f"Failed to list jobs: {e}")
        return {"error": str(e), "jobs": []}
    return {"jobs": results}


@router.post("/sync")
def trigger_sync():
    """Trigger all 7 LakebaseOps jobs to refresh Delta tables."""
    triggered = []
    errors = []
    try:
        client = get_client()
        for key, info in LAKEBASE_JOBS.items():
            try:
                run = client.jobs.run_now(info["job_id"])
                triggered.append({
                    "key": key,
                    "name": info["name"],
                    "job_id": info["job_id"],
                    "run_id": run.run_id,
                })
                logger.info(f"Triggered {info['name']}: run_id={run.run_id}")
            except Exception as e:
                errors.append({
                    "key": key,
                    "name": info["name"],
                    "error": str(e),
                })
                logger.warning(f"Failed to trigger {info['name']}: {e}")
    except Exception as e:
        return {"status": "error", "error": str(e), "triggered": [], "errors": []}

    return {
        "status": "triggered",
        "total": len(LAKEBASE_JOBS),
        "triggered_count": len(triggered),
        "error_count": len(errors),
        "triggered": triggered,
        "errors": errors,
    }


@router.get("/sync/status")
def poll_sync_status(run_ids: str = ""):
    """Poll status for multiple run IDs (comma-separated)."""
    if not run_ids:
        return {"runs": [], "overall": "no_runs"}

    id_list = [int(r.strip()) for r in run_ids.split(",") if r.strip()]
    runs = []
    try:
        client = get_client()
        for run_id in id_list:
            try:
                run = client.jobs.get_run(run_id)
                state = run.state
                life_cycle = state.life_cycle_state.value if state and state.life_cycle_state else "UNKNOWN"
                result_state = state.result_state.value if state and state.result_state else None
                state_message = state.state_message if state else ""

                # Map to simple status
                if life_cycle in ("PENDING", "QUEUED", "WAITING_FOR_RETRY"):
                    simple = "pending"
                elif life_cycle in ("RUNNING", "TERMINATING"):
                    simple = "running"
                elif life_cycle == "TERMINATED":
                    simple = "completed" if result_state == "SUCCESS" else "failed"
                elif life_cycle in ("SKIPPED", "INTERNAL_ERROR"):
                    simple = "failed"
                else:
                    simple = "unknown"

                # Find job name from run
                job_id = run.job_id
                job_name = next(
                    (v["name"] for v in LAKEBASE_JOBS.values() if v["job_id"] == job_id),
                    f"Job {job_id}"
                )

                runs.append({
                    "run_id": run_id,
                    "job_id": job_id,
                    "name": job_name,
                    "status": simple,
                    "life_cycle_state": life_cycle,
                    "result_state": result_state,
                    "message": state_message[:200] if state_message else "",
                })
            except Exception as e:
                runs.append({
                    "run_id": run_id,
                    "status": "error",
                    "message": str(e)[:200],
                })
    except Exception as e:
        return {"runs": [], "overall": "error", "error": str(e)}

    # Compute overall status — only terminal when ALL jobs are done
    statuses = [r["status"] for r in runs]
    terminal = {"completed", "failed", "error"}
    all_terminal = all(s in terminal for s in statuses)

    if not all_terminal:
        overall = "running"
    elif all(s == "completed" for s in statuses):
        overall = "completed"
    elif any(s in ("failed", "error") for s in statuses):
        overall = "failed"
    else:
        overall = "unknown"

    return {"runs": runs, "overall": overall}
