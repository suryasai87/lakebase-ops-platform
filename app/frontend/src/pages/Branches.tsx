import { useState } from "react";
import {
  Box,
  Typography,
  Grid,
  Skeleton,
  Alert,
  Tabs,
  Tab,
  Card,
  CardContent,
  Button,
  TextField,
  MenuItem,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  IconButton,
  Tooltip,
  Chip,
  Stack,
} from "@mui/material";
import { motion } from "framer-motion";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import RestartAltIcon from "@mui/icons-material/RestartAlt";
import TimerIcon from "@mui/icons-material/Timer";
import AccountTreeIcon from "@mui/icons-material/AccountTree";
import StorageIcon from "@mui/icons-material/Storage";
import ScheduleIcon from "@mui/icons-material/Schedule";
import VerifiedIcon from "@mui/icons-material/Verified";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip as RTooltip,
  ResponsiveContainer,
  CartesianGrid,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  Legend,
} from "recharts";
import KPICard from "../components/KPICard";
import DataTable from "../components/DataTable";
import StatusBadge from "../components/StatusBadge";
import { useApiData } from "../hooks/useApiData";

// --- Types ---

interface Branch {
  branch_name: string;
  parent_branch: string;
  ttl_days: number | null;
  created_at: string;
  creator_type: string;
  schema_drift_status: string;
  storage_mb: number;
}

interface BranchObservability {
  age_distribution: { bucket: string; count: number }[];
  storage_per_branch: { branch_name: string; storage_mb: number }[];
  creation_rate: { date: string; created: number; deleted: number }[];
  ttl_compliance: { status: string; count: number }[];
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

const PIE_COLORS = ["#3FB950", "#D29922", "#F85149", "#58A6FF"];

const TOOLTIP_STYLE = {
  contentStyle: { backgroundColor: "#161B22", border: "1px solid #30363D" },
  labelStyle: { color: "#C9D1D9" },
};

// --- Branch Creation Dialog ---

function CreateBranchDialog({
  open,
  onClose,
  onSubmit,
  branches,
}: {
  open: boolean;
  onClose: () => void;
  onSubmit: (name: string, parent: string, ttl: number) => void;
  branches: Branch[];
}) {
  const [name, setName] = useState("");
  const [parent, setParent] = useState("main");
  const [ttl, setTtl] = useState(7);

  const handleSubmit = () => {
    if (!name.trim()) return;
    onSubmit(name.trim(), parent, ttl);
    setName("");
    setParent("main");
    setTtl(7);
    onClose();
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>Create Branch</DialogTitle>
      <DialogContent sx={{ display: "flex", flexDirection: "column", gap: 2, pt: 2 }}>
        <TextField
          label="Branch Name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          fullWidth
          placeholder="feature/my-branch"
          sx={{ mt: 1 }}
        />
        <TextField
          label="Parent Branch"
          select
          value={parent}
          onChange={(e) => setParent(e.target.value)}
          fullWidth
        >
          <MenuItem value="main">main</MenuItem>
          {branches
            .filter((b) => b.branch_name !== "main")
            .map((b) => (
              <MenuItem key={b.branch_name} value={b.branch_name}>
                {b.branch_name}
              </MenuItem>
            ))}
        </TextField>
        <TextField
          label="TTL (days)"
          type="number"
          value={ttl}
          onChange={(e) => setTtl(Math.max(1, parseInt(e.target.value) || 1))}
          fullWidth
          inputProps={{ min: 1, max: 365 }}
          helperText="Branch will be auto-deleted after this many days"
        />
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} sx={{ textTransform: "none" }}>
          Cancel
        </Button>
        <Button
          onClick={handleSubmit}
          variant="contained"
          disabled={!name.trim()}
          sx={{ textTransform: "none" }}
        >
          Create
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// --- Branch Actions ---

function BranchActions({
  branch,
  onDelete,
  onReset,
  onExtendTtl,
}: {
  branch: Branch;
  onDelete: (name: string) => void;
  onReset: (name: string) => void;
  onExtendTtl: (name: string) => void;
}) {
  const isMain = branch.branch_name === "main";

  return (
    <Stack direction="row" spacing={0.5}>
      <Tooltip title="Extend TTL">
        <span>
          <IconButton
            size="small"
            onClick={() => onExtendTtl(branch.branch_name)}
            disabled={isMain}
          >
            <TimerIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Reset branch">
        <span>
          <IconButton
            size="small"
            onClick={() => onReset(branch.branch_name)}
            disabled={isMain}
          >
            <RestartAltIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
      <Tooltip title="Delete branch">
        <span>
          <IconButton
            size="small"
            onClick={() => onDelete(branch.branch_name)}
            disabled={isMain}
            color="error"
          >
            <DeleteIcon fontSize="small" />
          </IconButton>
        </span>
      </Tooltip>
    </Stack>
  );
}

// --- Observability Tab (GAP-018) ---

function ObservabilityTab({ data }: { data: BranchObservability | null }) {
  if (!data) {
    return (
      <Alert severity="info" sx={{ mt: 2 }}>
        No observability data available yet.
      </Alert>
    );
  }

  return (
    <motion.div variants={stagger} initial="hidden" animate="show">
      <Grid container spacing={3}>
        {/* Branch Age Distribution */}
        <Grid item xs={12} md={6}>
          <motion.div variants={item}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" gutterBottom>
                  Branch Age Distribution
                </Typography>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={data.age_distribution}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                    <XAxis dataKey="bucket" tick={{ fill: "#8B949E", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#8B949E", fontSize: 11 }} />
                    <RTooltip {...TOOLTIP_STYLE} />
                    <Bar dataKey="count" fill="#58A6FF" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </motion.div>
        </Grid>

        {/* Storage per Branch */}
        <Grid item xs={12} md={6}>
          <motion.div variants={item}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" gutterBottom>
                  Storage Consumption per Branch (MB)
                </Typography>
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={data.storage_per_branch} layout="vertical">
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                    <XAxis type="number" tick={{ fill: "#8B949E", fontSize: 11 }} />
                    <YAxis
                      dataKey="branch_name"
                      type="category"
                      width={120}
                      tick={{ fill: "#8B949E", fontSize: 11 }}
                    />
                    <RTooltip {...TOOLTIP_STYLE} />
                    <Bar dataKey="storage_mb" fill="#8B5CF6" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </motion.div>
        </Grid>

        {/* Creation / Deletion Rate */}
        <Grid item xs={12} md={6}>
          <motion.div variants={item}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" gutterBottom>
                  Creation / Deletion Rate Over Time
                </Typography>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={data.creation_rate}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#21262D" />
                    <XAxis dataKey="date" tick={{ fill: "#8B949E", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#8B949E", fontSize: 11 }} />
                    <RTooltip {...TOOLTIP_STYLE} />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="created"
                      stroke="#3FB950"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="deleted"
                      stroke="#F85149"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </motion.div>
        </Grid>

        {/* TTL Compliance */}
        <Grid item xs={12} md={6}>
          <motion.div variants={item}>
            <Card>
              <CardContent>
                <Typography variant="subtitle1" gutterBottom>
                  TTL Compliance Status
                </Typography>
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={data.ttl_compliance}
                      dataKey="count"
                      nameKey="status"
                      cx="50%"
                      cy="50%"
                      outerRadius={90}
                      label={({ status, count }) => `${status}: ${count}`}
                    >
                      {data.ttl_compliance.map((_, i) => (
                        <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                      ))}
                    </Pie>
                    <RTooltip {...TOOLTIP_STYLE} />
                    <Legend />
                  </PieChart>
                </ResponsiveContainer>
              </CardContent>
            </Card>
          </motion.div>
        </Grid>
      </Grid>
    </motion.div>
  );
}

// --- Helper: compute age in days ---

function ageDays(createdAt: string): number {
  const created = new Date(createdAt);
  const now = new Date();
  return Math.floor((now.getTime() - created.getTime()) / (1000 * 60 * 60 * 24));
}

// --- Main Component ---

export default function Branches() {
  const [tab, setTab] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);

  const {
    data: branches,
    loading,
    error,
    refetch,
  } = useApiData<Branch[]>("/api/operations/branches/status", { pollInterval: 30000 });

  const { data: observability } = useApiData<BranchObservability>(
    "/api/operations/branches/observability",
    { pollInterval: 60000 }
  );

  // --- Handlers (fire-and-forget POST calls) ---

  const handleCreate = async (name: string, parent: string, ttl: number) => {
    try {
      const res = await fetch("/api/operations/branches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ branch_name: name, parent_branch: parent, ttl_days: ttl }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      refetch();
    } catch (e: any) {
      console.error("Failed to create branch:", e.message);
    }
  };

  const handleDelete = async (name: string) => {
    if (!confirm(`Delete branch "${name}"? This cannot be undone.`)) return;
    try {
      const res = await fetch(`/api/operations/branches/${encodeURIComponent(name)}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error(`${res.status}`);
      refetch();
    } catch (e: any) {
      console.error("Failed to delete branch:", e.message);
    }
  };

  const handleReset = async (name: string) => {
    if (!confirm(`Reset branch "${name}" to its parent?`)) return;
    try {
      const res = await fetch(`/api/operations/branches/${encodeURIComponent(name)}/reset`, {
        method: "POST",
      });
      if (!res.ok) throw new Error(`${res.status}`);
      refetch();
    } catch (e: any) {
      console.error("Failed to reset branch:", e.message);
    }
  };

  const handleExtendTtl = async (name: string) => {
    try {
      const res = await fetch(`/api/operations/branches/${encodeURIComponent(name)}/extend-ttl`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ extend_days: 7 }),
      });
      if (!res.ok) throw new Error(`${res.status}`);
      refetch();
    } catch (e: any) {
      console.error("Failed to extend TTL:", e.message);
    }
  };

  // --- Loading / Error states ---

  if (error) {
    return (
      <Alert severity="error" sx={{ mt: 2 }}>
        Failed to load branch data: {error}
      </Alert>
    );
  }

  if (loading) {
    return (
      <Box>
        <Skeleton variant="text" width={200} height={40} sx={{ mb: 2 }} />
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {Array.from({ length: 4 }).map((_, i) => (
            <Grid item xs={12} sm={6} md={3} key={i}>
              <Skeleton variant="rounded" height={120} />
            </Grid>
          ))}
        </Grid>
        <Skeleton variant="rounded" height={400} />
      </Box>
    );
  }

  const branchList = branches || [];
  const activeBranches = branchList.filter((b) => b.branch_name !== "main");
  const driftCount = branchList.filter((b) => b.schema_drift_status === "drifted").length;
  const expiringSoon = branchList.filter(
    (b) => b.ttl_days !== null && ageDays(b.created_at) >= (b.ttl_days ?? 0) - 2
  ).length;
  const totalStorageMb = branchList.reduce((acc, b) => acc + (b.storage_mb || 0), 0);

  const kpis = [
    {
      title: "Active Branches",
      value: activeBranches.length,
      color: "#58A6FF",
      icon: <AccountTreeIcon />,
    },
    {
      title: "Schema Drift",
      value: driftCount,
      color: driftCount > 0 ? "#F85149" : "#3FB950",
      icon: <VerifiedIcon />,
    },
    {
      title: "Expiring Soon",
      value: expiringSoon,
      color: expiringSoon > 0 ? "#D29922" : "#3FB950",
      icon: <ScheduleIcon />,
    },
    {
      title: "Total Storage (MB)",
      value: totalStorageMb,
      color: "#8B5CF6",
      icon: <StorageIcon />,
    },
  ];

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
        <Typography variant="h4">Branches</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setCreateOpen(true)}
          sx={{ textTransform: "none", fontWeight: 600 }}
        >
          Create Branch
        </Button>
      </Box>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        Lakebase branch management, lifecycle tracking, and observability
      </Typography>

      {/* KPI Cards */}
      <motion.div variants={stagger} initial="hidden" animate="show">
        <Grid container spacing={2} sx={{ mb: 3 }}>
          {kpis.map((k) => (
            <Grid item xs={12} sm={6} md={3} key={k.title}>
              <motion.div variants={item}>
                <KPICard {...k} value={k.value} />
              </motion.div>
            </Grid>
          ))}
        </Grid>
      </motion.div>

      {/* Tabs */}
      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ mb: 3, "& .MuiTab-root": { textTransform: "none" } }}
      >
        <Tab label="Active Branches" />
        <Tab label="Observability" />
      </Tabs>

      {tab === 0 && (
        <Card>
          <CardContent>
            <Typography variant="subtitle1" gutterBottom>
              Active Branches
            </Typography>
            <DataTable
              title=""
              columns={[
                { key: "branch_name", label: "Branch Name" },
                { key: "parent_branch", label: "Parent" },
                { key: "ttl_display", label: "TTL" },
                { key: "age_display", label: "Age" },
                { key: "creator_type", label: "Creator" },
                { key: "schema_drift_display", label: "Schema Drift" },
                { key: "actions_display", label: "Actions" },
              ]}
              rows={branchList.map((b) => ({
                ...b,
                ttl_display: b.ttl_days !== null ? `${b.ttl_days}d` : "No TTL",
                age_display: `${ageDays(b.created_at)}d`,
                schema_drift_display: b.schema_drift_status,
                actions_display: "—",
              }))}
              maxHeight={500}
            />
            {/* Render action buttons in an overlay approach isn't feasible with DataTable,
                so we show a secondary action row */}
            <Box sx={{ mt: 2 }}>
              <Typography variant="caption" color="text.secondary" sx={{ mb: 1, display: "block" }}>
                Branch Actions
              </Typography>
              <Stack direction="row" spacing={1} flexWrap="wrap" useFlexGap>
                {branchList
                  .filter((b) => b.branch_name !== "main")
                  .map((b) => (
                    <Chip
                      key={b.branch_name}
                      label={b.branch_name}
                      size="small"
                      variant="outlined"
                      onDelete={() => handleDelete(b.branch_name)}
                      deleteIcon={<DeleteIcon fontSize="small" />}
                      onClick={() => handleReset(b.branch_name)}
                      icon={<AccountTreeIcon fontSize="small" />}
                      sx={{ "& .MuiChip-deleteIcon": { color: "#F85149" } }}
                    />
                  ))}
              </Stack>
              <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: "block" }}>
                Click chip to reset, click X to delete. Use "Create Branch" to add new.
              </Typography>
            </Box>
          </CardContent>
        </Card>
      )}

      {tab === 1 && <ObservabilityTab data={observability} />}

      {/* Create Branch Dialog */}
      <CreateBranchDialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSubmit={handleCreate}
        branches={branchList}
      />
    </Box>
  );
}
