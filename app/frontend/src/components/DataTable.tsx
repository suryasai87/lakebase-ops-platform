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
  Tooltip,
} from "@mui/material";

const MAX_CELL_CHARS = 120;

interface Column {
  key: string;
  label: string;
  format?: (value: any) => string;
}

interface DataTableProps {
  title: string;
  columns: Column[];
  rows: Record<string, any>[];
  maxHeight?: number;
}

function formatCell(value: any, col: Column): string {
  if (value == null) return "—";
  if (col.format) return col.format(value);
  return String(value);
}

function rowKey(row: Record<string, any>, index: number, columns: Column[]): string | number {
  if (row.id != null) return row.id;
  if (columns.length > 0 && row[columns[0].key] != null) return `${row[columns[0].key]}-${index}`;
  return index;
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
                  <TableRow key={rowKey(row, i, columns)} hover>
                    {columns.map((c) => {
                      const text = formatCell(row[c.key], c);
                      const truncated = text.length > MAX_CELL_CHARS;
                      return (
                        <TableCell key={c.key} sx={{ borderBottom: "1px solid #21262D", maxWidth: 300 }}>
                          {truncated ? (
                            <Tooltip title={text} arrow placement="top-start">
                              <span style={{ cursor: "help" }}>
                                {text.slice(0, MAX_CELL_CHARS)}...
                              </span>
                            </Tooltip>
                          ) : (
                            text
                          )}
                        </TableCell>
                      );
                    })}
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
