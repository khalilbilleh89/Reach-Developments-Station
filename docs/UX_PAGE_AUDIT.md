# Full-page UX audit

Standing owner requirement: no side drawers anywhere, including mobile navigation.
Small centered confirmations, reason prompts and short forms are allowed.

Source audit: `050e45a`, with this change applied. All 18 shared-drawer render sites
(including loading/error branches) in 10 feature files and the mobile navigation drawer
are converted. The Drawer primitive, narrow variants, backdrop and slide animations are removed.

| Area | Converted flows | Source |
| --- | --- | --- |
| Projects | Create project | `ProjectsRegister.tsx` |
| Land | Register parcel; parcel detail/edit and its sections | `LandTab.tsx` |
| Inventory | Phase, building and floor inspectors | `inventory/StructureViews.tsx` |
| Commissions | Commission record and beneficiary distribution | `CommissionsTab.tsx` |
| Collections | Collection account | `collections/CollectionAccount.tsx` |
| Construction | Contract and certificate files, including loading and errors | `construction/ContractFile.tsx`, `construction/CertificateFile.tsx` |
| Cashflow | Figure/source drilldown | `cashflow/CashflowDrilldown.tsx` |
| Management | Create action and action detail, including embedded entry points | `portfolio/ActionRecord.tsx` |
| Outlook | Observation inspection | `portfolio/Outlook.tsx` |
| Mobile shell | Navigation menu | `shell/AppSidebar.tsx` |

## Behavior

`RecordPage` renders into the main workspace in normal document flow. It fills the
available content width, with a page heading and Back control. It is not a fixed overlay,
modal, or widened drawer. The underlying register stays mounted but hidden, retaining its
filters, pagination and state. Nested pages replace the preceding page until Back.
Existing URL selections continue to work; local-state flows use their existing Back callback.
This change does not add new deep-link URLs to local-state workflows.

Small dialogs render outside the hidden register and keep their focus handling and error
feedback. Back checks unsaved changes. The existing record permissions, API calls and
Delete controls are preserved. No new record creators or removal gaps are introduced.

Mobile navigation occupies the full page without a backdrop or lateral animation.
The persistent desktop navigation rail is ordinary navigation, not a drawer.

## Future acceptance checks

- Use a routed full page or `RecordPage` for substantial record flows.
- Never introduce a Drawer, side inspector, slide-over, or fixed side form.
- Verify desktop and phone width, long-page scrolling, nested dialogs and nested pages.
- Verify Back, retained filters, focus restoration and dirty-form confirmation.
- Keep visible deletion and the standing deletion contract with every feature.

The existing product-experience CI suite rejects the old drawer primitive/layout and
checks page semantics. Source checks complement browser checks; they do not prove every
business workflow. The deletion audit remains separate and its existing gaps stay open.

## Validation for this change

- 256 presentation, deletion and CI selector checks passed.
- All 87 frontend tests passed; ESLint, TypeScript and production build passed.
- Real Chrome component integration checks at 1440px and 390px confirmed full width,
  no horizontal overflow, nested page return, register search retention, small popup
  visibility, Escape on the popup, and Stay/Discard behavior on a dirty page.
- Browser checks use a local fixture with the actual shared components, not production
  data. Individual business pages were source-audited, not all exercised end to end.
