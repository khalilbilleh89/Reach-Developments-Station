/**
 * ProjectSelector tests
 */
import React from "react";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import "@testing-library/jest-dom";
import { ProjectSelector } from "../ProjectSelector";

jest.mock("@/styles/dashboard.module.css", () => ({}));

// Mock the dashboard API module
jest.mock("@/lib/dashboard-api", () => ({
  getProjects: jest.fn(),
}));

import { getProjects } from "@/lib/dashboard-api";
const mockGetProjects = getProjects as jest.Mock;

describe("ProjectSelector", () => {
  beforeEach(() => {
    jest.clearAllMocks();
  });

  it("shows loading state initially", async () => {
    // Never-resolving promise to keep loading state
    mockGetProjects.mockReturnValue(new Promise(() => {}));
    render(<ProjectSelector onSelect={jest.fn()} />);
    expect(screen.getByText(/Loading projects/i)).toBeInTheDocument();
  });

  it("renders project options after load", async () => {
    mockGetProjects.mockResolvedValue([
      { id: "1", name: "Marina Tower", code: "MT-01", status: "active" },
      { id: "2", name: "Palm Villa", code: "PV-01", status: "active" },
    ]);
    const onSelect = jest.fn();
    render(<ProjectSelector onSelect={onSelect} />);

    await waitFor(() =>
      expect(screen.getByRole("combobox")).toBeInTheDocument(),
    );

    expect(screen.getByText("Marina Tower")).toBeInTheDocument();
    expect(screen.getByText("Palm Villa")).toBeInTheDocument();
  });

  it("calls onSelect with the first project on initial load", async () => {
    const projects = [
      { id: "1", name: "Marina Tower", code: "MT-01", status: "active" },
      { id: "2", name: "Palm Villa", code: "PV-01", status: "active" },
    ];
    mockGetProjects.mockResolvedValue(projects);
    const onSelect = jest.fn();
    render(<ProjectSelector onSelect={onSelect} />);

    await waitFor(() => expect(onSelect).toHaveBeenCalledWith(projects[0]));
  });

  it("calls onSelect when selection changes", async () => {
    const projects = [
      { id: "1", name: "Marina Tower", code: "MT-01", status: "active" },
      { id: "2", name: "Palm Villa", code: "PV-01", status: "active" },
    ];
    mockGetProjects.mockResolvedValue(projects);
    const onSelect = jest.fn();
    render(<ProjectSelector onSelect={onSelect} selectedId="1" />);

    await waitFor(() =>
      expect(screen.getByRole("combobox")).toBeInTheDocument(),
    );

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "2" } });
    expect(onSelect).toHaveBeenCalledWith(projects[1]);
  });

  it("shows empty message when project list is empty", async () => {
    mockGetProjects.mockResolvedValue([]);
    render(<ProjectSelector onSelect={jest.fn()} />);
    await waitFor(() =>
      expect(screen.getByText(/No projects found/i)).toBeInTheDocument(),
    );
  });

  it("shows error message on API failure", async () => {
    mockGetProjects.mockRejectedValue(new Error("Network error"));
    render(<ProjectSelector onSelect={jest.fn()} />);
    await waitFor(() =>
      expect(screen.getByText("Network error")).toBeInTheDocument(),
    );
  });
});
