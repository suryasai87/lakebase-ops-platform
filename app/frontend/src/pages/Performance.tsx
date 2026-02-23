import { Box, Typography, Grid, CircularProgress } from "@mui/material";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import { useApiData } from "../hooks/useApiData";

export default function Performance() {
  const { data: queries, loading: qLoading } = useApiData<any[]>(
    "/api/performance/queries?hours=24&limit=10"
  );
  const { data: regressions, loading: rLoading } = useApiData<any[]>(
    "/api/performance/regressions"
  );

  if (qLoading || rLoading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 10 }}>
        <CircularProgress color="primary" />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Performance
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Slow query analysis and regression detection
      </Typography>

      <Grid container spacing={3}>
        <Grid item xs={12}>
          <DataTable
            title="Top 10 Slowest Queries (24h)"
            columns={[
              { key: "queryid", label: "Query ID" },
              { key: "total_calls", label: "Calls" },
              { key: "avg_exec_time_ms", label: "Avg (ms)" },
              { key: "total_time_ms", label: "Total (ms)" },
              { key: "total_rows", label: "Rows" },
              { key: "total_read_mb", label: "Read (MB)" },
            ]}
            rows={queries || []}
          />
        </Grid>
        <Grid item xs={12}>
          <DataTable
            title="Regression Detection"
            columns={[
              { key: "queryid", label: "Query ID" },
              { key: "baseline_ms", label: "Baseline (ms)" },
              { key: "recent_ms", label: "Recent (ms)" },
              { key: "pct_change", label: "Change %" },
              { key: "status", label: "Status" },
            ]}
            rows={(regressions || []).map((r: any) => ({
              ...r,
              status: r.status,
            }))}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
