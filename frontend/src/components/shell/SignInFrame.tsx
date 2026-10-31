import type { ReactNode } from "react";

/**
 * The sign-in surface (design system M1): a graphite panel carrying the mark
 * and a line about the product, the form beside it. Below 45rem the panel
 * becomes a short band above a centred card. Nothing on the panel is a
 * figure: a person who has not signed in is shown no count the server has
 * not vouched for to them.
 */
export function SignInFrame({ children, foot }: { children: ReactNode; foot?: ReactNode }) {
  return (
    <div className="shell shell-signin">
      <main className="signin signin-split">
        <aside className="signin-side" aria-label="About Reach">
          <div className="signin-brand">
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 32 32" aria-hidden="true"><path d="M6 27V5h10c7 0 11 3 11 9 0 4-2 7-6 9l7 4h-9l-9-7h6c4 0 6-2 6-6s-2-5-6-5h-5v18Z" fill="currentColor" /></svg>
            </span>
            <span>
              <span className="signin-brand-name">Reach</span>
              <br />
              <span className="signin-brand-sub">Developments Station</span>
            </span>
          </div>
          <div className="signin-side-text">
            <p className="signin-headline">Every unit, every euro, every deadline in one place.</p>
            <p className="signin-sub">The operating system for Reach developments: land, permits, inventory, sales, collections and construction, with the figures the ledger stands behind.</p>
          </div>
          <p className="signin-side-foot">Access is issued by an administrator.</p>
        </aside>
        <div className="signin-form">
          {children}
          {foot ? <p className="signin-foot">{foot}</p> : null}
        </div>
      </main>
    </div>
  );
}
