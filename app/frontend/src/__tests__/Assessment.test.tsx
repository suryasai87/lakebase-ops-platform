import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { ThemeProvider, CssBaseline } from "@mui/material";
import theme from "../theme";
import Assessment from "../pages/Assessment";

function renderAssessment() {
  return render(
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Assessment />
    </ThemeProvider>
  );
}

const cosmosDiscoveryResult = {
  profile_id: "test-cosmos-001",
  source_engine: "cosmosdb-nosql",
  source_endpoint: "myaccount.documents.azure.com",
  source_version: "CosmosDB",
  database: "cosmos-test-db",
  size_gb: 46.6,
  table_count: 8,
  cosmos_throughput_mode: "provisioned",
  cosmos_ru_per_sec: 4000,
  cosmos_consistency_level: "Session",
  cosmos_change_feed_enabled: true,
  cosmos_multi_region_writes: true,
  cosmos_regions: ["eastus", "westeurope"],
  cosmos_partition_key_paths: ["/userId", "/orderId"],
};

const readinessResult = {
  overall_score: 65,
  category: "ready_with_workarounds",
  recommended_tier: "autoscaling",
  recommended_cu: "2-8 CU",
  estimated_effort_days: 25,
  blocker_count: 2,
  warning_count: 3,
  supported_extensions: ["Partition keys", "Change Feed"],
  unsupported_extensions: ["Integrated cache"],
  dimension_scores: { feature_compatibility: 60, complexity: 70 },
  blockers: [
    {
      severity: "medium",
      category: "feature_compatibility",
      description: "'Integrated cache' not available in Lakebase",
      workaround: "Use application-level caching",
    },
  ],
  warnings: [
    "Provisioned throughput mode requires capacity planning for Lakebase CU sizing",
    "'Integrated cache' requires workaround: Use application-level caching",
    "Cosmos DB consistency level 'Strong' has no direct Lakebase equivalent",
  ],
};

describe("Assessment - CosmosDB Discovery", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, opts?: any) => {
        if (typeof url === "string" && url.includes("/regions/")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                regions: [{ value: "eastus", label: "East US" }],
              }),
          });
        }
        if (typeof url === "string" && url.includes("/history")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([]),
          });
        }
        if (opts?.method === "POST" && typeof url === "string" && url.includes("/discover")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(cosmosDiscoveryResult),
          });
        }
        if (typeof url === "string" && url.includes("/extension-matrix/")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                extensions: [],
                summary: { supported: 0, workaround: 0, unsupported: 0 },
              }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({}),
        });
      })
    );
  });

  it("renders CosmosDB-specific discovery fields after discover", async () => {
    renderAssessment();

    const engineSelect = screen.getByLabelText("Engine");
    fireEvent.change(engineSelect, { target: { value: "cosmosdb-nosql" } });

    const discoverBtn = screen.getByText("1. Discover");
    fireEvent.click(discoverBtn);

    await waitFor(() => {
      expect(screen.getByText("cosmos-test-db")).toBeTruthy();
    });

    expect(screen.getByText("46.6 GB")).toBeTruthy();
    expect(screen.getByText("provisioned")).toBeTruthy();
    expect(screen.getByText("4000")).toBeTruthy();
    expect(screen.getByText("Session")).toBeTruthy();
  });
});

describe("Assessment - Migration Warnings", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockImplementation((url: string, opts?: any) => {
        if (typeof url === "string" && url.includes("/regions/")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                regions: [{ value: "eastus", label: "East US" }],
              }),
          });
        }
        if (typeof url === "string" && url.includes("/history")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve([]),
          });
        }
        if (opts?.method === "POST" && typeof url === "string" && url.includes("/discover")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(cosmosDiscoveryResult),
          });
        }
        if (opts?.method === "POST" && typeof url === "string" && url.includes("/profile")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                qps: 2800,
                tps: 700,
                active_connections: 60,
                peak_connections: 200,
                read_write_ratio: "75/25",
                p99_latency_ms: 12,
                top_queries: 5,
                hot_tables: 4,
              }),
          });
        }
        if (opts?.method === "POST" && typeof url === "string" && url.includes("/readiness")) {
          return Promise.resolve({
            ok: true,
            json: () => Promise.resolve(readinessResult),
          });
        }
        if (typeof url === "string" && url.includes("/extension-matrix/")) {
          return Promise.resolve({
            ok: true,
            json: () =>
              Promise.resolve({
                extensions: [],
                summary: { supported: 0, workaround: 0, unsupported: 0 },
              }),
          });
        }
        return Promise.resolve({
          ok: true,
          json: () => Promise.resolve({}),
        });
      })
    );
  });

  it("renders migration warnings section with warning strings", async () => {
    renderAssessment();

    const engineSelect = screen.getByLabelText("Engine");
    fireEvent.change(engineSelect, { target: { value: "cosmosdb-nosql" } });

    fireEvent.click(screen.getByText("1. Discover"));
    await waitFor(() => expect(screen.getByText("cosmos-test-db")).toBeTruthy());

    fireEvent.click(screen.getByText("2. Profile"));
    await waitFor(() => expect(screen.getByText("2,800")).toBeTruthy());

    fireEvent.click(screen.getByText("3. Readiness"));
    await waitFor(() => {
      expect(screen.getByText("Migration Warnings (3)")).toBeTruthy();
    });

    expect(
      screen.getByText(/capacity planning for Lakebase CU sizing/)
    ).toBeTruthy();
    expect(
      screen.getByText(/no direct Lakebase equivalent/)
    ).toBeTruthy();
  });
});
