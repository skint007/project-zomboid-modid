from dataclasses import dataclass, field


@dataclass
class Mod:
    mod_id: str
    workshop_id: str
    name: str = ""
    description: str = ""
    enabled: bool = True
