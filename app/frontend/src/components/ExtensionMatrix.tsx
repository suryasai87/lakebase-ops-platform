import {
  Card,
  CardContent,
  Typography,
  Box,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
} from "@mui/material";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import WarningIcon from "@mui/icons-material/Warning";
import CancelIcon from "@mui/icons-material/Cancel";

interface Extension {
  name: string;
  version: string;
  status: "supported" | "workaround" | "unsupported";
  workaround: string;
}

interface Summary {
  supported: number;
  workaround: number;
  unsupported: number;
}

interface ExtensionMatrixProps {
  extensions: Extension[];
  summary: Summary;
  database: string;
  matrixType?: "extension" | "feature";
}

function statusIcon(status: string) {
  switch (status) {
    case "supported":
      return <CheckCircleIcon sx={{ color: "#3FB950", fontSize: 18 }} />;
    case "workaround":
      return <WarningIcon sx={{ color: "#D29922", fontSize: 18 }} />;
    default:
      return <CancelIcon sx={{ color: "#F85149", fontSize: 18 }} />;
  }
}

function statusColor(status: string): "success" | "warning" | "error" {
  if (status === "supported") return "success";
  if (status === "workaround") return "warning";
  return "error";
}

export default function ExtensionMatrix({ extensions, summary, database, matrixType = "extension" }: ExtensionMatrixProps) {
  const total = summary.supported + summary.workaround + summary.unsupported;
  const title = matrixType === "feature" ? "Feature Compatibility" : "Extension Compatibility";

  return (
    <Card>
      <CardContent>
        <Box sx={{ display: "flex", alignItems: "center", gap: 1, mb: 1 }}>
          <Typography variant="subtitle1" fontWeight={600}>
            {title}
          </Typography>
          <Chip label={`${total} total`} size="small" variant="outlined" />
        </Box>

        <Box sx={{ display: "flex", gap: 1, mb: 2 }}>
          <Chip
            icon={<CheckCircleIcon />}
            label={`${summary.supported} supported`}
            size="small"
            color="success"
            variant="outlined"
          />
          <Chip
            icon={<WarningIcon />}
            label={`${summary.workaround} workaround`}
            size="small"
            color="warning"
            variant="outlined"
          />
          <Chip
            icon={<CancelIcon />}
            label={`${summary.unsupported} unsupported`}
            size="small"
            color="error"
            variant="outlined"
          />
        </Box>

        <TableContainer sx={{ maxHeight: 320 }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                <TableCell sx={{ bgcolor: "#0D1117", fontWeight: 600, borderBottom: "1px solid #30363D", width: 40 }}>
                  Status
                </TableCell>
                <TableCell sx={{ bgcolor: "#0D1117", fontWeight: 600, borderBottom: "1px solid #30363D" }}>
                  {matrixType === "feature" ? "Feature" : "Extension"}
                </TableCell>
                <TableCell sx={{ bgcolor: "#0D1117", fontWeight: 600, borderBottom: "1px solid #30363D" }}>
                  Version
                </TableCell>
                <TableCell sx={{ bgcolor: "#0D1117", fontWeight: 600, borderBottom: "1px solid #30363D" }}>
                  Notes
                </TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {extensions.map((ext) => (
                <TableRow key={ext.name} hover>
                  <TableCell sx={{ borderBottom: "1px solid #21262D" }}>
                    {statusIcon(ext.status)}
                  </TableCell>
                  <TableCell sx={{ borderBottom: "1px solid #21262D" }}>
                    <Chip
                      label={ext.name}
                      size="small"
                      color={statusColor(ext.status)}
                      variant="outlined"
                    />
                  </TableCell>
                  <TableCell sx={{ borderBottom: "1px solid #21262D", color: "#8B949E" }}>
                    {ext.version}
                  </TableCell>
                  <TableCell sx={{ borderBottom: "1px solid #21262D", maxWidth: 300 }}>
                    {ext.workaround ? (
                      <Tooltip title={ext.workaround} arrow>
                        <Typography variant="caption" sx={{ cursor: "help" }}>
                          {ext.workaround.length > 80 ? ext.workaround.slice(0, 80) + "..." : ext.workaround}
                        </Typography>
                      </Tooltip>
                    ) : (
                      <Typography variant="caption" color="text.secondary">
                        {ext.status === "supported" ? "Native support" : "Evaluate manually"}
                      </Typography>
                    )}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  );
}
