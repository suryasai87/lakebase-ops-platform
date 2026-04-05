import { Card, CardContent, Typography, Box, Chip, Alert, Tooltip, Link } from "@mui/material";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RechartsTooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
} from "recharts";
import TrendingDownIcon from "@mui/icons-material/TrendingDown";
import TrendingUpIcon from "@mui/icons-material/TrendingUp";
import InfoOutlinedIcon from "@mui/icons-material/InfoOutlined";

interface Rates {
  compute_per_hour?: number;
  storage_per_gb_month?: number;
  io_per_million?: number;
  dbu_rate?: number;
  storage_dsu_per_gb_month?: number;
  dbu_per_hour?: number;
}

interface Formulas {
  compute: string;
  storage: string;
  io?: string;
}

interface CostBreakdown {
  label: string;
  instance_ref?: string;
  source_url?: string;
  compute: number;
  storage: number;
  io?: number;
  total: number;
  rates?: Rates;
  formulas?: Formulas;
}

interface CostEstimateProps {
  source: CostBreakdown;
  lakebase: CostBreakdown;
  savingsPct: number;
  savingsMonthly: number;
  sizeGb: number;
  cuEstimate: number;
  region?: string;
  pricingVersion?: string;
  disclaimer?: string;
}

function fmt(n: number): string {
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function fmtRate(n: number | undefined): string {
  if (n == null) return "-";
  return `$${n.toFixed(3)}`;
}

function FormulaChip({ formula, label }: { formula: string; label: string }) {
  return (
    <Tooltip
      title={
        <Box sx={{ p: 0.5 }}>
          <Typography variant="caption" fontWeight={600}>{label}</Typography>
          <Typography variant="caption" display="block" sx={{ mt: 0.5, fontFamily: "monospace" }}>
            {formula}
          </Typography>
        </Box>
      }
      arrow
      placement="top"
    >
      <InfoOutlinedIcon sx={{ fontSize: 14, color: "#8B949E", cursor: "help", ml: 0.5 }} />
    </Tooltip>
  );
}

export default function CostEstimate({
  source,
  lakebase,
  savingsPct,
  savingsMonthly,
  sizeGb,
  cuEstimate,
  region,
  pricingVersion,
  disclaimer,
}: CostEstimateProps) {
  const chartData = [
    {
      name: source.label,
      Compute: source.compute,
      Storage: source.storage,
      IO: source.io || 0,
    },
    {
      name: "Lakebase",
      Compute: lakebase.compute,
      Storage: lakebase.storage,
      IO: 0,
    },
  ];

  const isSaving = savingsPct > 0;

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            Cost Comparison (Monthly)
          </Typography>
          <Chip
            icon={isSaving ? <TrendingDownIcon /> : <TrendingUpIcon />}
            label={isSaving ? `${savingsPct}% savings` : `${Math.abs(savingsPct)}% increase`}
            size="small"
            color={isSaving ? "success" : "warning"}
          />
          {region && <Chip label={region} size="small" variant="outlined" />}
          {pricingVersion && (
            <Chip label={`rates: ${pricingVersion}`} size="small" variant="outlined" sx={{ opacity: 0.7 }} />
          )}
        </Box>

        {disclaimer && (
          <Alert severity="info" sx={{ mb: 2, py: 0.25, "& .MuiAlert-message": { fontSize: "0.75rem" } }}>
            {disclaimer}
          </Alert>
        )}

        <Box sx={{ display: "flex", gap: 2, mb: 2 }}>
          <Box>
            <Box sx={{ display: "flex", alignItems: "center" }}>
              <Typography variant="caption" color="text.secondary">
                {source.label}
              </Typography>
              {source.formulas?.compute && (
                <FormulaChip formula={source.formulas.compute} label="Source Compute Formula" />
              )}
            </Box>
            <Typography variant="h6" sx={{ color: "#F85149" }}>
              {fmt(source.total)}/mo
            </Typography>
            {source.instance_ref && (
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.65rem" }}>
                Based on {source.instance_ref}
              </Typography>
            )}
          </Box>
          <Box>
            <Box sx={{ display: "flex", alignItems: "center" }}>
              <Typography variant="caption" color="text.secondary">
                Lakebase
              </Typography>
              {lakebase.formulas?.compute && (
                <FormulaChip formula={lakebase.formulas.compute} label="Lakebase Compute Formula" />
              )}
            </Box>
            <Typography variant="h6" sx={{ color: "#3FB950" }}>
              {fmt(lakebase.total)}/mo
            </Typography>
            {lakebase.rates?.dbu_per_hour != null && (
              <Typography variant="caption" color="text.secondary" sx={{ fontSize: "0.65rem" }}>
                ~{lakebase.rates.dbu_per_hour} DBU/hr @ {fmtRate(lakebase.rates.dbu_rate)}/DBU
              </Typography>
            )}
          </Box>
          <Box>
            <Typography variant="caption" color="text.secondary">
              Monthly Savings
            </Typography>
            <Typography variant="h6" sx={{ color: isSaving ? "#3FB950" : "#D29922" }}>
              {fmt(Math.abs(savingsMonthly))}
            </Typography>
          </Box>
        </Box>

        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={chartData} margin={{ top: 5, right: 30, left: 0, bottom: 5 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
            <XAxis dataKey="name" tick={{ fill: "#C9D1D9", fontSize: 12 }} />
            <YAxis
              tick={{ fill: "#8B949E", fontSize: 11 }}
              tickFormatter={(v) => `$${v.toLocaleString()}`}
            />
            <RechartsTooltip
              contentStyle={{ backgroundColor: "#161B22", border: "1px solid #30363D" }}
              labelStyle={{ color: "#C9D1D9" }}
              formatter={(value: number) => [`$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`, ""]}
            />
            <Legend wrapperStyle={{ color: "#8B949E", fontSize: 11 }} />
            <Bar dataKey="Compute" stackId="a" fill="#58A6FF" radius={[0, 0, 0, 0]} />
            <Bar dataKey="Storage" stackId="a" fill="#8B5CF6" />
            <Bar dataKey="IO" stackId="a" fill="#D29922" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>

        {/* Rate details with formula tooltips */}
        <Box sx={{ display: "flex", flexWrap: "wrap", gap: 2, mt: 1.5, pt: 1, borderTop: "1px solid #21262D" }}>
          <Box>
            <Typography variant="caption" color="text.secondary" fontWeight={600}>
              Source Rates
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                Compute: {fmtRate(source.rates?.compute_per_hour)}/hr
              </Typography>
              {source.formulas?.compute && (
                <FormulaChip formula={source.formulas.compute} label="Compute" />
              )}
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                Storage: {fmtRate(source.rates?.storage_per_gb_month)}/GB/mo
              </Typography>
              {source.formulas?.storage && (
                <FormulaChip formula={source.formulas.storage} label="Storage" />
              )}
            </Box>
            {(source.rates?.io_per_million ?? 0) > 0 && (
              <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
                <Typography variant="caption" color="text.secondary">
                  I/O: {fmtRate(source.rates?.io_per_million)}/M reqs
                </Typography>
                {source.formulas?.io && (
                  <FormulaChip formula={source.formulas.io} label="I/O" />
                )}
              </Box>
            )}
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" fontWeight={600}>
              Lakebase Rates
            </Typography>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                DBU: {fmtRate(lakebase.rates?.dbu_rate)}/DBU
              </Typography>
              {lakebase.formulas?.compute && (
                <FormulaChip formula={lakebase.formulas.compute} label="Compute" />
              )}
            </Box>
            <Box sx={{ display: "flex", alignItems: "center", gap: 0.5 }}>
              <Typography variant="caption" color="text.secondary">
                Storage: {fmtRate(lakebase.rates?.storage_dsu_per_gb_month)}/GB/mo
              </Typography>
              {lakebase.formulas?.storage && (
                <FormulaChip formula={lakebase.formulas.storage} label="Storage" />
              )}
            </Box>
          </Box>

          <Box>
            <Typography variant="caption" color="text.secondary" fontWeight={600}>
              Assumptions
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block">
              {sizeGb.toFixed(1)} GB storage, ~{cuEstimate} CU
            </Typography>
            <Typography variant="caption" color="text.secondary" display="block">
              730 hrs/month, on-demand pricing
            </Typography>
          </Box>
        </Box>

        {/* Pricing source links */}
        <Box sx={{ display: "flex", gap: 2, mt: 1 }}>
          {source.source_url && (
            <Link href={source.source_url} target="_blank" rel="noopener" variant="caption" sx={{ fontSize: "0.65rem" }}>
              {source.label} pricing page
            </Link>
          )}
          {lakebase.source_url && (
            <Link href={lakebase.source_url} target="_blank" rel="noopener" variant="caption" sx={{ fontSize: "0.65rem" }}>
              Lakebase pricing page
            </Link>
          )}
        </Box>
      </CardContent>
    </Card>
  );
}
