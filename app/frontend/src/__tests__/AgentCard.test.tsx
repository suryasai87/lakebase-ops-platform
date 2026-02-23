import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import AgentCard from "../components/AgentCard";

const mockAgent = {
  name: "PerformanceAgent",
  description: "Query analysis and indexing",
  tool_count: 14,
  color: "#f57c00",
  tools: [
    { name: "detect_unused_indexes", module: "indexes", schedule: "hourly", risk: "low" },
    { name: "schedule_vacuum_full", module: "maintenance", schedule: null, risk: "high" },
  ],
};

describe("AgentCard", () => {
  it("renders agent name and description", () => {
    render(<AgentCard {...mockAgent} />);
    expect(screen.getByText("PerformanceAgent")).toBeTruthy();
    expect(screen.getByText("Query analysis and indexing")).toBeTruthy();
  });

  it("shows tool count chip", () => {
    render(<AgentCard {...mockAgent} />);
    expect(screen.getByText("14 tools")).toBeTruthy();
  });

  it("shows tool names", () => {
    render(<AgentCard {...mockAgent} />);
    expect(screen.getByText("detect_unused_indexes")).toBeTruthy();
    expect(screen.getByText("schedule_vacuum_full")).toBeTruthy();
  });
});
