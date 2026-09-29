from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ModelPricing:
    name: str
    input_cost_credits: Decimal | None
    output_cost_credits: Decimal | None
    cached_input_cost_credits: Decimal | None = None
    cache_write_cost_credits: Decimal | None = None
    release_status: str = ""
    category: str = ""
    tier: str = ""
    threshold: str = ""
    provider: str = ""
    usd_per_credit: Decimal | None = None
    artificial_analysis_url: str = ""
    is_reasoning: bool = False
    context_window: str = ""

    @property
    def input_cost_usd(self) -> Decimal | None:
        return self._credits_to_usd(self.input_cost_credits)

    @property
    def cached_input_cost_usd(self) -> Decimal | None:
        return self._credits_to_usd(self.cached_input_cost_credits)

    @property
    def cache_write_cost_usd(self) -> Decimal | None:
        return self._credits_to_usd(self.cache_write_cost_credits)

    @property
    def output_cost_usd(self) -> Decimal | None:
        return self._credits_to_usd(self.output_cost_credits)

    def _credits_to_usd(self, value: Decimal | None) -> Decimal | None:
        if value is None or self.usd_per_credit is None:
            return None
        return value * self.usd_per_credit

    @property
    def context_label(self) -> str:
        parts: list[str] = []
        if self.threshold and self.threshold.casefold() != "not applicable":
            parts.append(self.threshold)
        if self.tier:
            tier_short = "Long" if "long" in self.tier.casefold() else "Def"
            parts.append(f"({tier_short})")
        if parts:
            return " ".join(parts)
        if self.tier:
            return self.tier
        if self.context_window:
            return f"{self.context_window} (Std)"
        return "Standard"

    @property
    def reasoning_label(self) -> str:
        return "Reasoning" if self.is_reasoning else "Standard"
