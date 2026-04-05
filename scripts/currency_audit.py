#!/usr/bin/env python
"""
scripts/currency_audit.py

CLI tool for currency integrity auditing.

Connects to the application database and scans all project-linked
financial records for currency anomalies, then prints a summary report.

Usage
-----
    python scripts/currency_audit.py

Output
------
    Summary counts per issue type followed by a detailed listing of each
    detected anomaly.  Exit code 0 if no issues, 1 if any issues found.
"""

from __future__ import annotations

import sys
from collections import Counter

# Ensure the project root is on the Python path when running directly.
import os

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.core.database import SessionLocal  # noqa: E402
from app.modules.admin.currency_audit_service import scan_currency_integrity  # noqa: E402


def main() -> int:
    print("Currency Integrity Audit")
    print("=" * 60)

    with SessionLocal() as db:
        issues = scan_currency_integrity(db)

    if not issues:
        print("✅  No currency anomalies detected.")
        return 0

    counts: Counter[str] = Counter(issue["type"] for issue in issues)

    print(f"\nTotal issues found: {len(issues)}\n")
    print("Counts by type:")
    for issue_type, count in sorted(counts.items()):
        print(f"  {issue_type:<30} {count}")

    print("\nIssue details:")
    print("-" * 60)
    for issue in issues:
        print(
            f"  [{issue['type']}]"
            f"  project={issue['project_id']}"
            f"  record_type={issue['record_type']}"
            f"  record_id={issue['record_id']}"
            f"  currency={issue['currency']!r}"
            f"  project_currency={issue['project_currency']!r}"
        )

    return 1


if __name__ == "__main__":
    sys.exit(main())
