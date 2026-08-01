from ai_enterprise.domain.review.policies import ReviewFinding


class FindingNormalizer:
    def from_review_container(
        self,
        *,
        findings: list[dict],
    ) -> tuple[ReviewFinding, ...]:
        return tuple(
            ReviewFinding(
                rule_id=str(item.get("rule_id", "review_agent")),
                category=str(item.get("category", "general")),
                severity=item.get("severity", "low"),
                title=str(item.get("title", "Finding")),
                description=str(item.get("description", "")),
                blocking=bool(item.get("blocking", False)),
                file_path=item.get("file_path"),
                line_start=item.get("line_start"),
                line_end=item.get("line_end"),
                evidence=item.get("evidence"),
            )
            for item in findings
        )
