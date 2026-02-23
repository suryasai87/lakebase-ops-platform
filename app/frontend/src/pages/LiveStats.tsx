import { Box, Typography, Grid, Card, CardContent, CircularProgress, Chip } from "@mui/material";
import { motion } from "framer-motion";
import KPICard from "../components/KPICard";
import SpeedIcon from "@mui/icons-material/Speed";
import StorageIcon from "@mui/icons-material/Storage";
import WarningAmberIcon from "@mui/icons-material/WarningAmber";
import DataTable from "../components/DataTable";
import { useApiData } from "../hooks/useApiData";

export default function LiveStats() {
  const { data, loading, error } = useApiData<any>("/api/lakebase/realtime", {
    pollInterval: 5000,
  });

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 10 }}>
        <CircularProgress color="primary" />
      </Box>
    );
  }

  if (error || data?.error) {
    return (
      <Box sx={{ mt: 4 }}>
        <Typography variant="h4" gutterBottom>
          Live Stats
        </Typography>
        <Card>
          <CardContent>
            <Typography color="error">
              Connection error: {error || data?.error}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
              Direct Lakebase connection required. This works when deployed to Databricks.
            </Typography>
          </CardContent>
        </Card>
      </Box>
    );
  }

  const connStates = data?.connection_states || {};
  const deadTables = data?.top_dead_tuple_tables || [];

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 2, mb: 3 }}>
        <Typography variant="h4">Live Stats</Typography>
        <motion.div
          animate={{ scale: [1, 1.2, 1] }}
          transition={{ repeat: Infinity, duration: 2 }}
        >
          <Chip label="LIVE" color="success" size="small" sx={{ fontWeight: 700 }} />
        </motion.div>
        <Typography variant="caption" color="text.secondary">
          Polling every 5s via direct PG connection
        </Typography>
      </Box>

      <Grid container spacing={2} sx={{ mb: 3 }}>
        <Grid item xs={12} sm={4}>
          <KPICard
            title="Cache Hit Ratio"
            value={data?.cache_hit_ratio ?? 0}
            color="#3FB950"
            icon={<SpeedIcon />}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <KPICard
            title="Active Connections"
            value={data?.connections ?? 0}
            color="#58A6FF"
            icon={<StorageIcon />}
          />
        </Grid>
        <Grid item xs={12} sm={4}>
          <KPICard
            title="Deadlocks"
            value={data?.deadlocks ?? 0}
            color="#F85149"
            icon={<WarningAmberIcon />}
          />
        </Grid>
      </Grid>

      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <Card>
            <CardContent>
              <Typography variant="subtitle1" gutterBottom>
                Connection States
              </Typography>
              {Object.entries(connStates).map(([state, count]) => (
                <Box
                  key={state}
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    py: 0.5,
                    borderBottom: "1px solid #21262D",
                  }}
                >
                  <Typography variant="body2">{state}</Typography>
                  <Typography variant="body2" fontWeight={600}>
                    {count as number}
                  </Typography>
                </Box>
              ))}
              {Object.keys(connStates).length === 0 && (
                <Typography variant="body2" color="text.secondary">
                  No connection data
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} md={6}>
          <DataTable
            title="Top Dead Tuple Tables"
            columns={[
              { key: "table", label: "Table" },
              { key: "dead", label: "Dead Tuples" },
              { key: "live", label: "Live Tuples" },
            ]}
            rows={deadTables}
            maxHeight={300}
          />
        </Grid>
      </Grid>

      <Grid container spacing={2} sx={{ mt: 1 }}>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                WAL Bytes
              </Typography>
              <Typography variant="h5">
                {data?.wal_bytes?.toLocaleString() ?? "—"}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                WAL Buffers Full
              </Typography>
              <Typography variant="h5">
                {data?.wal_buffers_full?.toLocaleString() ?? "—"}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
        <Grid item xs={12} sm={4}>
          <Card>
            <CardContent>
              <Typography variant="body2" color="text.secondary">
                Temp Files
              </Typography>
              <Typography variant="h5">
                {data?.temp_files?.toLocaleString() ?? "—"}
              </Typography>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
}
