import {
  Card,
  CardContent,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
} from "@mui/material";

interface DataTableProps {
  title: string;
  columns: { key: string; label: string }[];
  rows: Record<string, any>[];
  maxHeight?: number;
}

export default function DataTable({
  title,
  columns,
  rows,
  maxHeight = 400,
}: DataTableProps) {
  return (
    <Card>
      <CardContent>
        <Typography variant="subtitle1" gutterBottom>
          {title}
        </Typography>
        <TableContainer sx={{ maxHeight }}>
          <Table stickyHeader size="small">
            <TableHead>
              <TableRow>
                {columns.map((c) => (
                  <TableCell
                    key={c.key}
                    sx={{ bgcolor: "#0D1117", fontWeight: 600, borderBottom: "1px solid #30363D" }}
                  >
                    {c.label}
                  </TableCell>
                ))}
              </TableRow>
            </TableHead>
            <TableBody>
              {rows.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={columns.length} align="center" sx={{ color: "text.secondary" }}>
                    No data available
                  </TableCell>
                </TableRow>
              ) : (
                rows.map((row, i) => (
                  <TableRow key={i} hover>
                    {columns.map((c) => (
                      <TableCell key={c.key} sx={{ borderBottom: "1px solid #21262D" }}>
                        {row[c.key] ?? "—"}
                      </TableCell>
                    ))}
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      </CardContent>
    </Card>
  );
}
