#!/usr/bin/env python3
from dataclasses import dataclass, asdict
from typing import List, Optional

# ── DNA / Veto Schemas ──

@dataclass
class VetoConfig:
    """Configuration for Advocate veto behavior."""
    mode: str = "soft"           # "soft" | "hard"
    threshold: float = 0.4       # alignment_score below this = veto trigger
    auto_reject: bool = False    # if True, hard veto → automatic reject
    confidence_decay: float = 0.2  # how much confidence drops on veto

    def validate(self):
        assert self.mode in ("soft", "hard"), f"Invalid veto mode: {self.mode}"
        assert 0.0 <= self.threshold <= 1.0
        assert 0.0 <= self.confidence_decay <= 1.0

@dataclass
class DNAProfile:
    """User DNA profile loaded from user_dna.json."""
    dna: str = "BALANCED"
    preferences: List[str] = None
    veto_config: VetoConfig = None

    def __post_init__(self):
        if self.preferences is None:
            self.preferences = []
        if self.veto_config is None:
            self.veto_config = VetoConfig()

    @classmethod
    def from_dict(cls, data: dict) -> 'DNAProfile':
        vc_data = data.get("veto_config", {})
        vc = VetoConfig(
            mode=vc_data.get("mode", "soft"),
            threshold=vc_data.get("threshold", 0.4),
            auto_reject=vc_data.get("auto_reject", False),
            confidence_decay=vc_data.get("confidence_decay", 0.2),
        )
        return cls(
            dna=data.get("dna", "BALANCED"),
            preferences=data.get("preferences", []),
            veto_config=vc,
        )

    def to_dict(self) -> dict:
        return {
            "dna": self.dna,
            "preferences": self.preferences,
            "veto_config": asdict(self.veto_config),
        }

@dataclass
class VetoItem:
    """Structured veto outcome from User Advocate."""
    veto: bool = False
    severity: str = "soft"        # "soft" | "hard"
    veto_reason: str = ""
    alignment_score: float = 1.0   # 0.0-1.0
    suggested_alternative: str = ""

    def validate(self):
        assert self.severity in ("soft", "hard"), f"Invalid severity: {self.severity}"
        assert 0.0 <= self.alignment_score <= 1.0

    @classmethod
    def from_dict(cls, data: dict) -> 'VetoItem':
        return cls(
            veto=bool(data.get("veto", False)),
            severity=data.get("severity", "soft"),
            veto_reason=data.get("veto_reason", data.get("reason", "")),
            alignment_score=float(data.get("alignment_score", 1.0)),
            suggested_alternative=data.get("suggested_alternative", ""),
        )

    def to_dict(self) -> dict:
        return asdict(self)


# ── Existing Critique / Verdict Schemas (unchanged below) ──

@dataclass
class CritiqueItem:
    id: str
    category: str  # Literal["security", "performance", "design"]
    severity: str  # Literal["blocker", "warning"]
    description: str
    suggested_action: str

    def validate(self):
        assert isinstance(self.id, str) and self.id, "ID must be a non-empty string"
        assert self.category in ["security", "performance", "design"], f"Invalid category: {self.category}"
        assert self.severity in ["blocker", "warning"], f"Invalid severity: {self.severity}"
        assert isinstance(self.description, str) and self.description, "Description must be a non-empty string"
        assert isinstance(self.suggested_action, str) and self.suggested_action, "Suggested action must be a non-empty string"

@dataclass
class CritiqueList:
    critiques: List[CritiqueItem]

    @classmethod
    def from_dict(cls, data: dict) -> 'CritiqueList':
        items = []
        for c in data.get("critiques", []):
            item = CritiqueItem(
                id=c.get("id", ""),
                category=c.get("category", ""),
                severity=c.get("severity", ""),
                description=c.get("description", ""),
                suggested_action=c.get("suggested_action", "")
            )
            item.validate()
            items.append(item)
        return cls(critiques=items)

    def to_dict(self) -> dict:
        return {"critiques": [asdict(c) for c in self.critiques]}

@dataclass
class VerdictResolution:
    critique_id: str
    accepted: bool
    resolution: str

    def validate(self):
        assert isinstance(self.critique_id, str) and self.critique_id, "Critique ID must be a non-empty string"
        assert isinstance(self.accepted, bool), f"Accepted must be a boolean: {self.accepted}"
        assert isinstance(self.resolution, str) and self.resolution, "Resolution must be a non-empty string"

@dataclass
class VerdictList:
    resolutions: List[VerdictResolution]

    @classmethod
    def from_dict(cls, data: dict) -> 'VerdictList':
        items = []
        for r in data.get("resolutions", []):
            # Safe parsing accepted (convert 1/0/true/false string or bool to bool)
            acc_val = r.get("accepted")
            if isinstance(acc_val, str):
                accepted = acc_val.lower() == "true"
            else:
                accepted = bool(acc_val)
            
            item = VerdictResolution(
                critique_id=r.get("critique_id", ""),
                accepted=accepted,
                resolution=r.get("resolution", "")
            )
            item.validate()
            items.append(item)
        return cls(resolutions=items)

    def to_dict(self) -> dict:
        return {"resolutions": [asdict(r) for r in self.resolutions]}
