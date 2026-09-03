/**
 * The product's UI primitives.
 *
 * Hand-written on the design tokens in globals.css — no component library, no
 * icon package, no CSS-in-JS. Each piece has one responsibility and none of
 * them knows a business rule: nothing in here decides what a price is, whether
 * a unit may be released, or who may do either.
 */

export { Badge, StatusDot } from "./Badge";
export type { Tone } from "./Badge";
export { Button, ButtonRow } from "./Button";
export { Card, Panel, SubPanel } from "./Card";
export { ConfirmDialog } from "./ConfirmDialog";
export { Drawer } from "./Drawer";
export type { DrawerFact } from "./Drawer";
export {
  InlineMeta,
  InlineMetaItem,
  KeyValue,
  KeyValueGrid,
  Metric,
  MetricGroup,
  Stat,
  StatRow,
  TableScroll,
  Waterfall,
  WaterfallRow,
} from "./Data";
export type { MetricTone } from "./Data";
export { EmptyState, Loading, Notice } from "./Feedback";
export {
  DataToolbar,
  Field,
  FieldRow,
  FilterBar,
  Form,
  FormActions,
  FormSection,
  MoneyInput,
  RateInput,
  StickyActions,
  ToolbarFilter,
} from "./Form";
export { FormDialog } from "./FormDialog";
export { PageHeader, SectionHeader } from "./Headers";
export { PromptDialog } from "./PromptDialog";
export { Icon } from "./Icon";
export type { IconName } from "./Icon";
export { TabPanel, Tabs } from "./Tabs";
export { Steps, Timeline, TimelineItem } from "./Timeline";
export type { TimelineState } from "./Timeline";
