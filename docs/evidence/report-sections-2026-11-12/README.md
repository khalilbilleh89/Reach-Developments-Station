# Reports sections — synthetic visual evidence

Reviewed the production static export on 12 November 2026. All records are synthetic.

| View | Desktop 1440 px | Phone 390 px |
| --- | --- | --- |
| Before: Reports | [Before](before-1440.png) | [Before](before-390.png) |
| After: Site reports | [After](after-site-1440.png) | [After](after-site-390.png) |
| After: Completion certificates | [After](after-certificates-1440.png) | [After](after-certificates-390.png) |
| After: Client charters | [After](after-charters-1440.png) | [After](after-charters-390.png) |

The existing latest-report hierarchy is preserved inside Site reports. New sections
reuse Tabs, CardRows, RowMenu and the shared full-page document editor/viewer.
The mobile tab strip scrolls horizontally as designed; the document body and
forms remain vertically scrollable. No page-level horizontal overflow was found
at 1600, 1440, 1280, 1024, 768 or 390 px. No new visual debt identified.

Browser checks: PDF upload without a date to two units; three-page preview and
Next page; Drive charter creation for one unit without a date; metadata edit;
unsaved-change Stay action; reasoned Delete and register refresh. Integration
tests separately prove retained files, applicability and audit after removal.

Local build used `next build --webpack` because this isolated Windows worktree
shares a dependency junction; Turbopack rejects a junction outside its root.
CI uses the ordinary clean-install build. A local preview worker import-path
misconfiguration was corrected before the successful upload/preview check.
