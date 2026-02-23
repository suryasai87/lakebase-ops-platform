import { useLocation, useNavigate } from "react-router-dom";
import {
  Drawer,
  List,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Typography,
  Box,
  Divider,
} from "@mui/material";
import DashboardIcon from "@mui/icons-material/Dashboard";
import SmartToyIcon from "@mui/icons-material/SmartToy";
import SpeedIcon from "@mui/icons-material/Speed";
import StorageIcon from "@mui/icons-material/Storage";
import BuildIcon from "@mui/icons-material/Build";
import MonitorHeartIcon from "@mui/icons-material/MonitorHeart";

const NAV = [
  { label: "Dashboard", path: "/", icon: <DashboardIcon /> },
  { label: "Agents", path: "/agents", icon: <SmartToyIcon /> },
  { label: "Performance", path: "/performance", icon: <SpeedIcon /> },
  { label: "Indexes", path: "/indexes", icon: <StorageIcon /> },
  { label: "Operations", path: "/operations", icon: <BuildIcon /> },
  { label: "Live Stats", path: "/live", icon: <MonitorHeartIcon /> },
];

export default function Sidebar({ width }: { width: number }) {
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <Drawer
      variant="permanent"
      sx={{
        width,
        "& .MuiDrawer-paper": {
          width,
          bgcolor: "background.paper",
          borderRight: "1px solid #30363D",
        },
      }}
    >
      <Box sx={{ p: 2, textAlign: "center" }}>
        <Typography variant="h6" color="primary" fontWeight={700}>
          LakebaseOps
        </Typography>
        <Typography variant="caption" color="text.secondary">
          3 Agents &middot; 47 Tools
        </Typography>
      </Box>
      <Divider sx={{ borderColor: "#30363D" }} />
      <List sx={{ px: 1, mt: 1 }}>
        {NAV.map((item) => (
          <ListItemButton
            key={item.path}
            selected={location.pathname === item.path}
            onClick={() => navigate(item.path)}
            sx={{
              borderRadius: 2,
              mb: 0.5,
              "&.Mui-selected": {
                bgcolor: "rgba(255,54,33,0.12)",
                "&:hover": { bgcolor: "rgba(255,54,33,0.18)" },
              },
            }}
          >
            <ListItemIcon sx={{ minWidth: 36, color: "inherit" }}>
              {item.icon}
            </ListItemIcon>
            <ListItemText primary={item.label} />
          </ListItemButton>
        ))}
      </List>
    </Drawer>
  );
}
