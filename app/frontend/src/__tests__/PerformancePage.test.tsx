import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Performance from "../pages/Performance";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          {
            queryid: "abc123",
            query: "SELECT * FROM users",
            total_calls: 100,
            avg_exec_time_ms: 45.2,
            total_time_ms: 4520,
            total_rows: 10000,
            total_read_mb: 12.5,
          },
        ]),
    })
  );
});

describe("Performance page", () => {
  it("renders title after data loads", async () => {
    render(
      <MemoryRouter>
        <Performance />
      </MemoryRouter>
    );
    expect(await screen.findByText("Performance")).toBeTruthy();
  });

  it("renders slow queries table title", async () => {
    render(
      <MemoryRouter>
        <Performance />
      </MemoryRouter>
    );
    expect(await screen.findByText("Top 10 Slowest Queries (24h)")).toBeTruthy();
  });

  it("renders regression detection table title", async () => {
    render(
      <MemoryRouter>
        <Performance />
      </MemoryRouter>
    );
    expect(await screen.findByText("Regression Detection")).toBeTruthy();
  });

  it("renders subtitle", async () => {
    render(
      <MemoryRouter>
        <Performance />
      </MemoryRouter>
    );
    expect(
      await screen.findByText("Slow query analysis and regression detection")
    ).toBeTruthy();
  });
});
