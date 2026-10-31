/**
 * The product's UI primitives.
 *
 * Hand-written on the design tokens in globals.css — no component library, no
 * icon package, no CSS-in-JS. Each piece has one responsibility and none of
 * them knows a business rule: nothing in here decides what a price is, whether
 * a unit may be released, or who may do either.
 *
 * One name per primitive. There are no aliases here: a second name for the
 * same component is how two screens drift apart while both believing they use
 * the canonical one, and `tests/test_product_experience.py` fails the build
 * if one appears.
 */

export { Badge, StatusDot } from "./Badge";
export type { Tone } from "./Badge";
export { Button, ButtonRow } from "./Button";
export { Card, SubPanel } from "./Card";
export type { CardTone } from "./Card";
export { DialogPortal } from "./DialogPortal";
export { ConfirmDialog } from "./ConfirmDialog";
export { RecordPage } from "./RecordPage";
export type { RecordPageFact, RecordPageHeadline } from "./RecordPage";
export {
  Breakdown,
  BreakdownRow,
  Distribution,
  DistributionBand,
  DistributionTrack,
  IdentityCell,
  InlineMeta,
  InlineMetaItem,
  KeyValue,
  KeyValueGrid,
  Meter,
  Metric,
  MetricGroup,
  PlaceCell,
  Position,
  PositionFigure,
  PositionSupport,
  PositionSupportItem,
  StatStrip,
  StatStripItem,
  StatStripNote,
  Waterfall,
  WaterfallRow,
} from "./Data";
export { TableScroll } from "./TableScroll";
export { ExternalLink, isUrl } from "./Link";
export type { BandHeat, MetricTone } from "./Data";
export { EmptyState, Loading, Notice } from "./Feedback";
export {
  ChoiceCards,
  DataToolbar,
  Field,
  FieldRow,
  Form,
  FormActions,
  FormOutline,
  FormSection,
  MoneyInput,
  RateInput,
  StickyActions,
  ToolbarFilter,
  sectionId,
} from "./Form";
export { FormDialog } from "./FormDialog";
export { PageHeader, SectionHeader } from "./Headers";
export { PromptDialog } from "./PromptDialog";
export { Icon } from "./Icon";
export type { IconName } from "./Icon";
export { TabPanel, Tabs } from "./Tabs";
export { Steps, Timeline, TimelineItem } from "./Timeline";
export type { TimelineState } from "./Timeline";

export { Disclosure } from "./Disclosure";
export { Views } from "./Views";
export { NextBar, RecordStrip } from "./RecordStrip";
export { FlowActions, FlowSteps } from "./Flow";
export type { FlowStep } from "./Flow";
export { BulkBar, CardRow, CardRows, DATE_PRESETS, DatePoint, DateRange, FilterChips, InlineEdit, SelectAllCell, SelectCell, SortHeader, useSelection, useSort } from "./Register";
export type { DatePreset, FilterChip, SortKey } from "./Register";
export { SavedViews } from "./SavedViews";
export { DensityProvider, DensitySwitch, useDensity } from "./Density";
export type { View } from "./Views";
export { Segmented } from "./Segmented";
export { RowMenu } from "./RowMenu";
export { ToastProvider, useToast } from "./Toast";
export type { ToastOptions } from "./Toast";
export { Banner } from "./Banner";
export { Switch, Tooltip, AvatarStack, Kbd } from "./Controls";
export { AttentionList } from "./Attention";
export type { AttentionEntry } from "./Attention";
export { CountComposition, CountSeries, UnitGrid } from "./CountVisuals";
export { SourceNote } from "./SourceNote";
export type { Coverage } from "./SourceNote";
export { RecordWorkspace, RecordLink, useRecordTab, useRecordHref } from "./RecordWorkspace";
export type { WorkspaceFact, WorkspaceHeadline } from "./RecordWorkspace";

export { RegisterPagination } from "./RegisterPagination";
export { UnsavedChangesGuard, DraftBoundary } from "./UnsavedChangesGuard";

export { ValidationSummary } from "./ValidationSummary";
