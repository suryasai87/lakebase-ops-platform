import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import DataTable from "../components/DataTable";

describe("DataTable", () => {
  it("renders column headers", () => {
    render(
      <DataTable
        title="Test Table"
        columns={[
          { key: "name", label: "Name" },
          { key: "value", label: "Value" },
        ]}
        rows={[{ name: "Row1", value: 42 }]}
      />
    );
    expect(screen.getByText("Name")).toBeTruthy();
    expect(screen.getByText("Value")).toBeTruthy();
    expect(screen.getByText("Row1")).toBeTruthy();
  });

  it("shows empty state when no rows", () => {
    render(
      <DataTable
        title="Empty"
        columns={[{ key: "col", label: "Col" }]}
        rows={[]}
      />
    );
    expect(screen.getByText("No data available")).toBeTruthy();
  });
});
