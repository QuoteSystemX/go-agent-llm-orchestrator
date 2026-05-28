#!/usr/bin/env python3
from dataclasses import dataclass, asdict
from typing import List

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
