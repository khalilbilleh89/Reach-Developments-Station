import { Icon } from "./Icon";

/**
 * A destination outside this product: a map, an authority's portal, a filing.
 *
 * The label is what the place is called, never the address. An operator who
 * pastes a hundred characters of map query string into a project's location
 * has recorded a useful link and a useless name, and this is the difference:
 * the address stays in the `href` where a browser wants it, and the screen
 * says where the reader is being sent.
 *
 * Opens in a new tab because the reader is in the middle of something, with
 * the `noreferrer` pairing that keeps the destination from reaching back.
 */
export function ExternalLink({
  href,
  children,
  className,
}: {
  href: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <a
      className={className ? `link-external ${className}` : "link-external"}
      href={href}
      target="_blank"
      rel="noopener noreferrer"
    >
      {children}
      <Icon name="external" />
    </a>
  );
}

/**
 * Whether a recorded free-text place is actually a web address.
 *
 * The location field has always been free text, so it holds "Abdoun, Amman"
 * on one project and a map URL on the next. This decides which of the two a
 * screen is holding so it can render each as itself.
 */
export function isUrl(value: string | null | undefined): value is string {
  if (!value) return false;
  return /^https?:\/\/\S+$/i.test(value.trim());
}
