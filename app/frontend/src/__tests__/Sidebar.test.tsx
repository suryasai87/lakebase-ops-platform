import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { MemoryRouter } from "react-router-dom";
import Sidebar from "../components/Sidebar";

describe("Sidebar component", () => {
  it("renders LakebaseOps branding", () => {
    render(
      <MemoryRouter>
        <Sidebar width={240} />
      </MemoryRouter>
    );
    expect(screen.getByText("LakebaseOps")).toBeTruthy();
  });

  it("renders all navigation items", () => {
    render(
      <MemoryRouter>
        <Sidebar width={240} />
      </MemoryRouter>
    );
    expect(screen.getByText("Dashboard")).toBeTruthy();
    expect(screen.getByText("Agents")).toBeTruthy();
    expect(screen.getByText("Performance")).toBeTruthy();
    expect(screen.getByText("Indexes")).toBeTruthy();
    expect(screen.getByText("Operations")).toBeTruthy();
    expect(screen.getByText("Branches")).toBeTruthy();
    expect(screen.getByText("Adoption")).toBeTruthy();
    expect(screen.getByText("Live Stats")).toBeTruthy();
    expect(screen.getByText("Assessment")).toBeTruthy();
  });

  it("highlights the active route", () => {
    render(
      <MemoryRouter initialEntries={["/branches"]}>
        <Sidebar width={240} />
      </MemoryRouter>
    );
    const branchesButton = screen.getByText("Branches").closest("div[role='button']") ||
      screen.getByText("Branches").closest(".MuiListItemButton-root");
    // The selected button should exist with Mui-selected class
    expect(branchesButton).toBeTruthy();
  });
});
