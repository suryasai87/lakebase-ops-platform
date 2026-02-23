import { useState } from "react";
import { Box, Typography, Tabs, Tab, CircularProgress } from "@mui/material";
import DataTable from "../components/DataTable";
import { useApiData } from "../hooks/useApiData";

export default function Operations() {
  const [tab, setTab] = useState(0);
  const { data: vacuum, loading: vl } = useApiData<any[]>("/api/operations/vacuum?days=7");
  const { data: sync, loading: sl } = useApiData<any[]>("/api/operations/sync");
  const { data: branches, loading: bl } = useApiData<any[]>("/api/operations/branches");
  const { data: archival, loading: al } = useApiData<any[]>("/api/operations/archival");

  const loading = vl || sl || bl || al;

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        Operations
      </Typography>
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
