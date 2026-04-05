import { Box, Typography, Grid, Skeleton, Alert, Card, CardContent } from "@mui/material";
import { motion } from "framer-motion";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import GroupIcon from "@mui/icons-material/Group";
import BugReportIcon from "@mui/icons-material/BugReport";
import AccessTimeIcon from "@mui/icons-material/AccessTime";
import SchoolIcon from "@mui/icons-material/School";
import BuildCircleIcon from "@mui/icons-material/BuildCircle";
import RocketLaunchIcon from "@mui/icons-material/RocketLaunch";
import SupportAgentIcon from "@mui/icons-material/SupportAgent";
import VerifiedIcon from "@mui/icons-material/Verified";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  BarChart,
  Bar,
} from "recharts";
import KPICard from "../components/KPICard";
import { useApiData } from "../hooks/useApiData";

// --- Types ---

interface AdoptionKPI {
  name: string;
  current_value: number;
  previous_value: number;
  unit: string;
  trend: "up" | "down" | "flat";
}

interface SprintTrend {
  sprint: string;
  mock_classes_created: number;
  provisioning_time_min: number;
  dba_tickets: number;
  dev_wait_time_hours: number;
  migration_success_rate: number;
  active_branches: number;
  ci_cd_integrations: number;
  agent_invocations: number;
  compliance_score: number;
}

interface AdoptionData {
  kpis: AdoptionKPI[];
  trends: SprintTrend[];
}

// --- Animation variants ---

const stagger = {
  hidden: {},
  show: { transition: { staggerChildren: 0.08 } },
};
const item = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
};

const TOOLTIP_STYLE = {
  contentStyle: { backgroundColor: "#161B22", border: "1px solid #30363D" },
  labelStyle: { color: "#C9D1D9" },
};

// --- KPI icon/color mapping ---

const KPI_CONFIG: Record<string, { icon: React.ReactNode; color: string }> = {
  mock_classes_created: { icon: <SchoolIcon />, color: "#58A6FF" },
  provisioning_time_min: { icon: <AccessTimeIcon />, color: "#D29922" },
  dba_tickets: { icon: <BugReportIcon />, color: "#F85149" },
  dev_wait_time_hours: { icon: <AccessTimeIcon />, color: "#D29922" },
  migration_success_rate: { icon: <VerifiedIcon />, color: "#3FB950" },
  active_branches: { icon: <BuildCircleIcon />, color: "#8B5CF6" },
  ci_cd_integrations: { icon: <RocketLaunchIcon />, color: "#58A6FF" },
  agent_invocations: { icon: <SupportAgentIcon />, color: "#3FB950" },
  compliance_score: { icon: <VerifiedIcon />, color: "#3FB950" },
};

function trendSuffix(kpi: AdoptionKPI): string {
  if (kpi.unit === "%") return "%";
  if (kpi.unit === "min") return " min";
  if (kpi.unit === "hours") return " hrs";
  return "";
}

function trendDelta(kpi: AdoptionKPI): string {
  const diff = kpi.current_value - kpi.previous_value;
  if (diff === 0) return "flat";
  const pct =
    kpi.previous_value !== 0
      ? ((diff / kpi.previous_value) * 100).toFixed(1)
      : "N/A";
  return diff > 0 ? `+${pct}%` : `${pct}%`;
}

// --- Trend Chart Configs ---

const METRIC_GROUPS = [
  {
    title: "Development Velocity",
    metrics: [
      { key: "mock_classes_created", label: "Mock Classes", color: "#58A6FF" },
      { key: "active_branches", label: "Active Branches", color: "#8B5CF6" },
    ],
  },
  {
    title: "Operational Efficiency",
    metrics: [
      { key: "provisioning_time_min", label: "Provisioning (min)", color: "#D29922" },
      { key: "dev_wait_time_hours", label: "Dev Wait (hrs)", color: "#F85149" },
    ],
  },
  {
    title: "Quality and Compliance",
    metrics: [
      { key: "migration_success_rate", label: "Migration Success %", color: "#3FB950" },
      { key: "compliance_score", label: "Compliance Score", color: "#3FB950" },
    ],
  },
  {
    title: "Support and Automation",
    metrics: [
      { key: "dba_tickets", label: "DBA Tickets", color: "#F85149" },
      { key: "agent_invocations", label: "Agent Invocations", color: "#58A6FF" },
      { key: "ci_cd_integrations", label: "CI/CD Integrations", color: "#8B5CF6" },
    ],
  },
];

export default function AdoptionMetrics() {
  const { data, loading, error } = useApiData<AdoptionData>("/api/metrics/adoption", {
    pollInterval: 120000,
  });

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        Failed to load adoption metrics: {error}
      </Alert>
    );
  }

  if (loading) {
    return (
      <Box>
        <Skeleton variant="text" width={250} height={40} sx={{ mb: 2 }} />
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {Array.from({ length: 9 }).map((_, i) => (
            <Grid item xs={12} sm={6} md={4} lg={3} key={i}>
              <Skeleton variant="rounded" height={120} />
            </Grid>
          ))}
        </Grid>
        <Skeleton variant="rounded" height={300} sx={{ mb: 2 }} />
        <Skeleton variant="rounded" height={300} />
      </Box>
    );
  }

  const kpis = data?.kpis || [];
  const trends = data?.trends || [];

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
        <TrendingUpIcon sx={{ color: "#58A6FF" }} />
        <Typography variant="h4">Adoption Metrics</Typography>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Sprint-over-sprint trends for 9 key performance indicators tracking Lakebase adoption
      </Typography>

      {/* KPI Cards */}
      <motion.div variants={stagger} initial="hidden" animate="show">
        <Grid container spacing={2} sx={{ mb: 4 }}>
          {kpis.map((kpi) => {
            const cfg = KPI_CONFIG[kpi.name] || {
              icon: <GroupIcon />,
              color: "#58A6FF",
            };
            return (
              <Grid item xs={12} sm={6} md={4} lg={3} key={kpi.name}>
                <motion.div variants={item}>
                  <KPICard
                    title={kpi.name.replace(/_/g, " ")}
                    value={kpi.current_value}
                    suffix={trendSuffix(kpi)}
                    color={cfg.color}
                    icon={cfg.icon}
                  />
                  <Typography
                    variant="caption"
                    sx={{
                      mt: 0.5,
                      display: "block",
                      textAlign: "center",
                      color:
                        kpi.trend === "up"
                          ? "#3FB950"
                          : kpi.trend === "down"
                          ? "#F85149"
                          : "#8B949E",
                    }}
                  >
                    {trendDelta(kpi)} vs previous sprint
                  </Typography>
                </motion.div>
              </Grid>
            );
          })}
        </Grid>
      </motion.div>

      {/* Trend Charts */}
      {trends.length > 0 && (
        <motion.div variants={stagger} initial="hidden" animate="show">
          <Grid container spacing={3}>
            {METRIC_GROUPS.map((group) => (
              <Grid item xs={12} md={6} key={group.title}>
                <motion.div variants={item}>
                  <Card>
                    <CardContent>
                      <Typography variant="subtitle1" gutterBottom>
                        {group.title}
                      </Typography>
                      <ResponsiveContainer width="100%" height={250}>
                        {group.metrics.length <= 2 ? (
                          <LineChart data={trends}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                            <XAxis
                              dataKey="sprint"
                              tick={{ fill: "#8B949E", fontSize: 11 }}
                            />
                            <YAxis tick={{ fill: "#8B949E", fontSize: 11 }} />
                            <Tooltip {...TOOLTIP_STYLE} />
                            <Legend />
                            {group.metrics.map((m) => (
                              <Line
                                key={m.key}
                                type="monotone"
                                dataKey={m.key}
                                name={m.label}
                                stroke={m.color}
                                strokeWidth={2}
                                dot={{ r: 3 }}
                              />
                            ))}
                          </LineChart>
                        ) : (
                          <BarChart data={trends}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                            <XAxis
                              dataKey="sprint"
                              tick={{ fill: "#8B949E", fontSize: 11 }}
                            />
                            <YAxis tick={{ fill: "#8B949E", fontSize: 11 }} />
                            <Tooltip {...TOOLTIP_STYLE} />
                            <Legend />
                            {group.metrics.map((m) => (
                              <Bar
                                key={m.key}
                                dataKey={m.key}
                                name={m.label}
                                fill={m.color}
                                radius={[4, 4, 0, 0]}
                              />
                            ))}
                          </BarChart>
                        )}
                      </ResponsiveContainer>
                    </CardContent>
                  </Card>
                </motion.div>
              </Grid>
            ))}
          </Grid>
        </motion.div>
      )}

      {/* Empty state for trends */}
      {trends.length === 0 && (
        <Alert severity="info" sx={{ mt: 2 }}>
          No sprint trend data available yet. Metrics will appear after the first sprint completes.
        </Alert>
      )}
    </Box>
  );
}
