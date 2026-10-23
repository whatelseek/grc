"""Implementation scoring for a CIS Controls assessment.

A safeguard scores 1 when implemented, 0.5 when partial and 0 when not implemented.
«Не применимо» is excluded from both sides of the ratio rather than counted as done,
so marking something out of scope never flatters the result.
"""

from collections import defaultdict

from app.models import AssessmentItem, ImplementationStatus

STATUS_SCORES = {
    ImplementationStatus.implemented: 1.0,
    ImplementationStatus.partial: 0.5,
    ImplementationStatus.not_implemented: 0.0,
}
PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2, None: 3}


def _ratio(scored: float, counted: int) -> float | None:
    return round(scored / counted, 4) if counted else None


class _Bucket:
    __slots__ = ("scored", "counted", "not_applicable", "implemented", "partial", "missing")

    def __init__(self) -> None:
        self.scored = 0.0
        self.counted = 0
        self.not_applicable = 0
        self.implemented = 0
        self.partial = 0
        self.missing = 0

    def add(self, status: ImplementationStatus) -> None:
        if status is ImplementationStatus.not_applicable:
            self.not_applicable += 1
            return
        self.counted += 1
        self.scored += STATUS_SCORES[status]
        if status is ImplementationStatus.implemented:
            self.implemented += 1
        elif status is ImplementationStatus.partial:
            self.partial += 1
        else:
            self.missing += 1

    def as_dict(self, **extra) -> dict:
        return {
            "implementation": _ratio(self.scored, self.counted),
            "in_scope": self.counted + self.not_applicable,
            "counted": self.counted,
            "implemented": self.implemented,
            "partial": self.partial,
            "not_implemented": self.missing,
            "not_applicable": self.not_applicable,
            **extra,
        }


def compute(items: list[AssessmentItem], target_ig: int, catalogue: dict[str, dict]) -> dict:
    """`catalogue` maps a requirement code to its definition (see app.catalogue)."""
    by_id = {item.safeguard_id: item for item in items}

    overall = _Bucket()
    by_ig: dict[int, _Bucket] = defaultdict(_Bucket)
    by_control: dict[str, _Bucket] = defaultdict(_Bucket)
    by_function: dict[str, _Bucket] = defaultdict(_Bucket)
    by_asset: dict[str, _Bucket] = defaultdict(_Bucket)
    gaps: list[dict] = []
    answered = 0

    for safeguard_id, safeguard in catalogue.items():
        in_target = safeguard["ig"] <= target_ig
        item = by_id.get(safeguard_id)
        status = item.status if item else ImplementationStatus.not_implemented
        if item is not None:
            answered += 1

        # Every group gets its own readiness figure, so IG1 can be reported on its own.
        by_ig[safeguard["ig"]].add(status)

        if not in_target:
            continue
        overall.add(status)
        by_control[safeguard["control"]].add(status)
        if safeguard["security_function"]:
            by_function[safeguard["security_function"]].add(status)
        if safeguard["asset_class"]:
            by_asset[safeguard["asset_class"]].add(status)

        if status in (ImplementationStatus.not_implemented, ImplementationStatus.partial):
            gaps.append(
                {
                    "safeguard_id": safeguard_id,
                    "control": safeguard["control"],
                    "control_title": safeguard["control_title"],
                    "title": safeguard["title"],
                    "ig": safeguard["ig"],
                    "security_function": safeguard["security_function"],
                    "asset_class": safeguard["asset_class"],
                    "status": status.value,
                    "owner": item.owner if item else "",
                    "due_date": item.due_date.isoformat() if item and item.due_date else None,
                    "priority": item.priority.value if item and item.priority else None,
                    "notes": item.notes if item else "",
                    "evidence_count": len(item.evidence) if item else 0,
                }
            )

    # Lowest group first: IG1 is the floor everyone is expected to clear.
    gaps.sort(key=lambda gap: (gap["ig"], PRIORITY_ORDER[gap["priority"]], gap["safeguard_id"]))

    cumulative: dict[str, dict] = {}
    for level in (1, 2, 3):
        bucket = _Bucket()
        for ig_level in range(1, level + 1):
            source = by_ig[ig_level]
            bucket.scored += source.scored
            bucket.counted += source.counted
            bucket.not_applicable += source.not_applicable
            bucket.implemented += source.implemented
            bucket.partial += source.partial
            bucket.missing += source.missing
        cumulative[f"IG{level}"] = bucket.as_dict(level=level)

    total_in_scope = sum(1 for s in catalogue.values() if s["ig"] <= target_ig)
    assessed = sum(1 for sid, s in catalogue.items() if s["ig"] <= target_ig and sid in by_id)

    return {
        "target_ig": target_ig,
        "overall": overall.as_dict(),
        "implementation_groups": cumulative,
        "by_control": [
            {"control": control, **by_control[control].as_dict()}
            for control in sorted(by_control, key=lambda c: int(c))
        ],
        "by_function": [
            {"security_function": name, **by_function[name].as_dict()} for name in sorted(by_function)
        ],
        "by_asset_class": [
            {"asset_class": name, **by_asset[name].as_dict()} for name in sorted(by_asset)
        ],
        "gaps": gaps,
        "progress": {
            "in_scope": total_in_scope,
            "assessed": assessed,
            "answered_total": answered,
            "complete": assessed == total_in_scope,
        },
    }
