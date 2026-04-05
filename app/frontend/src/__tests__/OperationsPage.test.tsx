import { render, screen } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Operations from "../pages/Operations";

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve([]),
    })
  );
});

describe("Operations page", () => {
  it("renders title after data loads", async () => {
    render(
      <MemoryRouter>
        <Operations />
      </MemoryRouter>
    );
    expect(await screen.findByText("Operations")).toBeTruthy();
  });

  it("renders Vacuum tab", async () => {
    render(
      <MemoryRouter>
        <Operations />
      </MemoryRouter>
    );
    expect(await screen.findByText("Vacuum")).toBeTruthy();
  });

  it("renders Sync tab", async () => {
    render(
      <MemoryRouter>
        <Operations />
      </MemoryRouter>
    );
    expect(await screen.findByText("Sync")).toBeTruthy();
  });

  it("renders sync button", async () => {
    render(
      <MemoryRouter>
        <Operations />
      </MemoryRouter>
    );
    expect(
      await screen.findByText("Sync Tables in Unity Catalog Schema Lakebase_Ops")
    ).toBeTruthy();
  });
});
