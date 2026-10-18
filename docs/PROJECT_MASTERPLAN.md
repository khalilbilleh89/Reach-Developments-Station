# Interactive project masterplan

The owner's masterplan sales workflow lives in **Inventory > Masterplan** for every
project. Upload one drawing page per view; trace unit outlines and bind them to
permanent Inventory unit IDs. Operators select a unit in its project location and
open the existing Unit 360 workspace for authoritative details, pricing and sales.

## What this delivery supports

- PDF page selection and PNG/JPEG/WebP uploads, up to 10 MiB. The source is stored
  unchanged, with a separate normalised PNG preview bounded to 2560 pixels per side.
- Multiple masterplans, floor drawings, sections/elevations and render photographs
  per project, with a drawing reference/revision and editable title.
- Full-page footprint authoring: point-by-point tracing, keyboard-editable normalised
  coordinates, Undo, clear, unit selection, explicit base elevation and height in metres.
- Server validation of project ownership, active unit identity, duplicate mappings,
  polygon bounds, unique vertices, nonzero area and crossing/touching edges.
- 2D image overlays; calibrated, rotatable and tiltable schematic 3D extrusion for
  plan views; zoom/pan/reset; unit search and commercial-status filtering.
- Full-page presentation view and unit selection, keyboard accessible polygon controls
  and a tabular selection alternative. Unit 360 links preserve the map return context.
- Current inventory statuses, rather than a separate editable sales inventory.
  Commercial, legal, collection and delivery remain distinct. Unit labels may change
  without breaking mapping identity. Inactive/removed units show unavailable, never Available.
- Inventory refresh every 30 seconds while visible, plus focus and explicit refresh.
  Refresh pauses while authoring so drafts are retained. Confirm availability in the
  owning sale workflow before making a commitment; the map does not reserve a unit.

## Geometry and evidence

Normalised X/Y fractions refer to the full rasterised page, including margins. Image
aspect ratio is retained across zoom and camera changes. Set **Full image width in
metres** from measured drawing evidence to enable the 3D massing view. Base elevation
and unit height share the plan's modelling datum. These inputs are for visualisation;
traced polygon area never replaces an approved inventory area schedule.

A render photograph is a flat reference view with selectable hotspots. It is not
interpreted as a floor footprint, and perspective photographs cannot be extruded.
Floor drawings can be uploaded independently and selected by their titles. This PR
does not align different sheets into a single building model automatically.

**This is schematic 3D massing, not automatic photorealistic reconstruction.** Detailed
facades, terrain, interiors, roof forms, BIM/CAD import, GLB models, automatic tracing
and image-to-3D generation are outside this delivery. Accurate architectural modelling
requires verified unit boundaries, a common coordinate system, floor levels, heights
and approved source revisions. No project unit count or permit approval is inferred
from an uploaded drawing or marketing image. Reference drawings remain evidence.

## Permissions and source safety

Every route first uses the existing accessible-project boundary. Whole-project
membership is required even to read a preview: a full drawing exposes all phases,
which cannot be secured by filtering only its unit polygons. Existing structure
writers author and remove plans/mappings. No buyer information or prices are included
in new map APIs; Unit 360 applies its existing domain permissions.

Native PDFium and Pillow render in a fresh subprocess with a 30-second timeout.
Only raster PNG previews are served inline, with `no-store` and `nosniff`; embedded PDF
scripts and uploaded SVG/HTML are never served as active page content. Image dimensions
are bounded and Pillow decompression-bomb checks are enabled. The original bytes are
stored deferred and never included in metadata or audit JSON. The subprocess isolates
native renderer crashes and thread-safety; it is not an OS resource sandbox.

Sources are immutable: upload a new view for a revised drawing. Updating calibration
changes the visual geometry and is version-checked/audited; it does not certify a
measurement. Existing images and architectural originals in the owner's workspace
are not modified or copied into Git. No business drawing, actual unit dataset or
customer information is seeded into production by this feature.

## Lifecycle and deletion

`POST /api/v1/projects/{project_id}/inventory/masterplans` accepts raw file bytes and
query metadata. `PUT /{plan_id}` edits metadata/calibration with the expected version.
`GET /{plan_id}/source` downloads the original as an attachment;
`GET /{plan_id}/preview` returns PNG; `GET/POST /{plan_id}/mappings` lists/adds footprints;
`PUT /{plan_id}/mappings/{mapping_id}` edits a footprint with its expected version.

Delete buttons are available on the masterplan workspace and the selected-unit page.
`DELETE /{plan_id}` and `DELETE /{plan_id}/mappings/{mapping_id}` require a nonblank
reason and expected version, and retain attributed audit evidence. Delete a drawing's
footprints first; deleting a drawing never cascades into units or sales. Foreign keys
protect project and unit identity. A permanent unit deletion/purge with a footprint
requires explicitly deleting that footprint first; ordinary retained unit removal
leaves the map link unavailable. Project-level locking serialises competing authoring,
unit removal and deletion operations; stale edits/deletes return 409.

Migration `0045_inventory_masterplans` adds only `inventory_masterplans` and
`inventory_masterplan_mappings`. No backfill or business-state changes. Downgrade
refuses while a drawing remains, preventing silent source/geometry loss. Export and
resolve app-authored records before downgrading; code rollback can retain the additive
schema. Register both tables as PLATFORM (excluded from legacy intake).

## Verification

API tests cover file validation, PDF page selection, geometry rejection, stable unit
identity, live status ownership, duplicate/stale edits, deletion dependencies, reasons,
repeat deletion, role checks, project substitution, selected-phase image refusal,
audit retention and forward/backward migration. Frontend tests cover geometry,
keyboard activation, renamed/sold/unavailable units, calibrated 3D and flat render
references. Browser checks use a separate disposable database and synthetic inventory.
See the PR for executed counts and remaining review/CI evidence.

Governing rules: [ENGINEERING_RULES.md](ENGINEERING_RULES.md),
[DELETION_POLICY.md](DELETION_POLICY.md), [CI_STRATEGY.md](CI_STRATEGY.md).
