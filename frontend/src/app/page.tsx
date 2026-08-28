/**
 * MVP 1.0 application shell.
 *
 * PR-MVP-00 builds infrastructure, not business screens. This page states what
 * is actually true about the running deployment and nothing else: no sample
 * units, no sample sales, no placeholder metrics.
 */
export default function HomePage() {
  return (
    <div className="shell">
      <main className="panel">
        <p className="eyebrow">MVP 1.0</p>
        <h1 className="title">Reach Developments Station</h1>
        <p className="tagline">
          Real Estate Development Tracking &amp; Financial Control
        </p>

        <p className="status">
          <span className="status-dot" aria-hidden="true" />
          Foundation Ready
        </p>

        <hr className="divider" />

        <h2 className="section-heading">Service endpoints</h2>
        <dl className="reference-list">
          <div>
            <dt className="reference-term">Liveness</dt>
            <dd className="reference-value">GET /api/v1/health/live</dd>
          </div>
          <div>
            <dt className="reference-term">Readiness</dt>
            <dd className="reference-value">GET /api/v1/health/ready</dd>
          </div>
        </dl>

        <p className="footnote">
          The business domain is delivered by the roadmap PRs in{" "}
          <code>docs/MVP_ROADMAP.md</code>, starting with governance, country
          packs and access control.
        </p>
      </main>
    </div>
  );
}
