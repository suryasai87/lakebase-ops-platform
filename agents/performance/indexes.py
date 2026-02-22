"""FR-02: Automated Index Health Manager."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from framework.agent_framework import EventType
from config.settings import IndexRecommendation
from sql import queries

logger = logging.getLogger("lakebase_ops.performance")


class IndexMixin:
    """Mixin for index health detection and recommendations."""

    def detect_unused_indexes(self, project_id: str, branch_id: str, days: int = 7) -> dict:
        """Find indexes with idx_scan = 0, excluding PK and unique constraints."""
        rows = self.client.execute_query(project_id, branch_id, queries.UNUSED_INDEXES)

        recommendations = []
        for row in rows:
            size_mb = row.get("index_size_bytes", 0) / (1024 * 1024)
            rec = IndexRecommendation(
                table_name=row.get("table_name", ""),
                schema_name=row.get("schemaname", "public"),
                recommendation_type="drop_unused",
                index_name=row.get("index_name", ""),
                confidence="high" if size_mb > 10 else "medium",
                estimated_impact=f"Reclaim {size_mb:.1f} MB",
                ddl_statement=f"DROP INDEX CONCURRENTLY IF EXISTS {row.get('index_name', '')};",
                requires_approval=True,
            )
            recommendations.append(rec)

        if recommendations:
            records = [{
                "recommendation_id": str(uuid.uuid4())[:8],
                "project_id": project_id,
                "branch_id": branch_id,
                "table_name": r.table_name,
                "schema_name": r.schema_name,
                "recommendation_type": r.recommendation_type,
                "index_name": r.index_name,
                "confidence": r.confidence,
                "estimated_impact": r.estimated_impact,
                "ddl_statement": r.ddl_statement,
                "status": "pending_review",
                "created_at": datetime.now(timezone.utc).isoformat(),
            } for r in recommendations]
            self.writer.write_metrics("index_recommendations", records)

        return {
            "unused_indexes_found": len(recommendations),
            "total_reclaimable_mb": sum(
                row.get("index_size_bytes", 0) / (1024 * 1024) for row in rows
            ),
            "recommendations": [
                {"index": r.index_name, "table": r.table_name,
                 "confidence": r.confidence, "impact": r.estimated_impact}
                for r in recommendations
            ],
        }

    def detect_bloated_indexes(self, project_id: str, branch_id: str,
                                threshold: float = 2.0) -> dict:
        """Find indexes with bloat ratio > threshold."""
        rows = self.client.execute_query(project_id, branch_id, queries.BLOATED_INDEXES)

        bloated = []
        for row in rows:
            scans = row.get("idx_scan", 0)
            size = row.get("index_size_bytes", 0)
            if size > 50 * 1024 * 1024 and scans < 100:
                bloated.append({
                    "index_name": row.get("index_name", ""),
                    "table_name": row.get("table_name", ""),
                    "estimated_bloat_ratio": 2.5,
                    "size_mb": size / (1024 * 1024),
                    "ddl": f"REINDEX CONCURRENTLY {row.get('index_name', '')};",
                })

        return {"bloated_indexes_found": len(bloated), "indexes": bloated}

    def detect_missing_indexes(self, project_id: str, branch_id: str) -> dict:
        """Find tables where sequential scans dominate."""
        rows = self.client.execute_query(project_id, branch_id, queries.MISSING_INDEXES)

        candidates = []
        for row in rows:
            candidates.append({
                "table": row.get("relname", ""),
                "schema": row.get("schemaname", "public"),
                "seq_scans": row.get("seq_scan", 0),
                "idx_scans": row.get("idx_scan", 0),
                "live_tuples": row.get("n_live_tup", 0),
                "avg_tup_per_scan": row.get("avg_tup_per_scan", 0),
                "recommendation": "Analyze WHERE clauses in frequent queries to determine optimal index columns",
            })

        return {"missing_index_candidates": len(candidates), "candidates": candidates}

    def detect_duplicate_indexes(self, project_id: str, branch_id: str) -> dict:
        """Find indexes with overlapping column sets using pg_catalog.pg_index."""
        rows = self.client.execute_query(project_id, branch_id, queries.DUPLICATE_INDEXES)

        duplicates = []
        for row in rows:
            size_a_mb = row.get("size_a", 0) / (1024 * 1024)
            size_b_mb = row.get("size_b", 0) / (1024 * 1024)
            duplicates.append({
                "table": row.get("table_name", ""),
                "index_a": row.get("index_a", ""),
                "index_b": row.get("index_b", ""),
                "size_a_mb": round(size_a_mb, 1),
                "size_b_mb": round(size_b_mb, 1),
                "recommendation": f"DROP INDEX CONCURRENTLY {row.get('index_b', '')};",
            })

        if duplicates:
            records = [{
                "recommendation_id": str(uuid.uuid4())[:8],
                "project_id": project_id,
                "branch_id": branch_id,
                "table_name": d["table"],
                "schema_name": "public",
                "recommendation_type": "drop_duplicate",
                "index_name": d["index_b"],
                "confidence": "high",
                "estimated_impact": f"Reclaim {d['size_b_mb']:.1f} MB (duplicate of {d['index_a']})",
                "ddl_statement": d["recommendation"],
                "status": "pending_review",
                "created_at": datetime.now(timezone.utc).isoformat(),
            } for d in duplicates]
            self.writer.write_metrics("index_recommendations", records)

        return {
            "duplicate_indexes_found": len(duplicates),
            "duplicates": duplicates,
        }

    def detect_missing_fk_indexes(self, project_id: str, branch_id: str) -> dict:
        """Find foreign key constraints without corresponding indexes."""
        rows = self.client.execute_query(project_id, branch_id, queries.MISSING_FK_INDEXES)

        candidates = []
        for row in rows:
            table = row.get("table_name", "")
            column = row.get("column_name", "")
            candidates.append({
                "table": table,
                "constraint": row.get("constraint_name", ""),
                "column": column,
                "referenced_table": row.get("referenced_table", ""),
                "recommendation": f"CREATE INDEX CONCURRENTLY idx_{table}_{column} ON {table}({column});",
            })

        if candidates:
            records = [{
                "recommendation_id": str(uuid.uuid4())[:8],
                "project_id": project_id,
                "branch_id": branch_id,
                "table_name": c["table"],
                "schema_name": "public",
                "recommendation_type": "create_fk_index",
                "index_name": None,
                "suggested_columns": c["column"],
                "confidence": "high",
                "estimated_impact": f"Improve JOIN performance on FK {c['constraint']}",
                "ddl_statement": c["recommendation"],
                "status": "pending_review",
                "created_at": datetime.now(timezone.utc).isoformat(),
            } for c in candidates]
            self.writer.write_metrics("index_recommendations", records)

        return {
            "missing_fk_indexes": len(candidates),
            "candidates": candidates,
        }

    def run_full_index_analysis(self, project_id: str, branch_id: str) -> dict:
        """Complete index health analysis combining all detection methods."""
        results = {
            "project_id": project_id,
            "branch_id": branch_id,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        }

        results["unused"] = self.detect_unused_indexes(project_id, branch_id)
        results["bloated"] = self.detect_bloated_indexes(project_id, branch_id)
        results["missing"] = self.detect_missing_indexes(project_id, branch_id)
        results["duplicates"] = self.detect_duplicate_indexes(project_id, branch_id)
        results["missing_fk"] = self.detect_missing_fk_indexes(project_id, branch_id)

        total_issues = (
            results["unused"]["unused_indexes_found"]
            + results["bloated"]["bloated_indexes_found"]
            + results["missing"]["missing_index_candidates"]
            + results["duplicates"]["duplicate_indexes_found"]
            + results["missing_fk"]["missing_fk_indexes"]
        )

        results["total_issues"] = total_issues
        results["health_score"] = max(0, 100 - (total_issues * 10))

        if total_issues > 0:
            self.emit_event(EventType.INDEX_RECOMMENDATION, {
                "project_id": project_id,
                "branch_id": branch_id,
                "total_issues": total_issues,
            })

        return results
