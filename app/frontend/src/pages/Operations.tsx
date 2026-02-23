import { useState, useEffect, useRef, useCallback } from "react";
import {
  Box,
  Typography,
  Tabs,
  Tab,
  CircularProgress,
  Button,
  Paper,
  LinearProgress,
  Chip,
  Stack,
  Alert,
  Collapse,
} from "@mui/material";
import SyncIcon from "@mui/icons-material/Sync";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import HourglassTopIcon from "@mui/icons-material/HourglassTop";
import DataTable from "../components/DataTable";
import { useApiData } from "../hooks/useApiData";

interface TriggeredJob {
  key: string;
  name: string;
  job_id: number;
  run_id: number;
}

interface RunStatus {
  run_id: number;
  job_id?: number;
  name: string;
  status: string;
  life_cycle_state?: string;
  result_state?: string | null;
  message?: string;
}

interface SyncState {
  phase: "idle" | "triggering" | "running" | "completed" | "failed";
  triggered: TriggeredJob[];
  runs: RunStatus[];
  overall: string;
  errorMsg: string;
}

const statusColor: Record<string, "success" | "error" | "warning" | "info" | "default"> = {
  completed: "success",
  failed: "error",
  running: "warning",
  pending: "info",
  error: "error",
};

const statusIcon: Record<string, React.ReactElement> = {
  completed: <CheckCircleIcon fontSize="small" />,
  failed: <ErrorIcon fontSize="small" />,
  running: <SyncIcon fontSize="small" sx={{ animation: "spin 1s linear infinite", "@keyframes spin": { "0%": { transform: "rotate(0deg)" }, "100%": { transform: "rotate(360deg)" } } }} />,
  pending: <HourglassTopIcon fontSize="small" />,
};

export default function Operations() {
  const [tab, setTab] = useState(0);
  const { data: vacuum, loading: vl, refetch: rvac } = useApiData<any[]>("/api/operations/vacuum?days=7");
  const { data: sync, loading: sl, refetch: rsync } = useApiData<any[]>("/api/operations/sync");
  const { data: branches, loading: bl, refetch: rbranch } = useApiData<any[]>("/api/operations/branches");
  const { data: archival, loading: al, refetch: rarch } = useApiData<any[]>("/api/operations/archival");

  const loading = vl || sl || bl || al;

  // Sync job state
  const [syncState, setSyncState] = useState<SyncState>({
    phase: "idle",
    triggered: [],
    runs: [],
    overall: "",
    errorMsg: "",
  });
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // Poll job status
  const pollStatus = useCallback(async (runIds: number[]) => {
    try {
      const res = await fetch(`/api/jobs/sync/status?run_ids=${runIds.join(",")}`);
      if (!res.ok) throw new Error(`${res.status}`);
      const data = await res.json();
      const overall = data.overall || "unknown";
      const isTerminal = overall === "completed" || overall === "failed";
      setSyncState((prev) => ({
        ...prev,
        runs: data.runs || [],
        overall,
        phase: isTerminal ? (overall as SyncState["phase"]) : "running",
      }));
      if (isTerminal) {
        stopPolling();
        // Refetch table data after sync completes (even partial success refreshes some tables)
        setTimeout(() => { rvac(); rsync(); rbranch(); rarch(); }, 2000);
      }
    } catch (e: any) {
      setSyncState((prev) => ({ ...prev, errorMsg: e.message }));
    }
  }, [stopPolling, rvac, rsync, rbranch, rarch]);

  // Trigger sync
  const handleSync = async () => {
    setSyncState({ phase: "triggering", triggered: [], runs: [], overall: "", errorMsg: "" });
    try {
      const res = await fetch("/api/jobs/sync", { method: "POST" });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();

      if (data.status === "error") {
        setSyncState((prev) => ({ ...prev, phase: "failed", errorMsg: data.error }));
        return;
      }

      const triggered: TriggeredJob[] = data.triggered || [];
      const runIds = triggered.map((t) => t.run_id);

      // If no jobs were triggered, show failure immediately
      if (runIds.length === 0) {
        setSyncState((prev) => ({
          ...prev,
          phase: "failed",
          overall: "failed",
          errorMsg: data.errors?.length
            ? `All ${data.errors.length} job(s) failed to trigger: ${data.errors[0]?.error || "unknown error"}`
            : "No jobs were triggered",
        }));
        return;
      }

      setSyncState((prev) => ({
        ...prev,
        phase: "running",
        triggered,
        runs: triggered.map((t) => ({
          run_id: t.run_id,
          name: t.name,
          status: "pending",
        })),
        overall: "running",
        errorMsg: data.errors?.length
          ? `${data.errors.length} job(s) failed to trigger`
          : "",
      }));

      // Start polling every 3 seconds
      pollRef.current = setInterval(() => pollStatus(runIds), 3000);
      // Immediate first poll
      pollStatus(runIds);
    } catch (e: any) {
      setSyncState((prev) => ({
        ...prev,
        phase: "failed",
        errorMsg: e.message,
      }));
    }
  };

  // Cleanup on unmount
  useEffect(() => stopPolling, [stopPolling]);

  const completedCount = syncState.runs.filter((r) => r.status === "completed").length;
  const totalRuns = syncState.runs.length;
  const progressPct = totalRuns > 0 ? (completedCount / totalRuns) * 100 : 0;

  return (
    <Box>
      <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 2 }}>
        <Typography variant="h4">Operations</Typography>
        <Button
          variant="contained"
          startIcon={
            syncState.phase === "running" || syncState.phase === "triggering" ? (
              <CircularProgress size={18} color="inherit" />
            ) : (
              <SyncIcon />
            )
          }
          onClick={handleSync}
          disabled={syncState.phase === "triggering" || syncState.phase === "running"}
          sx={{ textTransform: "none", fontWeight: 600 }}
        >
          {syncState.phase === "triggering"
            ? "Triggering Jobs..."
            : syncState.phase === "running"
            ? `Syncing (${completedCount}/${totalRuns})`
            : "Sync Tables in Unity Catalog Schema Lakebase_Ops"}
        </Button>
      </Box>

      {/* Sync Progress Panel */}
      <Collapse in={syncState.phase !== "idle"}>
        <Paper sx={{ p: 2, mb: 3, bgcolor: "background.paper", border: "1px solid #30363D" }}>
          <Box sx={{ display: "flex", alignItems: "center", justifyContent: "space-between", mb: 1 }}>
            <Typography variant="subtitle1" fontWeight={600}>
              Job Sync Status
            </Typography>
            <Chip
              label={syncState.phase === "triggering" ? "Triggering" : syncState.overall || syncState.phase}
              color={statusColor[syncState.overall] || statusColor[syncState.phase] || "default"}
              size="small"
              icon={statusIcon[syncState.overall] || statusIcon[syncState.phase]}
            />
          </Box>

          {(syncState.phase === "running" || syncState.phase === "triggering") && (
            <LinearProgress
              variant={syncState.phase === "triggering" ? "indeterminate" : "determinate"}
              value={progressPct}
              sx={{ mb: 2, height: 6, borderRadius: 3 }}
            />
          )}

          {syncState.errorMsg && (
            <Alert severity="error" sx={{ mb: 1 }}>
              {syncState.errorMsg}
            </Alert>
          )}

          {syncState.phase === "completed" && (
            <Alert severity="success" sx={{ mb: 1 }}>
              All {totalRuns} jobs completed successfully. Table data will refresh shortly.
            </Alert>
          )}

          {syncState.runs.length > 0 && (
            <Stack spacing={0.5}>
              {syncState.runs.map((r) => (
                <Box
                  key={r.run_id}
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    py: 0.5,
                    px: 1,
                    borderRadius: 1,
                    bgcolor: "rgba(255,255,255,0.03)",
                  }}
                >
                  <Typography variant="body2">{r.name}</Typography>
                  <Chip
                    label={r.status}
                    color={statusColor[r.status] || "default"}
                    size="small"
                    variant="outlined"
                    icon={statusIcon[r.status]}
                  />
                </Box>
              ))}
            </Stack>
          )}

          {syncState.phase === "completed" || syncState.phase === "failed" ? (
            <Button
              size="small"
              onClick={() => setSyncState({ phase: "idle", triggered: [], runs: [], overall: "", errorMsg: "" })}
              sx={{ mt: 1, textTransform: "none" }}
            >
              Dismiss
            </Button>
          ) : null}
        </Paper>
      </Collapse>

      <Tabs
        value={tab}
        onChange={(_, v) => setTab(v)}
        sx={{ mb: 3, "& .MuiTab-root": { textTransform: "none" } }}
      >
        <Tab label="Vacuum" />
        <Tab label="Sync" />
        <Tab label="Branches" />
        <Tab label="Archival" />
      </Tabs>

      {loading ? (
        <Box sx={{ display: "flex", justifyContent: "center", mt: 5 }}>
          <CircularProgress color="primary" />
        </Box>
      ) : (
        <>
          {tab === 0 && (
            <DataTable
              title="Vacuum Operations (7d)"
              columns={[
                { key: "vacuum_date", label: "Date" },
                { key: "operation_type", label: "Type" },
                { key: "operations", label: "Ops" },
                { key: "successful", label: "OK" },
                { key: "failed", label: "Failed" },
                { key: "avg_duration_s", label: "Avg (s)" },
              ]}
              rows={vacuum || []}
            />
          )}
          {tab === 1 && (
            <DataTable
              title="Sync Status (Latest)"
              columns={[
                { key: "source_table", label: "Source" },
                { key: "target_table", label: "Target" },
                { key: "source_count", label: "Src Count" },
                { key: "target_count", label: "Tgt Count" },
                { key: "count_drift", label: "Drift" },
                { key: "lag_minutes", label: "Lag (min)" },
                { key: "status", label: "Status" },
              ]}
              rows={sync || []}
            />
          )}
          {tab === 2 && (
            <DataTable
              title="Branch Activity (30d)"
              columns={[
                { key: "event_date", label: "Date" },
                { key: "event_type", label: "Event" },
                { key: "events", label: "Count" },
                { key: "unique_branches", label: "Branches" },
              ]}
              rows={branches || []}
            />
          )}
          {tab === 3 && (
            <DataTable
              title="Cold Data Archival"
              columns={[
                { key: "archive_date", label: "Date" },
                { key: "source_table", label: "Table" },
                { key: "total_rows_archived", label: "Rows" },
                { key: "mb_reclaimed", label: "MB Reclaimed" },
                { key: "operations", label: "Ops" },
              ]}
              rows={archival || []}
            />
          )}
        </>
      )}
    </Box>
  );
}
