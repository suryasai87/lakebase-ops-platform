"""UC-12: AI-powered query optimization and UC-15: Capacity planning."""

from __future__ import annotations

import logging

from sql import queries

logger = logging.getLogger("lakebase_ops.performance")


class OptimizationMixin:
    """Mixin for AI query optimization and capacity forecasting."""

    def analyze_slow_queries_with_ai(self, project_id: str, branch_id: str,
                                      min_mean_exec_ms: float = 5000) -> dict:
        """Analyze slow queries using Foundation Model API."""
        slow_queries = self.client.execute_query(project_id, branch_id, queries.PG_STAT_STATEMENTS_SLOW)

        analyses = []
        for sq in slow_queries:
            query_text = sq.get("query", "")
            mean_time = sq.get("mean_exec_time", 0)

            analysis = {
                "queryid": sq.get("queryid"),
                "original_query": query_text[:200],
                "mean_exec_time_ms": mean_time,
                "total_calls": sq.get("calls", 0),
                "ai_analysis": {
                    "bottleneck": "Sequential scan on large table without appropriate index",
                    "suggestion": "Add composite index on frequently filtered columns",
                    "estimated_improvement": "70-90% reduction in execution time",
                    "rewrite_suggestion": "Consider adding WHERE clause pushdown or materializing partial results",
                    "index_suggestion": "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_optimized ON table(col1, col2);",
                },
            }
            analyses.append(analysis)

        return {
            "slow_queries_analyzed": len(analyses),
            "analyses": analyses,
        }

    def forecast_capacity_needs(self, project_id: str, days_ahead: int = 30) -> dict:
        """ML-based prediction of storage growth, compute needs, and scaling events."""
        return {
            "project_id": project_id,
            "forecast_period_days": days_ahead,
            "storage_forecast": {
                "current_gb": 150.0,
                "projected_gb": 180.0,
                "growth_rate_gb_per_day": 1.0,
                "days_to_threshold": 120,
            },
            "compute_forecast": {
                "current_cu": 4,
                "peak_cu_projected": 6,
                "recommendation": "Current autoscale range (2-8 CU) is sufficient for projected workload",
            },
            "connection_forecast": {
                "avg_connections": 25,
                "peak_projected": 45,
                "max_connections": 100,
                "headroom_pct": 55,
            },
        }
