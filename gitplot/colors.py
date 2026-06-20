"""Color scheme for gitplot graph nodes."""

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeColors:
    line: str  # HSV string for border/line
    fill: str  # HSV string for fill


# Object types in display order; hues are evenly spaced around the HSV wheel.
_TYPES = [
    "ref",
    "tag",
    "commit",
    "commit_summary",
    "tree",
    "blob",
    "staged_changes",
    "unstaged_changes",
    "untracked_file",
    "new_node",
]

_HIGHLIGHT_HUE = 0.15  # golden yellow for newly added nodes

SCHEME: dict[str, NodeColors] = {}
_step = 1.0 / (len(_TYPES) - 1)  # reserve last slot for highlight
for _i, _t in enumerate(_TYPES[:-1]):
    _hue = _i * _step
    SCHEME[_t] = NodeColors(
        line=f"{_hue:.3f} 1.000 1.000",
        fill=f"{_hue:.3f} 0.100 1.000",
    )

SCHEME["new_node"] = NodeColors(
    line=f"{_HIGHLIGHT_HUE:.3f} 1.000 1.000",
    fill=f"{_HIGHLIGHT_HUE:.3f} 0.400 1.000",
)
