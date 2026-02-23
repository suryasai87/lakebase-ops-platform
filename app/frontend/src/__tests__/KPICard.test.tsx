import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import KPICard from "../components/KPICard";

describe("KPICard", () => {
  it("renders title and suffix", () => {
    render(<KPICard title="Cache Hit" value={0.99} suffix="%" />);
    expect(screen.getByText("Cache Hit")).toBeTruthy();
    expect(screen.getByText("%")).toBeTruthy();
  });

  it("renders with custom color", () => {
    const { container } = render(
      <KPICard title="Connections" value={42} color="#58A6FF" />
    );
    expect(container.querySelector(".MuiCard-root")).toBeTruthy();
  });
});
