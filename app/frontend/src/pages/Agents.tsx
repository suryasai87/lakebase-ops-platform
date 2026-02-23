import { Grid, Typography, Box, CircularProgress } from "@mui/material";
import AgentCard from "../components/AgentCard";
import { useApiData } from "../hooks/useApiData";

export default function Agents() {
  const { data: agents, loading } = useApiData<any[]>("/api/agents/summary");

  if (loading) {
    return (
      <Box sx={{ display: "flex", justifyContent: "center", mt: 10 }}>
        <CircularProgress color="primary" />
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" gutterBottom>
        AI Agents
      </Typography>
      <Typography variant="body2" color="text.secondary" sx={{ mb: 3 }}>
        3 specialized agents managing the full Lakebase lifecycle
      </Typography>
      <Grid container spacing={3}>
        {(agents || []).map((agent: any) => (
          <Grid item xs={12} md={4} key={agent.name}>
            <AgentCard {...agent} />
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
