"""Render diagram sources to deterministic SVG.

Two source formats are supported:

* ``*.mmd`` -- the repository's original Mermaid subset (flowchart and sequence
  diagrams without edge labels). Kept for existing packages.
* ``*.dot`` -- Graphviz sources rendered with ``dot``. System-design chapters
  use these because they need edge labels, grouping, and highlighted "new in
  this step" components. The handbook palette is injected as default graph,
  node, and edge attributes, and ``role=...`` shorthands expand to palette
  attributes, so sources stay short and every figure looks like one book.

Graphviz output is deterministic for a given Graphviz version. The SVG records
that version in a header comment; validation compares sources to SVGs only when
the local version matches (see ``graphviz_version_of``).
"""

from __future__ import annotations

import argparse
import html
import re
import shutil
import subprocess
from collections import defaultdict, deque
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "generated" / "diagrams"

FLOW_EDGE = re.compile(
    r'^\s*([A-Za-z0-9_]+)\["([^"]+)"\]\s*'
    r'(-->|-.->)\s*([A-Za-z0-9_]+)\["([^"]+)"\]\s*$'
)
PARTICIPANT = re.compile(r"^\s*participant\s+([A-Za-z0-9_]+)\s+as\s+(.+?)\s*$")
MESSAGE = re.compile(
    r"^\s*([A-Za-z0-9_]+)\s*(-?--?>>?)\s*([A-Za-z0-9_]+)\s*:\s*(.+?)\s*$"
)


def _svg_text(x: float, y: float, text: str, *, anchor: str = "middle") -> str:
    return (
        f'<text x="{x:.0f}" y="{y:.0f}" text-anchor="{anchor}" '
        'font-family="Arial, sans-serif" font-size="14" fill="#172033">'
        f"{html.escape(text)}</text>"
    )


def _wrap_label(label: str, limit: int = 24) -> List[str]:
    words = label.split()
    lines: List[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > limit:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines or [label]


def render_flowchart(lines: Sequence[str]) -> str:
    nodes: Dict[str, str] = {}
    edges: List[Tuple[str, str, str]] = []
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        match = FLOW_EDGE.match(line)
        if not match:
            raise ValueError(f"unsupported flowchart line: {stripped}")
        left, left_label, arrow, right, right_label = match.groups()
        nodes[left] = left_label
        nodes[right] = right_label
        edges.append((left, right, arrow))

    if not nodes or not edges:
        raise ValueError("flowchart must contain at least one edge")

    incoming = {node: 0 for node in nodes}
    outgoing: Dict[str, List[str]] = defaultdict(list)
    for left, right, _ in edges:
        outgoing[left].append(right)
        incoming[right] += 1

    levels = {node: 0 for node in nodes}
    queue = deque(sorted(node for node, count in incoming.items() if count == 0))
    visited = set()
    while queue:
        node = queue.popleft()
        visited.add(node)
        for child in outgoing[node]:
            levels[child] = max(levels[child], levels[node] + 1)
            incoming[child] -= 1
            if incoming[child] == 0:
                queue.append(child)
    if len(visited) != len(nodes):
        raise ValueError("initial flowchart renderer requires an acyclic graph")

    by_level: Dict[int, List[str]] = defaultdict(list)
    for node, level in levels.items():
        by_level[level].append(node)
    for level_nodes in by_level.values():
        level_nodes.sort()

    box_width = 190
    box_height = 64
    x_gap = 70
    y_gap = 32
    margin = 40
    max_rows = max(len(items) for items in by_level.values())
    maximum_level = max(levels.values())
    width = (
        margin * 2
        + (maximum_level + 1) * box_width
        + maximum_level * x_gap
    )
    height = margin * 2 + max_rows * box_height + max(max_rows - 1, 0) * y_gap

    positions: Dict[str, Tuple[float, float]] = {}
    for level, level_nodes in sorted(by_level.items()):
        column_height = len(level_nodes) * box_height + max(
            len(level_nodes) - 1, 0
        ) * y_gap
        start_y = (height - column_height) / 2
        for row, node in enumerate(level_nodes):
            x = margin + level * (box_width + x_gap)
            y = start_y + row * (box_height + y_gap)
            positions[node] = (x, y)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        'role="img" aria-labelledby="title desc">',
        "<title id=\"title\">Market data architecture</title>",
        (
            '<desc id="desc">Architecture diagram rendered from checked-in '
            "Mermaid source.</desc>"
        ),
        "<defs>",
        (
            '<marker id="arrow" markerWidth="10" markerHeight="7" refX="9" '
            'refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" '
            'fill="#52627a"/></marker>'
        ),
        "</defs>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]

    for left, right, arrow in edges:
        left_x, left_y = positions[left]
        right_x, right_y = positions[right]
        x1 = left_x + box_width
        y1 = left_y + box_height / 2
        x2 = right_x
        y2 = right_y + box_height / 2
        dash = ' stroke-dasharray="7 5"' if arrow == "-.->" else ""
        parts.append(
            f'<line x1="{x1:.0f}" y1="{y1:.0f}" x2="{x2:.0f}" '
            f'y2="{y2:.0f}" stroke="#52627a" stroke-width="2"{dash} '
            'marker-end="url(#arrow)"/>'
        )

    for node, label in nodes.items():
        x, y = positions[node]
        parts.append(
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{box_width}" '
            f'height="{box_height}" rx="8" fill="#edf4ff" '
            'stroke="#315b8a" stroke-width="2"/>'
        )
        wrapped = _wrap_label(label)
        first_y = y + box_height / 2 - (len(wrapped) - 1) * 9 + 5
        for line_index, text in enumerate(wrapped):
            parts.append(
                _svg_text(
                    x + box_width / 2,
                    first_y + line_index * 18,
                    text,
                )
            )

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_sequence(lines: Sequence[str]) -> str:
    participants: List[Tuple[str, str]] = []
    messages: List[Tuple[str, str, str, str]] = []
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped or stripped.startswith("%%"):
            continue
        participant = PARTICIPANT.match(line)
        if participant:
            participants.append(participant.groups())
            continue
        message = MESSAGE.match(line)
        if message:
            messages.append(message.groups())
            continue
        raise ValueError(f"unsupported sequence-diagram line: {stripped}")

    if len(participants) < 2 or not messages:
        raise ValueError("sequence diagram requires participants and messages")

    aliases = [alias for alias, _ in participants]
    if any(source not in aliases or target not in aliases for source, _, target, _ in messages):
        raise ValueError("sequence message references an undeclared participant")

    margin = 50
    spacing = 220
    header_y = 25
    header_height = 54
    message_gap = 56
    width = margin * 2 + spacing * (len(participants) - 1) + 160
    height = 130 + message_gap * len(messages)
    x_by_alias = {
        alias: margin + 80 + index * spacing
        for index, (alias, _) in enumerate(participants)
    }

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="0 0 {width} {height}" '
        'role="img" aria-labelledby="title desc">',
        '<title id="title">Gap recovery sequence</title>',
        (
            '<desc id="desc">Sequence diagram rendered from checked-in '
            "Mermaid source.</desc>"
        ),
        "<defs>",
        (
            '<marker id="arrow" markerWidth="10" markerHeight="7" refX="9" '
            'refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" '
            'fill="#52627a"/></marker>'
        ),
        "</defs>",
        '<rect width="100%" height="100%" fill="#ffffff"/>',
    ]

    for alias, label in participants:
        x = x_by_alias[alias]
        parts.append(
            f'<rect x="{x - 80}" y="{header_y}" width="160" '
            f'height="{header_height}" rx="8" fill="#edf4ff" '
            'stroke="#315b8a" stroke-width="2"/>'
        )
        parts.append(_svg_text(x, header_y + 33, label))
        parts.append(
            f'<line x1="{x}" y1="{header_y + header_height}" x2="{x}" '
            f'y2="{height - 30}" stroke="#9aa8ba" stroke-width="1.5" '
            'stroke-dasharray="6 5"/>'
        )

    for index, (source, arrow, target, label) in enumerate(messages):
        y = 110 + index * message_gap
        x1 = x_by_alias[source]
        x2 = x_by_alias[target]
        dash = ' stroke-dasharray="7 5"' if "--" in arrow else ""
        if x1 == x2:
            parts.append(
                f'<path d="M {x1} {y} h 70 v 24 h -70" fill="none" '
                f'stroke="#52627a" stroke-width="2"{dash} '
                'marker-end="url(#arrow)"/>'
            )
            parts.append(_svg_text(x1 + 35, y - 8, label))
        else:
            direction = 1 if x2 > x1 else -1
            parts.append(
                f'<line x1="{x1}" y1="{y}" x2="{x2 - direction * 8}" '
                f'y2="{y}" stroke="#52627a" stroke-width="2"{dash} '
                'marker-end="url(#arrow)"/>'
            )
            parts.append(_svg_text((x1 + x2) / 2, y - 8, label))

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def render_source(source: str) -> str:
    lines = source.splitlines()
    first = next((line.strip() for line in lines if line.strip()), "")
    if first.startswith("flowchart "):
        return render_flowchart(lines)
    if first == "sequenceDiagram":
        return render_sequence(lines)
    raise ValueError(f"unsupported Mermaid diagram declaration: {first!r}")


# --------------------------------------------------------------------------
# Graphviz (.dot) support
# --------------------------------------------------------------------------

PALETTE = {
    "ink": "#1f2328",
    "muted": "#6b7280",
    "rule": "#9aa4b2",
    "fill": "#f3f4f6",
    "accent": "#1a6fb5",
    "accent_fill": "#dbeafe",
    "warn": "#b5501a",
    "warn_fill": "#fde8d7",
    "ok": "#2f7a4f",
    "ok_fill": "#e3f1e8",
}

DOT_DEFAULTS = {
    "G": {
        "rankdir": "LR",
        "bgcolor": "white",
        "pad": "0.3",
        "nodesep": "0.45",
        "ranksep": "0.65",
        "fontname": "Helvetica",
        "fontsize": "12",
        "fontcolor": PALETTE["muted"],
    },
    "N": {
        "shape": "box",
        "style": "rounded,filled",
        "fillcolor": PALETTE["fill"],
        "color": PALETTE["rule"],
        "penwidth": "1.2",
        "fontname": "Helvetica",
        "fontsize": "14",
        "fontcolor": PALETTE["ink"],
        "margin": "0.18,0.10",
    },
    "E": {
        "color": PALETTE["muted"],
        "penwidth": "1.2",
        "arrowsize": "0.7",
        "fontname": "Helvetica",
        "fontsize": "12",
        "fontcolor": "#4b5563",
    },
}

NODE_ROLES = {
    "new": {"fillcolor": PALETTE["accent_fill"], "color": PALETTE["accent"], "penwidth": "1.8"},
    "warn": {"fillcolor": PALETTE["warn_fill"], "color": PALETTE["warn"], "penwidth": "1.6"},
    "ok": {"fillcolor": PALETTE["ok_fill"], "color": PALETTE["ok"], "penwidth": "1.6"},
    "store": {"shape": "cylinder"},
    "ext": {"style": "rounded,filled,dashed", "fillcolor": "#ffffff"},
    "note": {"shape": "note", "fillcolor": "#ffffff", "fontcolor": PALETTE["muted"], "fontsize": "11"},
}

EDGE_ROLES = {
    "new": {"color": PALETTE["accent"], "fontcolor": PALETTE["accent"], "penwidth": "1.8"},
    "warn": {"color": PALETTE["warn"], "fontcolor": PALETTE["warn"], "penwidth": "1.5"},
    "ok": {"color": PALETTE["ok"], "fontcolor": PALETTE["ok"], "penwidth": "1.5"},
    "async": {"style": "dashed"},
}

ZONE_ATTRS = (
    'style="rounded,dashed"; color="#9aa4b2"; fontcolor="#6b7280"; '
    'fontsize=12; labeljust=l; margin=12;'
)

ROLE_IN_LIST = re.compile(r'\brole\s*=\s*(?:"([a-z ,]+)"|([a-z]+))')
ZONE_STATEMENT = re.compile(r'\brole\s*=\s*zone\s*;?')
GRAPHVIZ_VERSION = re.compile(r"Generated by graphviz version ([0-9.]+)")


def _role_attrs(roles: Sequence[str], table: Dict[str, Dict[str, str]]) -> str:
    merged: Dict[str, str] = {}
    for role in roles:
        if role not in table:
            raise ValueError(f"unknown diagram role {role!r}; expected one of {sorted(table)}")
        merged.update(table[role])
    return ", ".join(f'{key}="{value}"' for key, value in merged.items())


def expand_dot_roles(source: str) -> str:
    """Expand ``role=...`` shorthands into palette attributes."""
    out: List[str] = []
    for line in source.splitlines():
        line = ZONE_STATEMENT.sub(ZONE_ATTRS, line)
        table = EDGE_ROLES if "->" in line or "--" in line.split("[", 1)[0] else NODE_ROLES

        def replace(match: "re.Match[str]") -> str:
            raw = match.group(1) or match.group(2)
            roles = [part for part in re.split(r"[ ,]+", raw) if part]
            return _role_attrs(roles, table)

        out.append(ROLE_IN_LIST.sub(replace, line))
    return "\n".join(out) + "\n"


def graphviz_available() -> bool:
    return shutil.which("dot") is not None


def local_graphviz_version() -> Optional[str]:
    if not graphviz_available():
        return None
    result = subprocess.run(["dot", "-V"], capture_output=True, text=True, check=False)
    match = re.search(r"version ([0-9.]+)", result.stderr + result.stdout)
    return match.group(1) if match else None


def graphviz_version_of(svg: str) -> Optional[str]:
    match = GRAPHVIZ_VERSION.search(svg)
    return match.group(1) if match else None


def render_dot(source: str) -> str:
    if not graphviz_available():
        raise ValueError("Graphviz `dot` is not installed (brew install graphviz / apt install graphviz)")
    # Inject palette defaults as the first statements of the graph so the
    # source can override them (command-line -G/-N/-E flags would win instead).
    names = {"G": "graph", "N": "node", "E": "edge"}
    defaults = "".join(
        f"  {names[kind]} [" + ", ".join(f'{k}="{v}"' for k, v in attrs.items()) + "];\n"
        for kind, attrs in DOT_DEFAULTS.items()
    )
    expanded = expand_dot_roles(source)
    brace = expanded.find("{")
    if brace < 0:
        raise ValueError("Graphviz source must contain a graph body")
    expanded = expanded[: brace + 1] + "\n" + defaults + expanded[brace + 1 :]
    result = subprocess.run(
        ["dot", "-Tsvg"], input=expanded, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise ValueError(f"dot failed: {result.stderr.strip()}")
    return result.stdout


def render_path(path: Path) -> str:
    """Render one diagram source file according to its suffix."""
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".dot":
        return render_dot(text)
    return render_source(text)


def discover_sources(root: Path) -> Iterable[Tuple[str, Path]]:
    base = root / "content" / "system-design"
    sources = list(base.glob("*/diagrams/*.mmd")) + list(base.glob("*/diagrams/*.dot"))
    for source_path in sorted(sources):
        yield source_path.parents[1].name, source_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    rendered = 0
    for question_id, source_path in discover_sources(root):
        if source_path.suffix == ".dot" and not graphviz_available():
            print(f"skipped {source_path.relative_to(root)}: Graphviz `dot` not installed")
            continue
        svg = render_path(source_path)
        output_path = root / "generated" / "diagrams" / question_id / (
            source_path.stem + ".svg"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(svg, encoding="utf-8")
        print(
            f"rendered {source_path.relative_to(root)} -> "
            f"{output_path.relative_to(root)}"
        )
        rendered += 1

    if rendered == 0:
        raise SystemExit("no diagram sources found")
    print(f"rendered {rendered} diagram(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
