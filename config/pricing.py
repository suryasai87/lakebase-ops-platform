"""
Pricing Registry for Migration Cost Estimation

All rates are on-demand / pay-as-you-go list prices sourced from public
pricing pages.  Rates are approximate mid-range estimates for a typical
production instance (e.g. db.r6g.xlarge for Aurora/RDS, 4-vCPU for
Cloud SQL / AlloyDB / Azure, Pro plan for Supabase).

IMPORTANT: These are *estimates* for directional comparison only.
Actual costs depend on instance type, reserved/committed pricing,
I/O patterns, egress, backups, and negotiated discounts.

Sources & last-verified dates are recorded per engine so the numbers
can be audited and refreshed.
"""

from __future__ import annotations

PRICING_VERSION = "2026-03"
PRICING_DISCLAIMER = (
    "Estimates only - based on published on-demand list prices as of "
    f"{PRICING_VERSION}. Actual costs vary by instance type, committed-use "
    "discounts, I/O patterns, backups, and egress. Contact your Databricks "
    "account team for a precise cost comparison."
)

# ── Source Engine Pricing ──────────────────────────────────────────────────
#
# Structure per engine:
#   label            - display name
#   cloud            - aws | gcp | azure | self-managed | multi
#   regions          - dict of region -> rate overrides (or "default")
#   instance_ref     - reference instance used for the estimate
#   source_url       - public pricing page
#   last_verified    - date rates were checked
#
# Rate fields (per region):
#   compute_per_hour - hourly cost for the reference instance
#   storage_per_gb_month - storage $/GB/month
#   io_per_million   - I/O cost per million requests (0 if bundled)
#
# Formulas (returned to frontend for transparency):
#   compute_formula  - human-readable formula
#   storage_formula  - human-readable formula
#   io_formula       - human-readable formula (empty if N/A)

SOURCE_ENGINES: dict[str, dict] = {
    "aurora-postgresql": {
        "label": "Aurora PostgreSQL",
        "cloud": "aws",
        "instance_ref": "db.r6g.xlarge (4 vCPU, 32 GB)",
        "source_url": "https://aws.amazon.com/rds/aurora/pricing/",
        "last_verified": "2026-03",
        "regions": {
            "us-east-1": {"compute_per_hour": 0.48, "storage_per_gb_month": 0.10, "io_per_million": 0.20},
            "us-west-2": {"compute_per_hour": 0.48, "storage_per_gb_month": 0.10, "io_per_million": 0.20},
            "eu-west-1": {"compute_per_hour": 0.53, "storage_per_gb_month": 0.11, "io_per_million": 0.22},
            "ap-southeast-1": {"compute_per_hour": 0.56, "storage_per_gb_month": 0.11, "io_per_million": 0.22},
            "default": {"compute_per_hour": 0.50, "storage_per_gb_month": 0.10, "io_per_million": 0.20},
        },
        "formulas": {
            "compute": "instance_hourly_rate x 730 hrs/month",
            "storage": "storage_gb x storage_rate_per_gb_month",
            "io": "avg_qps x 2,592,000 sec/month / 1,000,000 x io_rate_per_million",
        },
    },
    "rds-postgresql": {
        "label": "RDS PostgreSQL",
        "cloud": "aws",
        "instance_ref": "db.r6g.xlarge (4 vCPU, 32 GB)",
        "source_url": "https://aws.amazon.com/rds/postgresql/pricing/",
        "last_verified": "2026-03",
        "regions": {
            "us-east-1": {"compute_per_hour": 0.48, "storage_per_gb_month": 0.115, "io_per_million": 0.0},
            "us-west-2": {"compute_per_hour": 0.48, "storage_per_gb_month": 0.115, "io_per_million": 0.0},
            "eu-west-1": {"compute_per_hour": 0.53, "storage_per_gb_month": 0.127, "io_per_million": 0.0},
            "ap-southeast-1": {"compute_per_hour": 0.56, "storage_per_gb_month": 0.133, "io_per_million": 0.0},
            "default": {"compute_per_hour": 0.50, "storage_per_gb_month": 0.115, "io_per_million": 0.0},
        },
        "formulas": {
            "compute": "instance_hourly_rate x 730 hrs/month",
            "storage": "storage_gb x gp3_rate_per_gb_month",
            "io": "N/A (included in gp3 storage)",
        },
    },
    "cloud-sql-postgresql": {
        "label": "Cloud SQL for PostgreSQL",
        "cloud": "gcp",
        "instance_ref": "db-custom-4-16384 (4 vCPU, 16 GB)",
        "source_url": "https://cloud.google.com/sql/docs/postgres/pricing",
        "last_verified": "2026-03",
        "regions": {
            "us-central1": {"compute_per_hour": 0.31, "storage_per_gb_month": 0.17, "io_per_million": 0.0},
            "us-east1": {"compute_per_hour": 0.31, "storage_per_gb_month": 0.17, "io_per_million": 0.0},
            "europe-west1": {"compute_per_hour": 0.34, "storage_per_gb_month": 0.19, "io_per_million": 0.0},
            "asia-southeast1": {"compute_per_hour": 0.36, "storage_per_gb_month": 0.20, "io_per_million": 0.0},
            "default": {"compute_per_hour": 0.33, "storage_per_gb_month": 0.17, "io_per_million": 0.0},
        },
        "formulas": {
            "compute": "(vCPU_rate x 4 + memory_rate x 16) x 730 hrs/month",
            "storage": "storage_gb x ssd_rate_per_gb_month",
            "io": "N/A (included in SSD storage)",
        },
    },
    "azure-postgresql": {
        "label": "Azure Flexible Server",
        "cloud": "azure",
        "instance_ref": "D4ds_v5 (4 vCores, 16 GB) General Purpose",
        "source_url": "https://azure.microsoft.com/en-us/pricing/details/postgresql/flexible-server",
        "last_verified": "2026-03",
        "regions": {
            "eastus": {"compute_per_hour": 0.37, "storage_per_gb_month": 0.115, "io_per_million": 0.0},
            "westus2": {"compute_per_hour": 0.37, "storage_per_gb_month": 0.115, "io_per_million": 0.0},
            "westeurope": {"compute_per_hour": 0.42, "storage_per_gb_month": 0.127, "io_per_million": 0.0},
            "southeastasia": {"compute_per_hour": 0.44, "storage_per_gb_month": 0.133, "io_per_million": 0.0},
            "default": {"compute_per_hour": 0.39, "storage_per_gb_month": 0.115, "io_per_million": 0.0},
        },
        "formulas": {
            "compute": "instance_hourly_rate x 730 hrs/month",
            "storage": "storage_gb x premium_ssd_rate_per_gb_month",
            "io": "N/A (included in premium SSD)",
        },
    },
    "alloydb-postgresql": {
        "label": "AlloyDB for PostgreSQL",
        "cloud": "gcp",
        "instance_ref": "4 vCPU, 32 GB (N2 series)",
        "source_url": "https://cloud.google.com/alloydb/pricing",
        "last_verified": "2026-03",
        "regions": {
            "us-central1": {"compute_per_hour": 0.62, "storage_per_gb_month": 0.20, "io_per_million": 0.0},
            "us-east1": {"compute_per_hour": 0.62, "storage_per_gb_month": 0.20, "io_per_million": 0.0},
            "europe-west1": {"compute_per_hour": 0.68, "storage_per_gb_month": 0.22, "io_per_million": 0.0},
            "asia-southeast1": {"compute_per_hour": 0.72, "storage_per_gb_month": 0.23, "io_per_million": 0.0},
            "default": {"compute_per_hour": 0.64, "storage_per_gb_month": 0.20, "io_per_million": 0.0},
        },
        "formulas": {
            "compute": "(vCPU_rate x 4 + memory_rate x 32) x 730 hrs/month",
            "storage": "storage_gb x alloydb_storage_rate_per_gb_month",
            "io": "N/A (included in AlloyDB storage)",
        },
    },
    "supabase-postgresql": {
        "label": "Supabase PostgreSQL",
        "cloud": "multi",
        "instance_ref": "Small compute (2-core ARM, 4 GB)",
        "source_url": "https://supabase.com/docs/guides/platform/compute-and-disk",
        "last_verified": "2026-03",
        "regions": {
            "default": {"compute_per_hour": 0.068, "storage_per_gb_month": 0.125, "io_per_million": 0.0},
        },
        "formulas": {
            "compute": "compute_addon_monthly / 730 x 730 (flat monthly rate)",
            "storage": "storage_gb x $0.125/GB overage rate",
            "io": "N/A (included)",
        },
    },
    "self-managed-postgresql": {
        "label": "Self-Managed PostgreSQL",
        "cloud": "self-managed",
        "instance_ref": "4 vCPU, 32 GB EC2 r6g.xlarge + EBS gp3",
        "source_url": "https://aws.amazon.com/ec2/pricing/on-demand/",
        "last_verified": "2026-03",
        "regions": {
            "us-east-1": {"compute_per_hour": 0.20, "storage_per_gb_month": 0.08, "io_per_million": 0.0},
            "us-west-2": {"compute_per_hour": 0.20, "storage_per_gb_month": 0.08, "io_per_million": 0.0},
            "eu-west-1": {"compute_per_hour": 0.22, "storage_per_gb_month": 0.09, "io_per_million": 0.0},
            "default": {"compute_per_hour": 0.21, "storage_per_gb_month": 0.08, "io_per_million": 0.0},
        },
        "formulas": {
            "compute": "ec2_hourly_rate x 730 hrs/month (excludes DBA labor)",
            "storage": "storage_gb x ebs_gp3_rate_per_gb_month",
            "io": "N/A (included in gp3 baseline)",
        },
    },
    "dynamodb": {
        "label": "Amazon DynamoDB",
        "cloud": "aws",
        "instance_ref": "On-Demand (PAY_PER_REQUEST)",
        "source_url": "https://aws.amazon.com/dynamodb/pricing/on-demand/",
        "last_verified": "2026-03",
        "regions": {
            "us-east-1": {"compute_per_hour": 0.52, "storage_per_gb_month": 0.25, "io_per_million": 0.625},
            "us-west-2": {"compute_per_hour": 0.52, "storage_per_gb_month": 0.25, "io_per_million": 0.625},
            "eu-west-1": {"compute_per_hour": 0.57, "storage_per_gb_month": 0.28, "io_per_million": 0.687},
            "default": {"compute_per_hour": 0.54, "storage_per_gb_month": 0.25, "io_per_million": 0.625},
        },
        "formulas": {
            "compute": "estimated_RCU/s x 2,592,000 sec/month / 1,000,000 x $0.25/million RRU (normalized to hourly equiv)",
            "storage": "storage_gb x $0.25/GB/month",
            "io": "estimated_WCU/s x 2,592,000 sec/month / 1,000,000 x $1.25/million WRU",
        },
    },
}

# ── Lakebase Pricing ───────────────────────────────────────────────────────
#
# Lakebase compute is billed in DBUs via SKUs like
# PREMIUM_DATABASE_SERVERLESS_COMPUTE_US_EAST.  The DBU list price is
# looked up from system.billing.list_prices at runtime in production.
#
# For estimation we use the published Premium tier DBU rate.
# Storage is billed in DSUs with a 10x multiplier on raw GB.

LAKEBASE_PRICING = {
    "source_url": "https://www.databricks.com/product/pricing/lakebase",
    "last_verified": "2026-03",
    "regions": {
        "aws-us-east-1": {"dbu_rate": 0.070, "storage_dsu_per_gb_month": 0.023},
        "aws-us-west-2": {"dbu_rate": 0.070, "storage_dsu_per_gb_month": 0.023},
        "aws-eu-west-1": {"dbu_rate": 0.077, "storage_dsu_per_gb_month": 0.025},
        "aws-ap-southeast-1": {"dbu_rate": 0.082, "storage_dsu_per_gb_month": 0.027},
        "gcp-us-central1": {"dbu_rate": 0.070, "storage_dsu_per_gb_month": 0.023},
        "gcp-us-east1": {"dbu_rate": 0.070, "storage_dsu_per_gb_month": 0.023},
        "gcp-europe-west1": {"dbu_rate": 0.077, "storage_dsu_per_gb_month": 0.025},
        "gcp-asia-southeast1": {"dbu_rate": 0.082, "storage_dsu_per_gb_month": 0.027},
        "azure-eastus": {"dbu_rate": 0.070, "storage_dsu_per_gb_month": 0.023},
        "azure-westus2": {"dbu_rate": 0.070, "storage_dsu_per_gb_month": 0.023},
        "azure-westeurope": {"dbu_rate": 0.077, "storage_dsu_per_gb_month": 0.025},
        "azure-southeastasia": {"dbu_rate": 0.082, "storage_dsu_per_gb_month": 0.027},
        "default": {"dbu_rate": 0.070, "storage_dsu_per_gb_month": 0.023},
    },
    "formulas": {
        "compute": "estimated_CU x 2 DBU/CU x dbu_rate x 730 hrs/month",
        "storage": "storage_gb x dsu_rate_per_gb_month",
    },
}

HOURS_PER_MONTH = 730

# ── Region Mapping ─────────────────────────────────────────────────────────
#
# Maps cloud provider to available regions for the UI dropdown.

CLOUD_REGIONS: dict[str, list[dict[str, str]]] = {
    "aws": [
        {"value": "us-east-1", "label": "US East (N. Virginia)"},
        {"value": "us-west-2", "label": "US West (Oregon)"},
        {"value": "eu-west-1", "label": "Europe (Ireland)"},
        {"value": "ap-southeast-1", "label": "Asia Pacific (Singapore)"},
    ],
    "gcp": [
        {"value": "us-central1", "label": "US Central (Iowa)"},
        {"value": "us-east1", "label": "US East (South Carolina)"},
        {"value": "europe-west1", "label": "Europe West (Belgium)"},
        {"value": "asia-southeast1", "label": "Asia Southeast (Singapore)"},
    ],
    "azure": [
        {"value": "eastus", "label": "East US"},
        {"value": "westus2", "label": "West US 2"},
        {"value": "westeurope", "label": "West Europe"},
        {"value": "southeastasia", "label": "Southeast Asia"},
    ],
    "self-managed": [
        {"value": "us-east-1", "label": "US East (default)"},
        {"value": "us-west-2", "label": "US West"},
        {"value": "eu-west-1", "label": "Europe West"},
    ],
    "multi": [
        {"value": "default", "label": "Global (single rate)"},
    ],
}

ENGINE_CLOUD_MAP: dict[str, str] = {
    "aurora-postgresql": "aws",
    "rds-postgresql": "aws",
    "cloud-sql-postgresql": "gcp",
    "azure-postgresql": "azure",
    "alloydb-postgresql": "gcp",
    "supabase-postgresql": "multi",
    "self-managed-postgresql": "self-managed",
    "dynamodb": "aws",
}

# Lakebase region key prefix by cloud
_LAKEBASE_CLOUD_PREFIX: dict[str, str] = {
    "aws": "aws-",
    "gcp": "gcp-",
    "azure": "azure-",
    "self-managed": "aws-",
    "multi": "aws-",
}


def get_source_rates(engine: str, region: str) -> dict:
    """Look up source engine rates for a given region, falling back to default."""
    engine_cfg = SOURCE_ENGINES.get(engine, SOURCE_ENGINES["aurora-postgresql"])
    regions = engine_cfg["regions"]
    return regions.get(region, regions["default"])


def get_lakebase_rates(engine: str, region: str) -> dict:
    """Look up Lakebase rates for the cloud/region matching the source engine."""
    cloud = ENGINE_CLOUD_MAP.get(engine, "aws")
    prefix = _LAKEBASE_CLOUD_PREFIX.get(cloud, "aws-")
    key = f"{prefix}{region}"
    regions = LAKEBASE_PRICING["regions"]
    return regions.get(key, regions["default"])


def get_regions_for_engine(engine: str) -> list[dict[str, str]]:
    """Return the list of available regions for an engine's cloud provider."""
    cloud = ENGINE_CLOUD_MAP.get(engine, "aws")
    return CLOUD_REGIONS.get(cloud, CLOUD_REGIONS["aws"])
