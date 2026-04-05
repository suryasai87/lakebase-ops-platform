import { Box, Typography, Button } from "@mui/material";
import { useNavigate } from "react-router-dom";

export default function NotFound() {
  const navigate = useNavigate();

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "60vh",
        textAlign: "center",
      }}
    >
      <Typography variant="h1" sx={{ fontSize: "6rem", fontWeight: 700, color: "text.secondary" }}>
        404
      </Typography>
      <Typography variant="h5" sx={{ mb: 2 }}>
        Page not found
      </Typography>
      <Typography variant="body1" color="text.secondary" sx={{ mb: 4 }}>
        The page you are looking for does not exist or has been moved.
      </Typography>
      <Button variant="contained" onClick={() => navigate("/")}>
        Back to Dashboard
      </Button>
    </Box>
  );
}
