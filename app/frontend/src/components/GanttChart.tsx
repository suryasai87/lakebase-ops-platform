import { Card, CardContent, Typography, Box, Chip } from "@mui/material";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  CartesianGrid,
} from "recharts";

interface Phase {
  phase: number;
  name: string;
  start_day: number;
  duration_days: number;
  end_day: number;
}

interface GanttChartProps {
  phases: Phase[];
  totalDays: number;
  strategy: string;
  riskLevel: string;
}

const PHASE_COLORS = ["#58A6FF", "#3FB950", "#D29922", "#F85149"];

function riskColor(risk: string): "success" | "warning" | "error" {
  if (risk === "low") return "success";
  if (risk === "medium") return "warning";
  return "error";
}

export default function GanttChart({ phases, totalDays, strategy, riskLevel }: GanttChartProps) {
  const chartData = phases.map((p) => ({
    name: `P${p.phase}: ${p.name}`,
    start: p.start_day,
    duration: p.duration_days,
    label: `${p.duration_days}d`,
  }));

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Migration Timeline
          </Typography>
          <Chip label={`${totalDays}d total`} size="small" variant="outlined" />
          <Chip label={strategy.replace(/_/g, " ")} size="small" variant="outlined" />
          <Chip label={`${riskLevel} risk`} size="small" color={riskColor(riskLevel)} />
        </Box>

        <ResponsiveContainer width="100%" height={180}>
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 5, right: 30, left: 0, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#21262D" horizontal={false} />
            <XAxis
              type="number"
              domain={[0, Math.ceil(totalDays)]}
              tick={{ fill: "#8B949E", fontSize: 11 }}
              label={{ value: "Days", position: "insideBottomRight", offset: -5, fill: "#8B949E", fontSize: 11 }}
            />
            <YAxis
              type="category"
              dataKey="name"
              width={180}
              tick={{ fill: "#C9D1D9", fontSize: 11 }}
            />
            <Tooltip
              contentStyle={{ backgroundColor: "#161B22", border: "1px solid #30363D" }}
              labelStyle={{ color: "#C9D1D9" }}
              formatter={(value: number, name: string) => {
                if (name === "start") return [`Day ${value}`, "Start"];
                return [`${value} days`, "Duration"];
              }}
            />
            <Bar dataKey="start" stackId="a" fill="transparent" />
            <Bar dataKey="duration" stackId="a" radius={[0, 4, 4, 0]}>
              {chartData.map((_, i) => (
                <Cell key={i} fill={PHASE_COLORS[i % PHASE_COLORS.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
