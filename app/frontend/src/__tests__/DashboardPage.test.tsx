import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Dashboard from "../pages/Dashboard";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve([
          { metric_name: "cache_hit_ratio", metric_value: "0.9985" },
          { metric_name: "active_connections", metric_value: "5" },
        ]),
    })
  );
});

describe("Dashboard page", () => {
  it("renders title after data loads", async () => {
    render(
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    );
    expect(await screen.findByText("Dashboard")).toBeTruthy();
  });
});
