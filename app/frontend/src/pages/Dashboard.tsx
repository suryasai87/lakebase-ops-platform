import { Grid, Typography, Box, Skeleton, Alert, Card, CardContent, Chip, CircularProgress as MuiCircularProgress, Button } from "@mui/material";
import { motion } from "framer-motion";
import { useNavigate } from "react-router-dom";
import SpeedIcon from "@mui/icons-material/Speed";
import StorageIcon from "@mui/icons-material/Storage";
import SyncIcon from "@mui/icons-material/Sync";
import SecurityIcon from "@mui/icons-material/Security";
import MemoryIcon from "@mui/icons-material/Memory";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import AccountTreeIcon from "@mui/icons-material/AccountTree";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import SwapHorizIcon from "@mui/icons-material/SwapHoriz";
import KPICard from "../components/KPICard";
import MetricsChart from "../components/MetricsChart";
import GanttChart from "../components/GanttChart";
import CostEstimate from "../components/CostEstimate";
import { useApiData } from "../hooks/useApiData";

const ENGINE_LABELS: Record<string, string> = {
  "aurora-postgresql": "Aurora PostgreSQL",
  "rds-postgresql": "RDS PostgreSQL",
  "cloud-sql-postgresql": "Cloud SQL PG",
  "azure-postgresql": "Azure Flexible Server",
  "self-managed-postgresql": "Self-Managed PG",
  "alloydb-postgresql": "AlloyDB PG",
  "supabase-postgresql": "Supabase PG",
};

function scoreColor(score: number): string {
  if (score >= 80) return "#4caf50";
  if (score >= 60) return "#ff9800";
  return "#f44336";
}

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

export default function Dashboard() {
  const navigate = useNavigate();
  const { data: overview, loading, error } = useApiData<any[]>("/api/metrics/overview", {
    pollInterval: 60000,
  });
  const { data: trend } = useApiData<any[]>(
    "/api/metrics/trends?metric=cache_hit_ratio&hours=24"
  );
  const { data: assessmentHistory } = useApiData<any[]>("/api/assessment/history");
  const latestAssessment = assessmentHistory && assessmentHistory.length > 0 ? assessmentHistory[0] : null;
  const latestProfileId = latestAssessment?.profile_id || "";
  const { data: timelineData } = useApiData<any>(
    latestProfileId ? `/api/assessment/timeline/${latestProfileId}` : ""
  );
  const { data: costData } = useApiData<any>(
    latestProfileId ? `/api/assessment/cost-estimate/${latestProfileId}` : ""
  );

  if (error) {
    return <Alert severity="error" sx={{ mt: 2 }}>Failed to load dashboard metrics: {error}</Alert>;
  }

  if (loading) {
    return (
      <Box>
        <Skeleton variant="text" width={200} height={40} sx={{ mb: 2 }} />
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {Array.from({ length: 8 }).map((_, i) => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Skeleton variant="rounded" height={120} />
            </Grid>
          ))}
        </Grid>
        <Skeleton variant="rounded" height={300} />
      </Box>
    );
  }

  // Parse overview metrics into a lookup
  const m: Record<string, number> = {};
  (overview || []).forEach((row: any) => {
    m[row.metric_name] = parseFloat(row.metric_value) || 0;
  });

  const kpis = [
    { title: "Cache Hit Ratio", value: m.cache_hit_ratio ?? 0.99, suffix: "", color: "#3FB950", icon: <SpeedIcon /> },
    { title: "Connections", value: m.active_connections ?? 0, suffix: "", color: "#58A6FF", icon: <StorageIcon /> },
    { title: "Sync Lag (min)", value: m.max_sync_lag_minutes ?? 0, suffix: "min", color: "#D29922", icon: <SyncIcon /> },
    { title: "Deadlocks", value: m.deadlocks ?? 0, suffix: "", color: "#F85149", icon: <SecurityIcon /> },
    { title: "Connection Util %", value: (m.connection_utilization ?? 0) * 100, suffix: "%", color: "#58A6FF", icon: <MemoryIcon /> },
    { title: "Dead Tuple Ratio", value: m.max_dead_tuple_ratio ?? 0, suffix: "", color: "#D29922", icon: <DeleteSweepIcon /> },
    { title: "WAL Bytes", value: m.wal_bytes ?? 0, suffix: "", color: "#8B5CF6", icon: <AccountTreeIcon /> },
    { title: "Temp Files", value: m.temp_files ?? 0, suffix: "", color: "#F85149", icon: <WarningAmberIcon /> },
  ];

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Dashboard
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Real-time overview of LakebaseOps — 3 agents, 47 tools, 7 Delta tables
      </Typography>

      <motion.div variants={stagger} initial="hidden" animate="show">
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {kpis.map((k) => (
            <Grid item xs={12} sm={6} md={3} key={k.title}>
              <motion.div variants={item}>
                <KPICard {...k} />
              </motion.div>
            </Grid>
          ))}
        </Grid>
      </motion.div>

      <Grid container spacing={2}>
        <Grid item xs={12} md={latestAssessment ? 8 : 12}>
          <MetricsChart
            title="Cache Hit Ratio (24h)"
            data={trend || []}
            dataKey="avg_value"
            color="#3FB950"
            height={300}
          />
        </Grid>

        {latestAssessment && (
          <Grid item xs={12} md={4}>
            <Card sx={{ height: "100%" }}>
              <CardContent>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
                  <SwapHorizIcon sx={{ color: "#58A6FF" }} />
                  <Typography variant="subtitle1" fontWeight={600}>
                    Latest Assessment
                  </Typography>
                </Box>

                <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 2 }}>
                  <Box sx={{ position: "relative", display: "inline-flex" }}>
                    <MuiCircularProgress
                      variant="determinate"
                      value={latestAssessment.overall_score ?? 0}
                      size={64}
                      thickness={5}
                      sx={{ color: scoreColor(latestAssessment.overall_score ?? 0) }}
                    />
                    <Box sx={{
                      top: 0, left: 0, bottom: 0, right: 0,
                      position: "absolute", display: "flex",
                      alignItems: "center", justifyContent: "center",
                    }}>
                      <Typography variant="h6" fontWeight={700}>
                        {latestAssessment.overall_score ?? "-"}
                      </Typography>
                    </Box>
                  </Box>
                  <Box>
                    <Chip
                      label={ENGINE_LABELS[latestAssessment.source_engine] || latestAssessment.source_engine}
                      size="small"
                      variant="outlined"
                      sx={{ mb: 0.5 }}
                    />
                    <Typography variant="body2">{latestAssessment.database}</Typography>
                  </Box>
                </Box>

                <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5, mb: 2 }}>
                  <Chip
                    label={latestAssessment.category?.replace(/_/g, " ") ?? "unknown"}
                    size="small"
                    color={
                      latestAssessment.category === "ready" ? "success"
                        : latestAssessment.category === "ready_with_workarounds" ? "warning"
                        : "error"
                    }
                  />
                  <Chip label={`${latestAssessment.risk_level} risk`} size="small" variant="outlined" />
                  {latestAssessment.total_effort_days && (
                    <Chip label={`${latestAssessment.total_effort_days}d effort`} size="small" variant="outlined" />
                  )}
                </Box>

                <Typography variant="caption" color="text.secondary" sx={{ display: "block", mb: 1 }}>
                  {latestAssessment.size_gb?.toFixed(1)} GB
                  {latestAssessment.strategy && ` - ${latestAssessment.strategy.replace(/_/g, " ")}`}
                </Typography>

                <Button
                  size="small"
                  onClick={() => navigate("/assessment")}
                  sx={{ textTransform: "none" }}
                >
                  View Assessment
                </Button>
              </CardContent>
            </Card>
          </Grid>
        )}
      </Grid>

      {/* Migration Enrichment Widgets */}
      {(timelineData?.phases || costData?.source) && (
        <Grid container spacing={2} sx={{ mt: 1 }}>
          {timelineData?.phases && (
            <Grid item xs={12} md={costData?.source ? 6 : 12}>
              <GanttChart
                phases={timelineData.phases}
                totalDays={timelineData.total_days}
                strategy={timelineData.strategy}
                riskLevel={timelineData.risk_level}
              />
            </Grid>
          )}
          {costData?.source && (
            <Grid item xs={12} md={timelineData?.phases ? 6 : 12}>
              <CostEstimate
                source={costData.source}
                lakebase={costData.lakebase}
                savingsPct={costData.savings_pct}
                savingsMonthly={costData.savings_monthly}
                sizeGb={costData.size_gb}
                cuEstimate={costData.cu_estimate}
                region={costData.region}
                pricingVersion={costData.pricing_version}
                disclaimer={costData.disclaimer}
              />
            </Grid>
          )}
        </Grid>
      )}
    </Box>
  );
}
