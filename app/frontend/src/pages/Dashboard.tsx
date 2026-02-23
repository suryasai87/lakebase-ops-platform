import { Grid, Typography, Box, CircularProgress } from "@mui/material";
import { motion } from "framer-motion";
import SpeedIcon from "@mui/icons-material/Speed";
import StorageIcon from "@mui/icons-material/Storage";
import SyncIcon from "@mui/icons-material/Sync";
import SecurityIcon from "@mui/icons-material/Security";
import MemoryIcon from "@mui/icons-material/Memory";
import DeleteSweepIcon from "@mui/icons-material/DeleteSweep";
import AccountTreeIcon from "@mui/icons-material/AccountTree";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import KPICard from "../components/KPICard";
import MetricsChart from "../components/MetricsChart";
import { useApiData } from "../hooks/useApiData";

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

export default function Dashboard() {
  const { data: overview, loading } = useApiData<any[]>("/api/metrics/overview", {
    pollInterval: 60000,
  });
  const { data: trend } = useApiData<any[]>(
    "/api/metrics/trends?metric=cache_hit_ratio&hours=24"
  );

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 10 }}>
        <CircularProgress color="primary" />
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
        <Grid item xs={12}>
          <MetricsChart
            title="Cache Hit Ratio (24h)"
            data={trend || []}
            dataKey="avg_value"
            color="#3FB950"
            height={300}
          />
        </Grid>
      </Grid>
    </Box>
  );
}
