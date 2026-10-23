"""Compare two assessments of one client, so progress between audits is visible.

Requirements are matched by code. A code present in only one of the two catalogue
versions is reported separately rather than counted as a change in either direction.
"""

from app.cis_scoring import STATUS_SCORES, compute
from app.models import Assessment, ImplementationStatus

RANK = {
    ImplementationStatus.not_implemented: 0,
    ImplementationStatus.partial: 1,
    ImplementationStatus.implemented: 2,
}


def _verdicts(assessment: Assessment) -> dict[str, ImplementationStatus]:
    return {item.safeguard_id: item.status for item in assessment.items}


def _delta(before: float | None, after: float | None) -> float | None:
    if before is None or after is None:
        return None
    return round(after - before, 4)


def build(base: Assessment, target: Assessment, base_catalogue: dict, target_catalogue: dict) -> dict:
    """`base` is the earlier audit, `target` the later one."""
    base_result = compute(base.items, base.target_ig, base_catalogue)
    target_result = compute(target.items, target.target_ig, target_catalogue)

    base_verdicts = _verdicts(base)
    target_verdicts = _verdicts(target)
    shared = set(base_catalogue) & set(target_catalogue)

    improved: list[dict] = []
    regressed: list[dict] = []
    unchanged = 0

    for code in sorted(shared, key=lambda c: tuple(int(p or 0) for p in c.split(".")[:2])):
        before = base_verdicts.get(code, ImplementationStatus.not_implemented)
        after = target_verdicts.get(code, ImplementationStatus.not_implemented)
        if before is after:
            unchanged += 1
            continue
        # Moving to or from «не применимо» is a scope decision, not progress.
        if ImplementationStatus.not_applicable in (before, after):
            continue
        entry = {
            "safeguard_id": code,
            "title": target_catalogue[code]["title"],
            "control": target_catalogue[code]["control"],
            "ig": target_catalogue[code]["ig"],
            "before": before.value,
            "after": after.value,
        }
        (improved if RANK[after] > RANK[before] else regressed).append(entry)

    by_control_base = {row["control"]: row for row in base_result["by_control"]}
    by_control = [
        {
            "control": row["control"],
            "before": (by_control_base.get(row["control"]) or {}).get("implementation"),
            "after": row["implementation"],
            "delta": _delta(
                (by_control_base.get(row["control"]) or {}).get("implementation"),
                row["implementation"],
            ),
        }
        for row in target_result["by_control"]
    ]

    return {
        "base": _summary(base, base_result),
        "target": _summary(target, target_result),
        "overall_delta": _delta(
            base_result["overall"]["implementation"], target_result["overall"]["implementation"]
        ),
        "groups": [
            {
                "group": name,
                "before": base_result["implementation_groups"][name]["implementation"],
                "after": target_result["implementation_groups"][name]["implementation"],
                "delta": _delta(
                    base_result["implementation_groups"][name]["implementation"],
                    target_result["implementation_groups"][name]["implementation"],
                ),
            }
            for name in ("IG1", "IG2", "IG3")
        ],
        "by_control": by_control,
        "improved": improved,
        "regressed": regressed,
        "unchanged": unchanged,
        "only_in_base": sorted(set(base_catalogue) - set(target_catalogue)),
        "only_in_target": sorted(set(target_catalogue) - set(base_catalogue)),
        "gaps_closed": [
            entry for entry in improved if entry["after"] == ImplementationStatus.implemented.value
        ],
        "gaps_opened": [
            entry
            for entry in regressed
            if entry["before"] == ImplementationStatus.implemented.value
        ],
    }


def _summary(assessment: Assessment, result: dict) -> dict:
    return {
        "id": str(assessment.id),
        "name": assessment.name,
        "framework_version": assessment.framework_version,
        "target_ig": assessment.target_ig,
        "status": assessment.status.value,
        "updated_at": assessment.updated_at.isoformat() if assessment.updated_at else None,
        "completed_at": assessment.completed_at.isoformat() if assessment.completed_at else None,
        "implementation": result["overall"]["implementation"],
        "gaps": len(result["gaps"]),
    }


__all__ = ["build", "STATUS_SCORES"]
