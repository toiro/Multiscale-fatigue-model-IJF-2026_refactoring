from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CalculationDiagnostic:
    """An observed calculation event with its location and values."""

    reason: str
    context: dict[str, object] = field(default_factory=dict)
    message: str | None = None  # Original technical exception detail, when present.


class CrackLifeDiagnosticError(RuntimeError):
    """Calculation stopped at a diagnosable invalid numerical state."""

    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.context = context

    def diagnostic(self) -> CalculationDiagnostic:
        return CalculationDiagnostic(
            reason=type(self).__name__,
            message=str(self),
            context=dict(self.context),
        )


class WeightFunctionDomainError(CrackLifeDiagnosticError):
    """Calculation reached outside the supported weight-function domain."""
