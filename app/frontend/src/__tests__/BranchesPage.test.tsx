import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Branches from "../pages/Branches";

const MOCK_BRANCHES = [
  {
    branch_name: "main",
    parent_branch: "",
    ttl_days: null,
    created_at: "2026-01-01T00:00:00Z",
    creator_type: "system",
    schema_drift_status: "clean",
    storage_mb: 512,
  },
  {
    branch_name: "feature/auth",
    parent_branch: "main",
    ttl_days: 7,
    created_at: "2026-04-01T00:00:00Z",
    creator_type: "human",
    schema_drift_status: "drifted",
    storage_mb: 128,
  },
];

const MOCK_OBSERVABILITY = {
  age_distribution: [{ bucket: "0-7d", count: 3 }],
  storage_per_branch: [{ branch_name: "main", storage_mb: 512 }],
  creation_rate: [{ date: "2026-04-01", created: 2, deleted: 1 }],
  ttl_compliance: [{ status: "compliant", count: 5 }],
};

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation((url: string) => {
      if (url.includes("/observability")) {
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve(MOCK_OBSERVABILITY),
        });
      }
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(MOCK_BRANCHES),
      });
    })
  );
});

describe("Branches page", () => {
  it("renders title after data loads", async () => {
    render(
      <MemoryRouter>
        <Branches />
      </MemoryRouter>
    );
    expect(await screen.findByText("Branches")).toBeTruthy();
  });

  it("displays KPI cards after loading", async () => {
    render(
      <MemoryRouter>
        <Branches />
      </MemoryRouter>
    );
    // Wait for the page to fully render by finding the subtitle
    await screen.findByText(/Lakebase branch management/);
    // KPI titles may also appear in the DataTable headers, use getAllByText
    expect(screen.getAllByText("Schema Drift").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Expiring Soon")).toBeTruthy();
    expect(screen.getByText("Total Storage (MB)")).toBeTruthy();
    expect(screen.getAllByText("Active Branches").length).toBeGreaterThanOrEqual(1);
  });

  it("shows create branch button and opens dialog", async () => {
    render(
      <MemoryRouter>
        <Branches />
      </MemoryRouter>
    );
    const btn = await screen.findByRole("button", { name: /Create Branch/i });
    fireEvent.click(btn);
    expect(await screen.findByLabelText("Branch Name")).toBeTruthy();
  });

  it("shows Active Branches tab and Observability tab", async () => {
    render(
      <MemoryRouter>
        <Branches />
      </MemoryRouter>
    );
    await screen.findByText(/Lakebase branch management/);
    // Tabs use role="tab"
    const tabs = screen.getAllByRole("tab");
    const labels = tabs.map((t) => t.textContent);
    expect(labels).toContain("Active Branches");
    expect(labels).toContain("Observability");
  });
});
