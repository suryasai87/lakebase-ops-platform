import { useState, useCallback, useEffect } from "react";
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  TextField,
  Button,
  Stepper,
  Step,
  StepLabel,
  CircularProgress,
  Alert,
  Chip,
  LinearProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  FormControlLabel,
  Switch,
  Divider,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import StorageIcon from "@mui/icons-material/Storage";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import WarningIcon from "@mui/icons-material/Warning";
import ErrorIcon from "@mui/icons-material/Error";
import HistoryIcon from "@mui/icons-material/History";
import ComputerIcon from "@mui/icons-material/Computer";
import DataTable from "../components/DataTable";
import GanttChart from "../components/GanttChart";
import ExtensionMatrix from "../components/ExtensionMatrix";
import CostEstimate from "../components/CostEstimate";
import { useApiData } from "../hooks/useApiData";

const STEPS = ["Discover", "Profile", "Readiness", "Blueprint"];

const ENGINE_LABELS: Record<string, string> = {
  "aurora-postgresql": "Aurora PG",
  "rds-postgresql": "RDS PG",
  "cloud-sql-postgresql": "Cloud SQL PG",
  "azure-postgresql": "Azure PG",
  "self-managed-postgresql": "Self-Managed PG",
  "alloydb-postgresql": "AlloyDB PG",
  "supabase-postgresql": "Supabase PG",
  "dynamodb": "DynamoDB",
  "cosmosdb-nosql": "Cosmos DB",
};

const NOSQL_ENGINES = new Set(["dynamodb", "cosmosdb-nosql"]);

function severityColor(severity: string): "error" | "warning" | "info" | "success" {
  switch (severity) {
    case "blocker":
      return "error";
    case "high":
      return "warning";
    case "medium":
      return "info";
    default:
      return "success";
  }
}

function scoreColor(score: number): string {
  if (score >= 80) return "#4caf50";
  if (score >= 60) return "#ff9800";
  return "#f44336";
}

export default function Assessment() {
  const [activeStep, setActiveStep] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [mockMode, setMockMode] = useState(true);

  const [form, setForm] = useState({
    endpoint: "",
    database: "",
    source_engine: "aurora-postgresql",
    region: "us-east-1",
    source_user: "",
    source_password: "",
  });

  const [discover, setDiscover] = useState<any>(null);
  const [profile, setProfile] = useState<any>(null);
  const [readiness, setReadiness] = useState<any>(null);
  const [blueprint, setBlueprint] = useState<any>(null);
  const [timeline, setTimeline] = useState<any>(null);
  const [extMatrix, setExtMatrix] = useState<any>(null);
  const [costEstimate, setCostEstimate] = useState<any>(null);
  const [availableRegions, setAvailableRegions] = useState<{value: string; label: string}[]>([]);
  const [tier, setTier] = useState<string>("premium");

  const { data: history, refetch: refetchHistory } = useApiData<any[]>("/api/assessment/history");

  const fetchRegions = useCallback((engine: string) => {
    fetch(`/api/assessment/regions/${engine}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => {
        if (d?.regions) {
          setAvailableRegions(d.regions);
          if (d.regions.length > 0) {
            setForm((prev) => ({ ...prev, region: d.regions[0].value }));
          }
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => { fetchRegions(form.source_engine); }, [form.source_engine, fetchRegions]);

  const callApi = useCallback(
    async (path: string, body: any) => {
      setLoading(true);
      setError(null);
      try {
        const res = await fetch(`/api/assessment/${path}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
        return await res.json();
      } catch (e: any) {
        setError(e.message);
        return null;
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const fetchEnrichments = useCallback(async (profileId: string, selectedTier?: string) => {
    const t = selectedTier || tier;
    const urls = [
      `/api/assessment/timeline/${profileId}`,
      `/api/assessment/extension-matrix/${profileId}`,
      `/api/assessment/cost-estimate/${profileId}?tier=${t}`,
    ];
    const results = await Promise.allSettled(
      urls.map((u) => fetch(u).then((r) => (r.ok ? r.json() : null)))
    );
    if (results[0].status === "fulfilled") setTimeline(results[0].value);
    if (results[1].status === "fulfilled") setExtMatrix(results[1].value);
    if (results[2].status === "fulfilled") setCostEstimate(results[2].value);
  }, [tier]);

  const runDiscover = async () => {
    const result = await callApi("discover", { ...form, mock: mockMode });
    if (result) {
      setDiscover(result);
      setActiveStep(1);
      if (result.profile_id) {
        fetch(`/api/assessment/extension-matrix/${result.profile_id}`)
          .then((r) => (r.ok ? r.json() : null))
          .then((d) => d && setExtMatrix(d));
      }
    }
  };

  const runProfile = async () => {
    const result = await callApi("profile", {
      profile_id: discover?.profile_id,
      mock: mockMode,
      endpoint: form.endpoint,
      database: form.database,
      source_user: form.source_user,
      source_password: form.source_password,
    });
    if (result) {
      setProfile(result);
      setActiveStep(2);
    }
  };

  const runReadiness = async () => {
    const result = await callApi("readiness", {
      profile_id: discover?.profile_id,
      mock: mockMode,
    });
    if (result) {
      setReadiness(result);
      setActiveStep(3);
    }
  };

  const runBlueprint = async () => {
    const result = await callApi("blueprint", {
      profile_id: discover?.profile_id,
      mock: mockMode,
    });
    if (result) {
      setBlueprint(result);
      setActiveStep(4);
      refetchHistory();
      if (discover?.profile_id) {
        fetchEnrichments(discover.profile_id);
      }
    }
  };

  const reset = () => {
    setActiveStep(0);
    setDiscover(null);
    setProfile(null);
    setReadiness(null);
    setBlueprint(null);
    setTimeline(null);
    setExtMatrix(null);
    setCostEstimate(null);
    setError(null);
  };

  const handleTierChange = (_: any, newTier: string | null) => {
    if (newTier && discover?.profile_id) {
      setTier(newTier);
      fetch(`/api/assessment/cost-estimate/${discover.profile_id}?tier=${newTier}`)
        .then((r) => (r.ok ? r.json() : null))
        .then((d) => d && setCostEstimate(d));
    }
  };

  return (
    <Box>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "center", mb: 2 }}>
        <Box>
          <Typography variant="h4" gutterBottom>
            Migration Assessment
          </Typography>
          <Typography variant="body2" color="text.secondary">
            Evaluate external databases for migration to Lakebase
          </Typography>
        </Box>
        <FormControlLabel
          control={<Switch checked={mockMode} onChange={(e) => setMockMode(e.target.checked)} />}
          label="Mock mode"
        />
      </Box>

      <Stepper activeStep={activeStep} sx={{ mb: 4 }}>
        {STEPS.map((label) => (
          <Step key={label}>
            <StepLabel>{label}</StepLabel>
          </Step>
        ))}
      </Stepper>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Connection Form */}
        <Grid item xs={12} md={4}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                <StorageIcon sx={{ mr: 1, verticalAlign: "middle" }} />
                Source Database
              </Typography>
              <TextField
                fullWidth
                label="Endpoint"
                placeholder="aurora-cluster.xxx.us-east-1.rds.amazonaws.com"
                value={form.endpoint}
                onChange={(e) => setForm({ ...form, endpoint: e.target.value })}
                size="small"
                sx={{ mb: 2 }}
                disabled={!mockMode ? false : true}
              />
              <TextField
                fullWidth
                label="Database"
                placeholder="app_production"
                value={form.database}
                onChange={(e) => setForm({ ...form, database: e.target.value })}
                size="small"
                sx={{ mb: 2 }}
              />
              <TextField
                fullWidth
                label="Engine"
                value={form.source_engine}
                onChange={(e) => setForm({ ...form, source_engine: e.target.value })}
                size="small"
                sx={{ mb: 2 }}
                select
                SelectProps={{ native: true }}
              >
                <option value="aurora-postgresql">Aurora PostgreSQL (Standard)</option>
                <option value="aurora-postgresql-io">Aurora PostgreSQL (I/O-Optimized)</option>
                <option value="rds-postgresql">RDS PostgreSQL</option>
                <option value="cloud-sql-postgresql">Cloud SQL PostgreSQL</option>
                <option value="azure-postgresql">Azure PostgreSQL</option>
                <option value="self-managed-postgresql">Self-Managed PostgreSQL</option>
                <option value="alloydb-postgresql">AlloyDB PostgreSQL</option>
                <option value="supabase-postgresql">Supabase PostgreSQL</option>
                <option value="dynamodb">Amazon DynamoDB</option>
                <option value="cosmosdb-nosql">Azure Cosmos DB (NoSQL)</option>
              </TextField>
              <TextField
                fullWidth
                label="Region"
                value={form.region}
                onChange={(e) => setForm({ ...form, region: e.target.value })}
                size="small"
                sx={{ mb: 2 }}
                select
                SelectProps={{ native: true }}
              >
                {availableRegions.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
                {availableRegions.length === 0 && (
                  <option value={form.region}>{form.region}</option>
                )}
              </TextField>
              {!mockMode && (
                <>
                  <TextField
                    fullWidth
                    label="Username"
                    value={form.source_user}
                    onChange={(e) => setForm({ ...form, source_user: e.target.value })}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                  <TextField
                    fullWidth
                    label="Password"
                    type="password"
                    value={form.source_password}
                    onChange={(e) => setForm({ ...form, source_password: e.target.value })}
                    size="small"
                    sx={{ mb: 2 }}
                  />
                </>
              )}
              <Button
                fullWidth
                variant="contained"
                onClick={runDiscover}
                disabled={loading}
                sx={{ mb: 1 }}
              >
                {loading && activeStep === 0 ? <CircularProgress size={20} /> : "1. Discover"}
              </Button>
              <Button
                fullWidth
                variant="contained"
                onClick={runProfile}
                disabled={loading || !discover}
                sx={{ mb: 1 }}
              >
                {loading && activeStep === 1 ? <CircularProgress size={20} /> : "2. Profile"}
              </Button>
              <Button
                fullWidth
                variant="contained"
                onClick={runReadiness}
                disabled={loading || !profile}
                sx={{ mb: 1 }}
              >
                {loading && activeStep === 2 ? <CircularProgress size={20} /> : "3. Readiness"}
              </Button>
              <Button
                fullWidth
                variant="contained"
                onClick={runBlueprint}
                disabled={loading || !readiness}
                sx={{ mb: 1 }}
              >
                {loading && activeStep === 3 ? <CircularProgress size={20} /> : "4. Blueprint"}
              </Button>
              <Divider sx={{ my: 1 }} />
              <Button fullWidth variant="outlined" onClick={reset} size="small">
                Reset
              </Button>
            </CardContent>
          </Card>
        </Grid>

        {/* Results Panel */}
        <Grid item xs={12} md={8}>
          {/* Discovery Results */}
          {discover && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Discovery Results
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      {NOSQL_ENGINES.has(form.source_engine) ? "Account/Region" : "Database"}
                    </Typography>
                    <Typography variant="h6">{discover.database}</Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Size
                    </Typography>
                    <Typography variant="h6">{discover.size_gb} GB</Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Tables
                    </Typography>
                    <Typography variant="h6">{discover.table_count}</Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      {NOSQL_ENGINES.has(form.source_engine) ? "Engine" : "PG Version"}
                    </Typography>
                    <Typography variant="h6">{discover.source_version}</Typography>
                  </Grid>
                </Grid>

                {form.source_engine === "cosmosdb-nosql" ? (
                  <Grid container spacing={2} sx={{ mt: 1 }}>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        Throughput
                      </Typography>
                      <Typography>{discover.cosmos_throughput_mode ?? "N/A"}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        RU/s
                      </Typography>
                      <Typography>{discover.cosmos_ru_per_sec ?? 0}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        Consistency
                      </Typography>
                      <Typography>{discover.cosmos_consistency_level ?? "N/A"}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        Change Feed
                      </Typography>
                      <Typography>{discover.cosmos_change_feed_enabled ? "Yes" : "No"}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        Multi-Region
                      </Typography>
                      <Typography>{discover.cosmos_multi_region_writes ? "Yes" : "No"}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        Regions
                      </Typography>
                      <Typography>{(discover.cosmos_regions || []).length}</Typography>
                    </Grid>
                  </Grid>
                ) : NOSQL_ENGINES.has(form.source_engine) ? (
                  <Grid container spacing={2} sx={{ mt: 1 }}>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        GSIs
                      </Typography>
                      <Typography>{discover.gsi_count ?? 0}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        LSIs
                      </Typography>
                      <Typography>{discover.lsi_count ?? 0}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        Billing
                      </Typography>
                      <Typography>{discover.billing_mode ?? "N/A"}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        Streams
                      </Typography>
                      <Typography>{discover.streams_enabled ? "Yes" : "No"}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        TTL
                      </Typography>
                      <Typography>{discover.ttl_enabled ? "Yes" : "No"}</Typography>
                    </Grid>
                    <Grid item xs={4} sm={2}>
                      <Typography variant="caption" color="text.secondary">
                        PITR
                      </Typography>
                      <Typography>{discover.pitr_enabled ? "Yes" : "No"}</Typography>
                    </Grid>
                  </Grid>
                ) : (
                  <>
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="body2" color="text.secondary" gutterBottom>
                        Extensions
                      </Typography>
                      <Box sx={{ display: "flex", flexWrap: "wrap", gap: 0.5 }}>
                        {(discover.extensions || []).map((ext: string) => (
                          <Chip key={ext} label={ext} size="small" variant="outlined" />
                        ))}
                      </Box>
                    </Box>
                    <Grid container spacing={2} sx={{ mt: 1 }}>
                      <Grid item xs={4} sm={2}>
                        <Typography variant="caption" color="text.secondary">
                          Functions
                        </Typography>
                        <Typography>{discover.function_count}</Typography>
                      </Grid>
                      <Grid item xs={4} sm={2}>
                        <Typography variant="caption" color="text.secondary">
                          Triggers
                        </Typography>
                        <Typography>{discover.trigger_count}</Typography>
                      </Grid>
                      <Grid item xs={4} sm={2}>
                        <Typography variant="caption" color="text.secondary">
                          Sequences
                        </Typography>
                        <Typography>{discover.sequence_count}</Typography>
                      </Grid>
                      <Grid item xs={4} sm={2}>
                        <Typography variant="caption" color="text.secondary">
                          Mat. Views
                        </Typography>
                        <Typography>{discover.materialized_view_count}</Typography>
                      </Grid>
                      <Grid item xs={4} sm={2}>
                        <Typography variant="caption" color="text.secondary">
                          Schemas
                        </Typography>
                        <Typography>{discover.schema_count}</Typography>
                      </Grid>
                      <Grid item xs={4} sm={2}>
                        <Typography variant="caption" color="text.secondary">
                          FKs
                        </Typography>
                        <Typography>{discover.foreign_key_count}</Typography>
                      </Grid>
                    </Grid>
                  </>
                )}
              </CardContent>
            </Card>
          )}

          {/* Workload Profile */}
          {profile && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  Workload Profile
                </Typography>
                <Grid container spacing={2}>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      QPS
                    </Typography>
                    <Typography variant="h6">
                      {profile.qps?.toLocaleString() ?? "N/A"}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      TPS
                    </Typography>
                    <Typography variant="h6">
                      {profile.tps?.toLocaleString() ?? "N/A"}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Connections
                    </Typography>
                    <Typography variant="h6">
                      {profile.active_connections ?? "N/A"}
                    </Typography>
                  </Grid>
                  <Grid item xs={6} sm={3}>
                    <Typography variant="body2" color="text.secondary">
                      Read/Write
                    </Typography>
                    <Typography variant="h6">
                      {profile.read_write_ratio ?? "N/A"}
                    </Typography>
                  </Grid>
                </Grid>
              </CardContent>
            </Card>
          )}

          {/* Readiness Score */}
          {readiness && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Box sx={{ display: "flex", alignItems: "center", mb: 2 }}>
                  <Typography variant="h6" sx={{ flexGrow: 1 }}>
                    Readiness Score
                  </Typography>
                  <Box sx={{ position: "relative", display: "inline-flex" }}>
                    <CircularProgress
                      variant="determinate"
                      value={readiness.overall_score ?? 0}
                      size={80}
                      thickness={6}
                      sx={{ color: scoreColor(readiness.overall_score ?? 0) }}
                    />
                    <Box
                      sx={{
                        top: 0,
                        left: 0,
                        bottom: 0,
                        right: 0,
                        position: "absolute",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                      }}
                    >
                      <Typography variant="h5" fontWeight={700}>
                        {readiness.overall_score ?? 0}
                      </Typography>
                    </Box>
                  </Box>
                </Box>

                <Chip
                  label={readiness.category?.replace(/_/g, " ").toUpperCase() ?? "UNKNOWN"}
                  color={
                    readiness.category === "ready"
                      ? "success"
                      : readiness.category === "ready_with_workarounds"
                      ? "warning"
                      : "error"
                  }
                  sx={{ mb: 2 }}
                />

                {readiness.recommended_tier && (
                  <Typography variant="body2" sx={{ mb: 2 }}>
                    Recommended tier: <strong>{readiness.recommended_tier}</strong>
                    {readiness.recommended_cu && ` (${readiness.recommended_cu} CU)`}
                  </Typography>
                )}

                {/* Dimension Scores */}
                {readiness.dimension_scores && (
                  <Box sx={{ mb: 2 }}>
                    <Typography variant="subtitle2" gutterBottom>
                      Dimension Scores
                    </Typography>
                    {Object.entries(readiness.dimension_scores).map(([dim, score]: [string, any]) => (
                      <Box key={dim} sx={{ mb: 1 }}>
                        <Box sx={{ display: "flex", justifyContent: "space-between" }}>
                          <Typography variant="body2">{dim.replace(/_/g, " ")}</Typography>
                          <Typography variant="body2" fontWeight={600}>
                            {score}%
                          </Typography>
                        </Box>
                        <LinearProgress
                          variant="determinate"
                          value={Number(score)}
                          sx={{
                            height: 6,
                            borderRadius: 3,
                            bgcolor: "rgba(255,255,255,0.1)",
                            "& .MuiLinearProgress-bar": {
                              bgcolor: scoreColor(Number(score)),
                            },
                          }}
                        />
                      </Box>
                    ))}
                  </Box>
                )}

                {/* Blockers */}
                {readiness.blockers && readiness.blockers.length > 0 && (
                  <Accordion defaultExpanded>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <ErrorIcon color="error" sx={{ mr: 1 }} />
                      <Typography>
                        Blockers ({readiness.blockers.length})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      {readiness.blockers.map((b: any, i: number) => (
                        <Alert
                          key={i}
                          severity={severityColor(b.severity)}
                          sx={{ mb: 1 }}
                        >
                          <Typography variant="subtitle2">{b.category}</Typography>
                          <Typography variant="body2">{b.description}</Typography>
                          {b.workaround && (
                            <Typography variant="caption" color="text.secondary">
                              Workaround: {b.workaround}
                            </Typography>
                          )}
                        </Alert>
                      ))}
                    </AccordionDetails>
                  </Accordion>
                )}

                {/* Migration Warnings */}
                {readiness.warnings && readiness.warnings.length > 0 && (
                  <Accordion defaultExpanded>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <WarningIcon color="warning" sx={{ mr: 1 }} />
                      <Typography>
                        Migration Warnings ({readiness.warnings.length})
                      </Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      {readiness.warnings.map((w: string, i: number) => (
                        <Alert
                          key={i}
                          severity={
                            w.toLowerCase().includes("no direct") || w.toLowerCase().includes("requires")
                              ? "warning"
                              : "info"
                          }
                          sx={{ mb: 1 }}
                        >
                          {w}
                        </Alert>
                      ))}
                    </AccordionDetails>
                  </Accordion>
                )}
              </CardContent>
            </Card>
          )}

          {/* Environment Sizing Recommendations */}
          {readiness?.sizing_by_env && readiness.sizing_by_env.length > 0 && (
            <Card sx={{ mb: 2 }}>
              <CardContent>
                <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
                  <ComputerIcon color="primary" />
                  <Typography variant="h6">Environment Sizing</Typography>
                  <ToggleButtonGroup
                    value={tier}
                    exclusive
                    onChange={handleTierChange}
                    size="small"
                    sx={{ ml: "auto" }}
                  >
                    <ToggleButton value="premium">Premium</ToggleButton>
                    <ToggleButton value="enterprise">Enterprise</ToggleButton>
                  </ToggleButtonGroup>
                </Box>
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Environment</TableCell>
                        <TableCell align="right">CU Range</TableCell>
                        <TableCell align="right">RAM</TableCell>
                        <TableCell align="right">Max Connections</TableCell>
                        <TableCell align="center">Scale-to-Zero</TableCell>
                        <TableCell align="center">Autoscaling</TableCell>
                        <TableCell>Notes</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {readiness.sizing_by_env.map((env: any) => (
                        <TableRow key={env.env}>
                          <TableCell>
                            <Chip
                              label={env.env.toUpperCase()}
                              size="small"
                              color={env.env === "prod" ? "error" : env.env === "staging" ? "warning" : "info"}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" fontWeight={600}>
                              {env.cu_min}-{env.cu_max} CU
                            </Typography>
                          </TableCell>
                          <TableCell align="right">{env.ram_gb} GB</TableCell>
                          <TableCell align="right">{env.max_connections?.toLocaleString()}</TableCell>
                          <TableCell align="center">
                            <Chip
                              label={env.scale_to_zero ? "Yes" : "No"}
                              size="small"
                              color={env.scale_to_zero ? "success" : "default"}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell align="center">
                            <Chip
                              label={env.autoscaling ? "Yes" : "No"}
                              size="small"
                              color={env.autoscaling ? "success" : "default"}
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="caption" color="text.secondary">
                              {env.notes}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
                <Alert severity="info" sx={{ mt: 2, py: 0.25, "& .MuiAlert-message": { fontSize: "0.75rem" } }}>
                  1 CU = 2 GB RAM. Autoscaling range max spread: 16 CU. Scale-to-zero reduces idle costs.
                  Contact your Databricks account team for production sizing validation.
                </Alert>
              </CardContent>
            </Card>
          )}

          {/* Blueprint */}
          {blueprint && (
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>
                  <CheckCircleIcon color="success" sx={{ mr: 1, verticalAlign: "middle" }} />
                  Migration Blueprint
                </Typography>

                {blueprint.strategy && (
                  <Chip
                    label={`Strategy: ${blueprint.strategy.replace(/_/g, " ")}`}
                    color="primary"
                    sx={{ mb: 2 }}
                  />
                )}

                {blueprint.total_effort_days && (
                  <Typography variant="body2" sx={{ mb: 2 }}>
                    Estimated effort: <strong>{blueprint.total_effort_days} days</strong>
                  </Typography>
                )}

                {blueprint.phases &&
                  blueprint.phases.map((phase: any, i: number) => (
                    <Accordion key={i}>
                      <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                        <Typography>
                          Phase {i + 1}: {phase.name}
                          {phase.duration_days && (
                            <Chip
                              label={`${phase.duration_days}d`}
                              size="small"
                              sx={{ ml: 1 }}
                            />
                          )}
                        </Typography>
                      </AccordionSummary>
                      <AccordionDetails>
                        <Typography variant="body2" sx={{ mb: 1 }}>
                          {phase.description}
                        </Typography>
                        {phase.steps && (
                          <ul style={{ margin: 0, paddingLeft: 20 }}>
                            {phase.steps.map((step: string, j: number) => (
                              <li key={j}>
                                <Typography variant="body2">{step}</Typography>
                              </li>
                            ))}
                          </ul>
                        )}
                      </AccordionDetails>
                    </Accordion>
                  ))}

                {blueprint.markdown && (
                  <Accordion sx={{ mt: 2 }}>
                    <AccordionSummary expandIcon={<ExpandMoreIcon />}>
                      <Typography>Full Markdown Report</Typography>
                    </AccordionSummary>
                    <AccordionDetails>
                      <Box
                        component="pre"
                        sx={{
                          whiteSpace: "pre-wrap",
                          fontSize: "0.8rem",
                          bgcolor: "rgba(0,0,0,0.3)",
                          p: 2,
                          borderRadius: 1,
                          maxHeight: 400,
                          overflow: "auto",
                        }}
                      >
                        {blueprint.markdown}
                      </Box>
                    </AccordionDetails>
                  </Accordion>
                )}
              </CardContent>
            </Card>
          )}

          {/* Extension Compatibility Matrix (shown after discover) */}
          {extMatrix && extMatrix.extensions && (
            <Box sx={{ mb: 2 }}>
              <ExtensionMatrix
                extensions={extMatrix.extensions}
                summary={extMatrix.summary}
                database={extMatrix.database}
                matrixType={extMatrix.matrix_type || "extension"}
              />
            </Box>
          )}

          {/* Migration Timeline Gantt (shown after blueprint) */}
          {timeline && timeline.phases && (
            <Box sx={{ mb: 2 }}>
              <GanttChart
                phases={timeline.phases}
                totalDays={timeline.total_days}
                strategy={timeline.strategy}
                riskLevel={timeline.risk_level}
              />
            </Box>
          )}

          {/* Cost Comparison (shown after blueprint) */}
          {costEstimate && costEstimate.source && (
            <Box sx={{ mb: 2 }}>
              <CostEstimate
                source={costEstimate.source}
                lakebase={costEstimate.lakebase}
                savingsPct={costEstimate.savings_pct}
                savingsMonthly={costEstimate.savings_monthly}
                sizeGb={costEstimate.size_gb}
                cuEstimate={costEstimate.cu_estimate}
                region={costEstimate.region}
                pricingVersion={costEstimate.pricing_version}
                disclaimer={costEstimate.disclaimer}
                costDisclaimer={costEstimate.cost_disclaimer}
                pricingUrls={costEstimate.pricing_urls}
                pricingSource={costEstimate.pricing_source}
                tierLabel={costEstimate.tier_label}
                skuName={costEstimate.sku_name}
              />
            </Box>
          )}

          {/* Empty state */}
          {!discover && !loading && (
            <Card>
              <CardContent sx={{ textAlign: "center", py: 6 }}>
                <StorageIcon sx={{ fontSize: 48, opacity: 0.3, mb: 2 }} />
                <Typography variant="h6" color="text.secondary">
                  Start a Migration Assessment
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  Configure the source database and click Discover to begin the 4-step assessment pipeline.
                </Typography>
              </CardContent>
            </Card>
          )}
        </Grid>
      </Grid>

      {/* Recent Assessments History */}
      {(history && history.length > 0) && (
        <Card sx={{ mt: 3 }}>
          <CardContent>
            <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 2 }}>
              <HistoryIcon />
              <Typography variant="h6">Recent Assessments</Typography>
            </Box>
            <DataTable
              title=""
              columns={[
                { key: "source_engine", label: "Engine", format: (v: string) => ENGINE_LABELS[v] || v },
                { key: "database", label: "Database" },
                { key: "size_gb", label: "Size (GB)", format: (v: number) => v?.toFixed(1) ?? "-" },
                { key: "overall_score", label: "Score", format: (v: number) => v != null ? `${v}/100` : "-" },
                { key: "category", label: "Category", format: (v: string) => v?.replace(/_/g, " ") ?? "-" },
                { key: "strategy", label: "Strategy", format: (v: string) => v?.replace(/_/g, " ") ?? "-" },
                { key: "risk_level", label: "Risk" },
                { key: "timestamp", label: "Date", format: (v: string) => v ? new Date(v).toLocaleDateString() : "-" },
              ]}
              rows={history}
            />
          </CardContent>
        </Card>
      )}
    </Box>
  );
}
