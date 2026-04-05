import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import AdoptionMetrics from "../pages/AdoptionMetrics";

const MOCK_ADOPTION_DATA = {
  kpis: [
    { name: "mock_classes_created", current_value: 42, previous_value: 35, unit: "", trend: "up" },
    { name: "provisioning_time_min", current_value: 3.5, previous_value: 8.2, unit: "min", trend: "down" },
    { name: "dba_tickets", current_value: 2, previous_value: 12, unit: "", trend: "down" },
    { name: "dev_wait_time_hours", current_value: 0.5, previous_value: 4, unit: "hours", trend: "down" },
    { name: "migration_success_rate", current_value: 98.5, previous_value: 92, unit: "%", trend: "up" },
    { name: "active_branches", current_value: 15, previous_value: 8, unit: "", trend: "up" },
    { name: "ci_cd_integrations", current_value: 6, previous_value: 3, unit: "", trend: "up" },
    { name: "agent_invocations", current_value: 320, previous_value: 180, unit: "", trend: "up" },
    { name: "compliance_score", current_value: 95, previous_value: 88, unit: "%", trend: "up" },
  ],
  trends: [
    {
      sprint: "S1",
      mock_classes_created: 20,
      provisioning_time_min: 12,
      dba_tickets: 15,
      dev_wait_time_hours: 6,
      migration_success_rate: 85,
      active_branches: 5,
      ci_cd_integrations: 1,
      agent_invocations: 50,
      compliance_score: 78,
    },
    {
      sprint: "S2",
      mock_classes_created: 42,
      provisioning_time_min: 3.5,
      dba_tickets: 2,
      dev_wait_time_hours: 0.5,
      migration_success_rate: 98.5,
      active_branches: 15,
      ci_cd_integrations: 6,
      agent_invocations: 320,
      compliance_score: 95,
    },
  ],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(MOCK_ADOPTION_DATA),
    })
  );
});

describe("AdoptionMetrics page", () => {
  it("renders page title after data loads", async () => {
    render(
      <MemoryRouter>
        <AdoptionMetrics />
      </MemoryRouter>
    );
    expect(await screen.findByText("Adoption Metrics")).toBeTruthy();
  });

  it("displays KPI cards with human-readable names", async () => {
    render(
      <MemoryRouter>
        <AdoptionMetrics />
      </MemoryRouter>
    );
    await screen.findByText("Adoption Metrics");
    expect(screen.getByText("mock classes created")).toBeTruthy();
    expect(screen.getByText("dba tickets")).toBeTruthy();
    expect(screen.getByText("compliance score")).toBeTruthy();
  });

  it("shows trend chart section titles", async () => {
    render(
      <MemoryRouter>
        <AdoptionMetrics />
      </MemoryRouter>
    );
    await screen.findByText("Adoption Metrics");
    expect(screen.getByText("Development Velocity")).toBeTruthy();
    expect(screen.getByText("Operational Efficiency")).toBeTruthy();
    expect(screen.getByText("Quality and Compliance")).toBeTruthy();
    expect(screen.getByText("Support and Automation")).toBeTruthy();
  });

  it("shows subtitle description", async () => {
    render(
      <MemoryRouter>
        <AdoptionMetrics />
      </MemoryRouter>
    );
    expect(
      await screen.findByText(/Sprint-over-sprint trends for 9 key performance indicators/)
    ).toBeTruthy();
  });

  it("shows empty trend state when no data", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve({ kpis: [], trends: [] }),
      })
    );
    render(
      <MemoryRouter>
        <AdoptionMetrics />
      </MemoryRouter>
    );
    expect(
      await screen.findByText(/No sprint trend data available yet/)
    ).toBeTruthy();
  });
});
