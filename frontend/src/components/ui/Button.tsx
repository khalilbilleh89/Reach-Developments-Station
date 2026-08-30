"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "default" | "primary" | "danger" | "quiet" | "link";

/**
 * Every button in the product.
 *
 * One primary action per view, everything else quiet: a screen where six
 * buttons are all filled blue is a screen that has not decided what it is for.
 * `type` defaults to "button" because an unmarked button inside a form submits
 * it, and in this product that means recording something.
 */
export function Button({
  variant = "default",
  small,
  block,
  children,
  className,
  type = "button",
  ...rest
}: {
  variant?: Variant;
  small?: boolean;
  block?: boolean;
  children: ReactNode;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  const classes = [
    "button",
    variant === "default" ? "" : `button-${variant}`,
    small ? "button-small" : "",
    block ? "button-block" : "",
    className ?? "",
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <button className={classes} type={type} {...rest}>
      {children}
    </button>
  );
}

/** A row of related actions, wrapping rather than overflowing on a phone. */
export function ButtonRow({ children }: { children: ReactNode }) {
  return <div className="button-row">{children}</div>;
}
