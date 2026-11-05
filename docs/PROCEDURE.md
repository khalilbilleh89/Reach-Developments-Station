# Creative / Procedure

Procedure sits immediately below Matrix. Create a project-owned procedure, enter the objective, SOP text/reference, inputs and outputs, then define Start, Action, Decision and End steps. Each step supports a description, responsible role, input and output. Decisions connect Yes and No to chosen steps; action/start nodes connect Next. Reordering changes presentation only. Deleting a step clears incoming links, which must be reconnected before save.

The map fits the screen; Expand allows detailed scrolling. Labels and complete step details accompany the SVG. Walk through follows the user's selected branch without changing operational records. This is manual procedure documentation, not automated Collections execution. No business policy is seeded. SOP content is plain text/reference, not a PDF or Word attachment.

Save requires one Start, at least one End, unique IDs, valid links, every node reachable and a possible end path from every node. Cycles with exits are supported; closed loops are rejected. Up to 100 steps. There is no approval/publication lifecycle: saved content remains user-authored procedure documentation.

Whole-project readers may view. Project managers and effective administrators may create/update/remove. Writes take the project lock and check versions; stale updates/deletions return 409. Deletion requires a reason and retains payload plus attributed audit snapshots. API /projects/{project_id}/procedures supports GET/POST, PUT /{procedure_id}, POST /{procedure_id}/delete.

Migration 0061_project_procedures follows 0060_plan_categories. It adds one table, no backfill. Empty downgrade works; retained records block downgrade. Roll forward after use.
