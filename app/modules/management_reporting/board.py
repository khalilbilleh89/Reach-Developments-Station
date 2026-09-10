"""One print-ready historical report; no live financial queries."""

from app.modules.management_reporting.schemas import BoardPack, Comparison, SnapshotOut


def board_pack(snapshot: SnapshotOut, comparison: Comparison | None) -> BoardPack:
    return BoardPack(
        snapshot=snapshot,
        comparison=comparison,
        historical_notice=(
            f"This report reflects the immutable management snapshot captured at "
            f"{snapshot.captured_at.isoformat()}. "
            "Current source records may have changed since capture."
        ),
        section_order=[
            "Report identity",
            "Executive position",
            "Changes since prior snapshot",
            "Projects requiring attention",
            "Commercial",
            "Collections",
            "Cash and funding",
            "Construction cost control",
            "Development, permits and design",
            "Forward outlook",
            "Management actions",
            "Coverage and data limitations",
            "Project appendix",
        ],
    )
