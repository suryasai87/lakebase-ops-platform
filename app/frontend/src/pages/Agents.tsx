import { Grid, Typography, Box, Skeleton, Alert } from "@mui/material";
import AgentCard from "../components/AgentCard";
import { useApiData } from "../hooks/useApiData";

export default function Agents() {
  const { data: agents, loading, error } = useApiData<any[]>("/api/agents/summary");

  if (error) {
    return <Alert severity="error" sx={{ mt: 2 }}>Failed to load agents: {error}</Alert>;
  }

  if (loading) {
    return (
      <Box>
        <Skeleton variant="text" width={200} height={40} sx={{ mb: 2 }} />
        <Grid container spacing={3}>
          {Array.from({ length: 3 }).map((_, i) => (
            <Grid item xs={12} md={4} key={i}>
              <Skeleton variant="rounded" height={200} />
            </Grid>
          ))}
        </Grid>
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
