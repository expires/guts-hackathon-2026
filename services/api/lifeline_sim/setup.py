"""Life setup that `CharacterSpec` cannot hold. Used by "Test it" scenarios (ADR 0018).

The setup is part of the replay input, so it lives in the stored `Life`: the first history entry
(`decision_id=None`, `event_id=None`) carries it in `choice_id`, for example
`setup/scenario?deal_end=2022&focus=mortgage_deal_end`. A life without that entry has the
empty setup, so every life created before this module replays exactly as before.

Fields:
- `deal_end_year`: the year the starting mortgage fix ends. The deal-end event fires in that year.
- `focus`: template tags that always fire when the data gives them any chance (see params.FOCUS_*).
- `focus_until`: the scenario's end year. Focus (forcing, the cap exemption and the cooldown
  bypass) applies only up to that year. After it, the life plays by the normal rules.
- `path`: student start path id (ADR 0052, `lifeline_sim.paths`), for example `uni`.
- `quick`: Quick Life (ages 18 to 25 in 5 or 6 AGE taps, 2 or 3 events). Needs `path`.
"""

from __future__ import annotations

from dataclasses import dataclass

SETUP_PREFIX = "setup/scenario"


@dataclass(frozen=True)
class Setup:
    deal_end_year: int | None = None
    focus: tuple[str, ...] = ()
    focus_until: int | None = None
    path: str | None = None
    quick: bool = False

    @property
    def empty(self) -> bool:
        return self.deal_end_year is None and not self.focus and self.path is None

    def encode(self) -> str:
        """Canonical text form. Empty setup gives ''."""
        if self.empty:
            return ""
        parts: list[str] = []
        if self.deal_end_year is not None:
            parts.append(f"deal_end={self.deal_end_year}")
        if self.focus:
            parts.append("focus=" + ",".join(sorted(set(self.focus))))
            if self.focus_until is not None:
                parts.append(f"until={self.focus_until}")
        if self.path is not None:
            parts.append(f"path={self.path}")
            if self.quick:
                parts.append("quick=1")
        return f"{SETUP_PREFIX}?{'&'.join(parts)}"

    @staticmethod
    def decode(text: str | None) -> Setup:
        if not text or not text.startswith(SETUP_PREFIX + "?"):
            return Setup()
        deal_end: int | None = None
        focus: tuple[str, ...] = ()
        until: int | None = None
        path: str | None = None
        quick = False
        for part in text[len(SETUP_PREFIX) + 1 :].split("&"):
            key, _, value = part.partition("=")
            if key == "deal_end" and value.lstrip("-").isdigit():
                deal_end = int(value)
            elif key == "focus" and value:
                focus = tuple(sorted({v for v in value.split(",") if v}))
            elif key == "until" and value.isdigit():
                until = int(value)
            elif key == "path" and value:
                path = value
            elif key == "quick":
                quick = value == "1"
        return Setup(
            deal_end_year=deal_end,
            focus=focus,
            focus_until=until if focus else None,
            path=path,
            quick=quick and path is not None,
        )
