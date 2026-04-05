import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import StatusBadge from "../components/StatusBadge";

describe("StatusBadge component", () => {
  it("renders healthy status with green styling", () => {
    render(<StatusBadge status="healthy" />);
    expect(screen.getByText("healthy")).toBeTruthy();
  });

  it("renders error status", () => {
    render(<StatusBadge status="error" />);
    expect(screen.getByText("error")).toBeTruthy();
  });

  it("renders warning status", () => {
    render(<StatusBadge status="warning" />);
    expect(screen.getByText("warning")).toBeTruthy();
  });

  it("renders unknown status with default styling", () => {
    render(<StatusBadge status="unknown" />);
    expect(screen.getByText("unknown")).toBeTruthy();
  });
});
