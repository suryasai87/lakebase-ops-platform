import { Card, CardContent, Typography } from "@mui/material";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface MetricsChartProps {
  title: string;
  data: Record<string, any>[];
  dataKey: string;
  color?: string;
  height?: number;
}

export default function MetricsChart({
  title,
  data,
  dataKey,
  color = "#58A6FF",
  height = 250,
}: MetricsChartProps) {
  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle1" gutterBottom>
          {title}
        </Typography>
        <ResponsiveContainer width="100%" height={height}>
          <AreaChart data={data}>
            <defs>
              <linearGradient id={`grad-${dataKey}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={color} stopOpacity={0.3} />
                <stop offset="100%" stopColor={color} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
            <XAxis
              dataKey="hour"
              tick={{ fill: "#8B949E", fontSize: 11 }}
              tickFormatter={(v) => {
                try { return new Date(v).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }); }
                catch { return v; }
              }}
            />
            <YAxis tick={{ fill: "#8B949E", fontSize: 11 }} />
            <Tooltip
              contentStyle={{ backgroundColor: "#161B22", border: "1px solid #30363D" }}
              labelStyle={{ color: "#C9D1D9" }}
            />
            <Area
              type="monotone"
              dataKey={dataKey}
              stroke={color}
              fill={`url(#grad-${dataKey})`}
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
