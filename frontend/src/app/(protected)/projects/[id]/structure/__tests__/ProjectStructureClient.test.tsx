/**
 * ProjectStructureClient tests — validates loading, error, and hierarchy
 * rendering states for the project structure viewer.
 */
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import "@testing-library/jest-dom";

// Mock Next.js navigation
jest.mock("next/navigation", () => ({
  useParams: jest.fn(() => ({ id: "proj-1" })),
  useRouter: () => ({ push: jest.fn() }),
  usePathname: () => "/projects/proj-1/structure",
}));

// Mock CSS modules
jest.mock("@/styles/project-structure.module.css", () => ({}));
jest.mock("@/components/shell/PageContainer.module.css", () => ({}));

// Mock API
jest.mock("@/lib/project-structure-api", () => ({
  getProjectStructure: jest.fn(),
}));

import { useParams } from "next/navigation";
import { getProjectStructure } from "@/lib/project-structure-api";
import { ProjectStructureClient } from "@/app/(protected)/projects/[id]/structure/ProjectStructureClient";

const mockUseParams = useParams as jest.Mock;
const mockGetProjectStructure = getProjectStructure as jest.Mock;

// ---------------------------------------------------------------------------
// Mock data
// ---------------------------------------------------------------------------

const mockUnit = {
  id: "unit-1",
  unit_number: "101",
  unit_type: "studio",
  status: "available",
};

const mockFloor = {
  id: "floor-1",
  name: "Ground Floor",
  code: "FL-00",
  sequence_number: 1,
  level_number: 0,
  status: "planned",
  unit_count: 1,
  units: [mockUnit],
};

const mockBuilding = {
  id: "building-1",
  name: "Block A",
  code: "BLK-A",
  status: "planned",
  floor_count: 1,
  unit_count: 1,
  floors: [mockFloor],
};

const mockPhase = {
  id: "phase-1",
  name: "Phase 1",
  code: null,
  sequence: 1,
  phase_type: "construction",
  status: "planned",
  building_count: 1,
  floor_count: 1,
  unit_count: 1,
  buildings: [mockBuilding],
};

const mockStructure = {
  project_id: "proj-1",
  project_name: "Marina Tower",
  project_code: "MT-01",
  project_status: "active",
  phase_count: 1,
  building_count: 1,
  floor_count: 1,
  unit_count: 1,
  phases: [mockPhase],
};

const mockEmptyStructure = {
  project_id: "proj-1",
  project_name: "Empty Project",
  project_code: "EP-01",
  project_status: "pipeline",
  phase_count: 0,
  building_count: 0,
  floor_count: 0,
  unit_count: 0,
  phases: [],
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ProjectStructureClient", () => {
  beforeEach(() => {
    jest.clearAllMocks();
    mockUseParams.mockReturnValue({ id: "proj-1" });
  });

  it("renders loading state initially", () => {
    mockGetProjectStructure.mockReturnValue(new Promise(() => {}));
    render(<ProjectStructureClient />);
    expect(screen.getByText(/loading project structure/i)).toBeInTheDocument();
  });

  it("renders error state on API failure", async () => {
    mockGetProjectStructure.mockRejectedValue(new Error("Network error"));
    render(<ProjectStructureClient />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument(),
    );
    expect(screen.getByText("Network error")).toBeInTheDocument();
  });

  it("renders error state with fallback message on non-Error rejection", async () => {
    mockGetProjectStructure.mockRejectedValue("unexpected");
    render(<ProjectStructureClient />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toBeInTheDocument(),
    );
    expect(screen.getByText("Failed to load project structure.")).toBeInTheDocument();
  });

  it("renders project name and code in page title after successful load", async () => {
    mockGetProjectStructure.mockResolvedValue(mockStructure);
    render(<ProjectStructureClient />);
    await waitFor(() =>
      expect(screen.getByText(/Marina Tower/)).toBeInTheDocument(),
    );
    expect(screen.getByText(/MT-01/)).toBeInTheDocument();
  });

  it("renders summary counts in structure tree", async () => {
    mockGetProjectStructure.mockResolvedValue(mockStructure);
    render(<ProjectStructureClient />);
    await waitFor(() =>
      expect(screen.getByText(/Phase 1/)).toBeInTheDocument(),
    );
    // Summary strip shows counts
    expect(screen.getByText("Phases")).toBeInTheDocument();
    expect(screen.getByText("Buildings")).toBeInTheDocument();
    expect(screen.getByText("Floors")).toBeInTheDocument();
    expect(screen.getByText("Units")).toBeInTheDocument();
  });

  it("renders phase node with status and type badges", async () => {
    mockGetProjectStructure.mockResolvedValue(mockStructure);
    render(<ProjectStructureClient />);
    await waitFor(() =>
      expect(screen.getByText(/Phase 1: Phase 1/)).toBeInTheDocument(),
    );
    expect(screen.getByText("construction")).toBeInTheDocument();
    expect(screen.getByText("planned")).toBeInTheDocument();
  });

  it("renders empty state when project has no phases", async () => {
    mockGetProjectStructure.mockResolvedValue(mockEmptyStructure);
    render(<ProjectStructureClient />);
    await waitFor(() =>
      expect(screen.getByText(/no phases yet/i)).toBeInTheDocument(),
    );
  });

  it("does not call API when projectId is placeholder '_'", async () => {
    mockUseParams.mockReturnValue({ id: "_" });
    render(<ProjectStructureClient />);
    await waitFor(() => expect(mockGetProjectStructure).not.toHaveBeenCalled());
  });

  it("renders building nodes when a phase is expanded by default", async () => {
    mockGetProjectStructure.mockResolvedValue(mockStructure);
    render(<ProjectStructureClient />);
    await waitFor(() =>
      expect(screen.getByText("Block A")).toBeInTheDocument(),
    );
  });

  it("expands building to show floors on click", async () => {
    mockGetProjectStructure.mockResolvedValue(mockStructure);
    const user = userEvent.setup();
    render(<ProjectStructureClient />);

    await waitFor(() =>
      expect(screen.getByText("Block A")).toBeInTheDocument(),
    );

    // Building is collapsed by default, click to expand
    const buildingButton = screen.getByRole("button", { name: /building: block a/i });
    await user.click(buildingButton);

    await waitFor(() =>
      expect(screen.getByText("Ground Floor")).toBeInTheDocument(),
    );
  });

  it("expands floor to show units on click", async () => {
    mockGetProjectStructure.mockResolvedValue(mockStructure);
    const user = userEvent.setup();
    render(<ProjectStructureClient />);

    // Expand building first
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /building: block a/i })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /building: block a/i }));

    // Expand floor
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /floor: ground floor/i })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /floor: ground floor/i }));

    // Unit should now be visible
    await waitFor(() =>
      expect(screen.getByText("101")).toBeInTheDocument(),
    );
  });

  it("renders building empty state when building has no floors", async () => {
    const structureWithEmptyBuilding = {
      ...mockStructure,
      phases: [
        {
          ...mockPhase,
          buildings: [
            {
              ...mockBuilding,
              floor_count: 0,
              unit_count: 0,
              floors: [],
            },
          ],
        },
      ],
    };
    mockGetProjectStructure.mockResolvedValue(structureWithEmptyBuilding);
    const user = userEvent.setup();
    render(<ProjectStructureClient />);

    await waitFor(() =>
      expect(screen.getByRole("button", { name: /building: block a/i })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /building: block a/i }));

    await waitFor(() =>
      expect(screen.getByText(/no floors in this building/i)).toBeInTheDocument(),
    );
  });

  it("renders floor empty state when floor has no units", async () => {
    const structureWithEmptyFloor = {
      ...mockStructure,
      phases: [
        {
          ...mockPhase,
          buildings: [
            {
              ...mockBuilding,
              floors: [{ ...mockFloor, unit_count: 0, units: [] }],
            },
          ],
        },
      ],
    };
    mockGetProjectStructure.mockResolvedValue(structureWithEmptyFloor);
    const user = userEvent.setup();
    render(<ProjectStructureClient />);

    // Expand building
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /building: block a/i })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /building: block a/i }));

    // Expand floor
    await waitFor(() =>
      expect(screen.getByRole("button", { name: /floor: ground floor/i })).toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /floor: ground floor/i }));

    await waitFor(() =>
      expect(screen.getByText(/no units on this floor/i)).toBeInTheDocument(),
    );
  });

  it("renders phase empty state when phase has no buildings", async () => {
    const structureWithEmptyPhase = {
      ...mockStructure,
      phases: [
        {
          ...mockPhase,
          building_count: 0,
          floor_count: 0,
          unit_count: 0,
          buildings: [],
        },
      ],
    };
    mockGetProjectStructure.mockResolvedValue(structureWithEmptyPhase);
    render(<ProjectStructureClient />);

    await waitFor(() =>
      expect(screen.getByText(/no buildings in this phase/i)).toBeInTheDocument(),
    );
  });
});
