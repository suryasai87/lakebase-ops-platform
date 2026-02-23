import { Chip } from "@mui/material";
import { motion } from "framer-motion";

const statusStyles: Record<string, { color: string; bg: string }> = {
  healthy: { color: "#3FB950", bg: "rgba(63,185,80,0.15)" },
  success: { color: "#3FB950", bg: "rgba(63,185,80,0.15)" },
  STABLE: { color: "#3FB950", bg: "rgba(63,185,80,0.15)" },
  warning: { color: "#D29922", bg: "rgba(210,153,34,0.15)" },
  WARNING: { color: "#D29922", bg: "rgba(210,153,34,0.15)" },
  degraded: { color: "#D29922", bg: "rgba(210,153,34,0.15)" },
  error: { color: "#F85149", bg: "rgba(248,81,73,0.15)" },
  failed: { color: "#F85149", bg: "rgba(248,81,73,0.15)" },
  REGRESSION: { color: "#F85149", bg: "rgba(248,81,73,0.15)" },
};

export default function StatusBadge({ status }: { status: string }) {
  const style = statusStyles[status] || { color: "#8B949E", bg: "rgba(139,148,158,0.15)" };
  return (
    <motion.span
      animate={
        ["error", "failed", "REGRESSION"].includes(status)
          ? { scale: [1, 1.08, 1] }
          : {}
      }
      transition={{ repeat: Infinity, duration: 2 }}
    >
      <Chip
        label={status}
        size="small"
        sx={{
          color: style.color,
          bgcolor: style.bg,
          fontWeight: 600,
          fontSize: "0.75rem",
        }}
      />
    </motion.span>
  );
}
