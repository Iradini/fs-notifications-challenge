from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User():
    email: str
    user_id: int | None = None

    
