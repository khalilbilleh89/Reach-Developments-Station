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
export { ConfirmDialog } from "./ConfirmDialog";
export { Drawer } from "./Drawer";
export type { DrawerFact, DrawerHeadline } from "./Drawer";
export {
  Breakdown,
  BreakdownRow,
  Distribution,
  DistributionBand,
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
  TableScroll,
  Waterfall,
  WaterfallRow,
} from "./Data";
export { ExternalLink, isUrl } from "./Link";
export type { MetricTone } from "./Data";
export { EmptyState, Loading, Notice } from "./Feedback";
export {
  DataToolbar,
  Field,
  FieldRow,
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
