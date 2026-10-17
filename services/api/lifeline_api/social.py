"""File-backed store for the friends leaderboard: display names, invite codes and friendships.

Lives in <CREDENTIALS_DIR>/social.json (0600, atomic writes), so it survives `uvicorn --reload` restarts.
Holds no money data at all. One process, guarded by an asyncio lock.
"""

from __future__ import annotations

import asyncio
import json
import logging
import secrets
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from lifeline_contracts.friends import INVITE_ALPHABET, INVITE_LENGTH
from lifeline_data.providers.store import write_private_json

log = logging.getLogger(__name__)


def new_invite_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(INVITE_LENGTH))


def normalise_code(raw: str) -> str:
    return "".join(raw.split()).upper()


@dataclass
class SocialProfile:
    friend_id: str
    display_name: str | None
    share_mix: bool
    invite_code: str


class SocialStore:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.lock = asyncio.Lock()
        self._profiles: dict[str, SocialProfile] = {}
        self._pairs: set[frozenset[str]] = set()
        self._load()

    # ---- persistence ----

    def _load(self) -> None:
        try:
            raw: Any = json.loads(self.path.read_text())
            profiles = {s: SocialProfile(**p) for s, p in raw.get("profiles", {}).items()}
            pairs = {frozenset(p) for p in raw.get("friendships", []) if len(p) == 2}
        except FileNotFoundError:
            return
        except (OSError, ValueError, TypeError, AttributeError):
            log.warning("social store unreadable; starting empty")
            return
        self._profiles, self._pairs = profiles, pairs

    def _save(self) -> None:
        write_private_json(
            self.path,
            {
                "profiles": {s: asdict(p) for s, p in self._profiles.items()},
                "friendships": sorted(sorted(p) for p in self._pairs),
            },
        )

    # ---- reads (call inside `async with store.lock` or accept a stale read) ----

    def profile(self, sub: str) -> SocialProfile | None:
        return self._profiles.get(sub)

    def subject_for_code(self, code: str) -> str | None:
        want = normalise_code(code)
        return next((s for s, p in self._profiles.items() if p.invite_code == want), None)

    def subject_for_friend_id(self, friend_id: str) -> str | None:
        return next((s for s, p in self._profiles.items() if p.friend_id == friend_id), None)

    def friends_of(self, sub: str) -> list[str]:
        return sorted(next(iter(p - {sub})) for p in self._pairs if sub in p)

    # ---- writes ----

    def ensure(self, sub: str) -> SocialProfile:
        p = self._profiles.get(sub)
        if p is None:
            p = SocialProfile(
                friend_id=f"fr_{secrets.token_hex(8)}",
                display_name=None,
                share_mix=False,
                invite_code=self._fresh_code(),
            )
            self._profiles[sub] = p
            self._save()
        return p

    def _fresh_code(self) -> str:
        used = {p.invite_code for p in self._profiles.values()}
        while (code := new_invite_code()) in used:
            pass
        return code

    def rotate_code(self, sub: str) -> SocialProfile:
        p = self.ensure(sub)
        p.invite_code = self._fresh_code()
        self._save()
        return p

    def set_settings(self, sub: str, display_name: str, share_mix: bool) -> SocialProfile:
        p = self.ensure(sub)
        p.display_name, p.share_mix = display_name, share_mix
        self._save()
        return p

    def add_friendship(self, a: str, b: str) -> bool:
        pair = frozenset((a, b))
        if len(pair) != 2 or pair in self._pairs:
            return False
        self._pairs.add(pair)
        self._save()
        return True

    def remove_friendship(self, a: str, b: str) -> bool:
        pair = frozenset((a, b))
        if pair not in self._pairs:
            return False
        self._pairs.discard(pair)
        self._save()
        return True
