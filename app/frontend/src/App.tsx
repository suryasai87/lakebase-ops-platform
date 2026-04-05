import { Routes, Route } from "react-router-dom";
import { Box } from "@mui/material";
import Sidebar from "./components/Sidebar";
import AnimatedLayout from "./components/AnimatedLayout";
import ErrorBoundary from "./components/ErrorBoundary";
import Dashboard from "./pages/Dashboard";
import Agents from "./pages/Agents";
import Performance from "./pages/Performance";
import Indexes from "./pages/Indexes";
import Operations from "./pages/Operations";
import LiveStats from "./pages/LiveStats";
import Assessment from "./pages/Assessment";
import NotFound from "./pages/NotFound";

const DRAWER_WIDTH = 240;

export default function App() {
  return (
    <Box sx={{ display: "flex", minHeight: "100vh" }}>
      <Sidebar width={DRAWER_WIDTH} />
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          ml: `${DRAWER_WIDTH}px`,
          p: 3,
          overflow: "auto",
        }}
      >
        <ErrorBoundary>
          <AnimatedLayout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/agents" element={<Agents />} />
              <Route path="/performance" element={<Performance />} />
              <Route path="/indexes" element={<Indexes />} />
              <Route path="/operations" element={<Operations />} />
              <Route path="/live" element={<LiveStats />} />
              <Route path="/assessment" element={<Assessment />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </AnimatedLayout>
        </ErrorBoundary>
      </Box>
    </Box>
  );
}
