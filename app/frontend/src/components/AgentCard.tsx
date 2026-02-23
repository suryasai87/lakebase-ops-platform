import {
  Card,
  CardContent,
  Typography,
  Chip,
  Box,
  LinearProgress,
} from "@mui/material";
import { motion } from "framer-motion";

interface Tool {
  name: string;
  module: string;
  schedule: string | null;
  risk: string;
}

interface AgentCardProps {
  name: string;
  description: string;
  tool_count: number;
  color: string;
  tools: Tool[];
}

const riskColor: Record<string, "success" | "warning" | "error"> = {
  low: "success",
  medium: "warning",
  high: "error",
};

export default function AgentCard({
  name,
  description,
  tool_count,
  color,
  tools,
}: AgentCardProps) {
  const scheduled = tools.filter((t) => t.schedule).length;
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -4 }}
      transition={{ type: "spring", stiffness: 300 }}
    >
      <Card sx={{ height: "100%", borderTop: `3px solid ${color}` }}>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            {name}
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            {description}
          </Typography>

          <Box sx={{ display: "flex", gap: 1, mb: 2, flexWrap: "wrap" }}>
            <Chip label={`${tool_count} tools`} size="small" sx={{ bgcolor: color, color: "#fff" }} />
            <Chip label={`${scheduled} scheduled`} size="small" variant="outlined" />
          </Box>

          <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: "block" }}>
            Tools
          </Typography>
          <Box sx={{ maxHeight: 200, overflow: "auto" }}>
            {tools.map((t) => (
              <Box
                key={t.name}
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                  py: 0.5,
                  borderBottom: "1px solid #21262D",
                }}
              >
                <Typography variant="caption" sx={{ fontFamily: "monospace" }}>
                  {t.name}
                </Typography>
                <Chip
                  label={t.risk}
                  size="small"
                  color={riskColor[t.risk] || "default"}
                  sx={{ height: 20, fontSize: "0.65rem" }}
                />
              </Box>
            ))}
          </Box>

          <Box sx={{ mt: 2 }}>
            <LinearProgress
              variant="determinate"
              value={(scheduled / tool_count) * 100}
              sx={{
                bgcolor: "#21262D",
                "& .MuiLinearProgress-bar": { bgcolor: color },
              }}
            />
            <Typography variant="caption" color="text.secondary">
              {scheduled}/{tool_count} automated
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </motion.div>
  );
}
