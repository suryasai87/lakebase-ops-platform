import { Card, CardContent, Typography, Box } from "@mui/material";
import { motion, useMotionValue, useTransform, animate } from "framer-motion";
import { useEffect } from "react";

interface KPICardProps {
  title: string;
  value: number;
  suffix?: string;
  color?: string;
  icon?: React.ReactNode;
}

function AnimatedNumber({ value }: { value: number }) {
  const mv = useMotionValue(0);
  const display = useTransform(mv, (v) =>
    Number.isInteger(value) ? Math.round(v).toLocaleString() : v.toFixed(2)
  );

  useEffect(() => {
    const controls = animate(mv, value, { duration: 1.2, ease: "easeOut" });
    return controls.stop;
  }, [value, mv]);

  return <motion.span>{display}</motion.span>;
}

export default function KPICard({
  title,
  value,
  suffix = "",
  color = "#58A6FF",
  icon,
}: KPICardProps) {
  return (
    <motion.div
      whileHover={{ scale: 1.03, y: -4 }}
      transition={{ type: "spring", stiffness: 300 }}
    >
      <Card sx={{ height: "100%" }}>
        <CardContent>
          <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="body2" color="text.secondary">
              {title}
            </Typography>
            {icon && (
              <Box sx={{ color, opacity: 0.8 }}>{icon}</Box>
            )}
          </Box>
          <Typography variant="h4" sx={{ color, fontWeight: 700 }}>
            <AnimatedNumber value={value} />
            {suffix && (
              <Typography component="span" variant="h6" sx={{ ml: 0.5, opacity: 0.7 }}>
                {suffix}
              </Typography>
            )}
          </Typography>
        </CardContent>
      </Card>
    </motion.div>
  );
}
