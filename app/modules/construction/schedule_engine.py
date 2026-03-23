"""
construction.schedule_engine

Pure Construction Schedule Calculation Engine.

Implements the Critical Path Method (CPM) for construction milestone scheduling.

Algorithm
---------
1. Build a directed acyclic graph (DAG) from milestone dependencies.
2. Forward pass  — compute Earliest Start (ES) and Earliest Finish (EF)
                   for each node, propagating from project day 0.
3. Backward pass — compute Latest Start (LS) and Latest Finish (LF)
                   working backwards from the project end.
4. Float         — Total Float = LS − ES = LF − EF.
5. Critical Path — milestones with Total Float == 0.
6. Delay         — if a milestone has slipped (actual_start > es), propagate
                   the slip forward through its successors.

No database access, no HTTP concerns, no cost formulas in this module.
All inputs and outputs use plain Python dataclasses.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Input / output dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SchedulePhase:
    """Represents one construction milestone as a CPM node.

    Parameters
    ----------
    phase_id:
        Unique identifier (matches ConstructionMilestone.id).
    duration_days:
        Planned duration in calendar days. Must be >= 0.
    predecessor_ids:
        IDs of phases that must finish before this phase can start.
    lag_days:
        Optional additional waiting days after each predecessor finishes.
        Keys are predecessor_id values; missing entries default to 0.
    actual_start_day:
        If the phase has already been started (or is delayed), the actual
        start day relative to project day 0.  None means not yet started.
    """

    phase_id: str
    duration_days: int
    predecessor_ids: List[str] = field(default_factory=list)
    lag_days: Dict[str, int] = field(default_factory=dict)
    actual_start_day: Optional[int] = None


@dataclass
class ScheduleResult:
    """CPM output for a single construction milestone.

    Parameters
    ----------
    phase_id:      matches the input SchedulePhase.phase_id
    earliest_start:  day on which the phase can start at the earliest
    earliest_finish: earliest_start + duration_days
    latest_start:    latest day the phase can start without delaying the project
    latest_finish:   latest_start + duration_days
    total_float:     scheduling slack (LS − ES);  0 => on critical path
    is_critical:     True when total_float == 0
    delay_days:      if actual_start_day > earliest_start, the slippage
    """

    phase_id: str
    earliest_start: int
    earliest_finish: int
    latest_start: int
    latest_finish: int
    total_float: int
    is_critical: bool
    delay_days: int = 0


@dataclass
class ScheduleOutput:
    """Full schedule result for a set of construction milestones.

    Parameters
    ----------
    phases:         CPM result for each phase, in topological order.
    project_duration: earliest finish of the last phase (critical path length).
    critical_path:  ordered list of phase_ids on the critical path.
    """

    phases: List[ScheduleResult]
    project_duration: int
    critical_path: List[str]


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def detect_cycle(phases: List[SchedulePhase]) -> Optional[List[str]]:
    """Return a cycle as a list of phase_ids if one exists, else None.

    Uses DFS colouring (white / grey / black).
    """
    ids = {p.phase_id for p in phases}
    adj: Dict[str, List[str]] = {p.phase_id: [] for p in phases}
    for p in phases:
        for pred in p.predecessor_ids:
            if pred in ids:
                # edge: predecessor → successor (for forward traversal)
                adj[pred].append(p.phase_id)

    WHITE, GREY, BLACK = 0, 1, 2
    colour: Dict[str, int] = {pid: WHITE for pid in ids}
    parent: Dict[str, Optional[str]] = {pid: None for pid in ids}

    def dfs(node: str) -> Optional[List[str]]:
        colour[node] = GREY
        for nxt in adj[node]:
            if colour[nxt] == GREY:
                # reconstruct cycle
                cycle = [nxt, node]
                cur = parent[node]
                while cur is not None and cur != nxt:
                    cycle.append(cur)
                    cur = parent[cur]
                cycle.append(nxt)
                return list(reversed(cycle))
            if colour[nxt] == WHITE:
                parent[nxt] = node
                result = dfs(nxt)
                if result is not None:
                    return result
        colour[node] = BLACK
        return None

    for pid in ids:
        if colour[pid] == WHITE:
            cycle = dfs(pid)
            if cycle is not None:
                return cycle
    return None


# ---------------------------------------------------------------------------
# Topological sort (Kahn's algorithm)
# ---------------------------------------------------------------------------


def _topological_sort(phases: List[SchedulePhase]) -> List[str]:
    """Return a topological ordering of phase_ids.

    Assumes the graph is already validated to be acyclic.
    """
    ids = {p.phase_id for p in phases}
    in_degree: Dict[str, int] = {pid: 0 for pid in ids}
    adj: Dict[str, List[str]] = {pid: [] for pid in ids}

    for p in phases:
        for pred in p.predecessor_ids:
            if pred in ids:
                adj[pred].append(p.phase_id)
                in_degree[p.phase_id] += 1

    queue: deque[str] = deque(pid for pid in ids if in_degree[pid] == 0)
    order: List[str] = []

    while queue:
        node = queue.popleft()
        order.append(node)
        for nxt in adj[node]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    return order


# ---------------------------------------------------------------------------
# CPM forward and backward passes
# ---------------------------------------------------------------------------


def _forward_pass(
    order: List[str],
    phase_map: Dict[str, SchedulePhase],
) -> Dict[str, tuple[int, int, int]]:
    """Compute (ES, EF, base_es) for each phase.

    base_es is the CPM-derived earliest start before honouring actual_start_day.

    Returns
    -------
    dict mapping phase_id → (earliest_start, earliest_finish, base_es)
    """
    es_ef: Dict[str, tuple[int, int, int]] = {}

    for pid in order:
        p = phase_map[pid]
        if not p.predecessor_ids:
            base_es = 0
        else:
            base_es = 0
            for pred_id in p.predecessor_ids:
                if pred_id not in es_ef:
                    # predecessor outside the provided set — treat as day-0 finish
                    pred_ef = 0
                else:
                    pred_ef = es_ef[pred_id][1]
                lag = p.lag_days.get(pred_id, 0)
                base_es = max(base_es, pred_ef + lag)

        # honour actual start if later than CPM early start
        es = base_es
        if p.actual_start_day is not None:
            es = max(es, p.actual_start_day)

        ef = es + p.duration_days
        es_ef[pid] = (es, ef, base_es)

    return es_ef


def _backward_pass(
    order: List[str],
    phase_map: Dict[str, SchedulePhase],
    es_ef: Dict[str, tuple[int, int, int]],
    project_end: int,
) -> Dict[str, tuple[int, int]]:
    """Compute (LS, LF) for each phase.

    Returns
    -------
    dict mapping phase_id → (latest_start, latest_finish)
    """
    # Build successor map
    successor_map: Dict[str, List[str]] = {pid: [] for pid in order}
    for pid in order:
        p = phase_map[pid]
        for pred_id in p.predecessor_ids:
            if pred_id in successor_map:
                successor_map[pred_id].append(pid)

    ls_lf: Dict[str, tuple[int, int]] = {}

    for pid in reversed(order):
        p = phase_map[pid]
        successors = successor_map[pid]
        if not successors:
            lf = project_end
        else:
            lf = project_end
            for suc_id in successors:
                suc_ls = ls_lf[suc_id][0]
                lag = phase_map[suc_id].lag_days.get(pid, 0)
                lf = min(lf, suc_ls - lag)

        ls = lf - p.duration_days
        ls_lf[pid] = (ls, lf)

    return ls_lf


# ---------------------------------------------------------------------------
# Main engine entry point
# ---------------------------------------------------------------------------


def compute_schedule(phases: List[SchedulePhase]) -> ScheduleOutput:
    """Compute the full CPM schedule for a set of construction milestones.

    Parameters
    ----------
    phases:
        List of :class:`SchedulePhase` nodes.  May be empty.

    Returns
    -------
    ScheduleOutput
        CPM results for each phase, project duration, and critical path.

    Raises
    ------
    ValueError
        If the dependency graph contains a cycle.
    """
    if not phases:
        return ScheduleOutput(phases=[], project_duration=0, critical_path=[])

    # Validate graph
    cycle = detect_cycle(phases)
    if cycle is not None:
        raise ValueError(
            f"Circular dependency detected in construction schedule: "
            f"{' → '.join(cycle)}"
        )

    phase_map: Dict[str, SchedulePhase] = {p.phase_id: p for p in phases}
    order = _topological_sort(phases)

    # Forward pass
    es_ef = _forward_pass(order, phase_map)

    # Project end = latest EF across all phases
    project_end = max(ef for _, ef, _ in es_ef.values()) if es_ef else 0

    # Backward pass
    ls_lf = _backward_pass(order, phase_map, es_ef, project_end)

    # Assemble results
    results: List[ScheduleResult] = []
    for pid in order:
        es, ef, base_es = es_ef[pid]
        ls, lf = ls_lf[pid]
        total_float = ls - es
        delay_days = max(0, es - base_es)
        results.append(
            ScheduleResult(
                phase_id=pid,
                earliest_start=es,
                earliest_finish=ef,
                latest_start=ls,
                latest_finish=lf,
                total_float=total_float,
                is_critical=(total_float == 0),
                delay_days=delay_days,
            )
        )

    critical_path = [r.phase_id for r in results if r.is_critical]

    return ScheduleOutput(
        phases=results,
        project_duration=project_end,
        critical_path=critical_path,
    )
