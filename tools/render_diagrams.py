"""Render the repository's supported Mermaid subset to deterministic SVG.

The initial repository avoids a Node dependency. It supports the flowchart and
sequence-diagram forms used by the gold-standard fixture. A later renderer may
delegate to Mermaid CLI without changing source files or output locations.
"""

from __future__ import annotations

import argparse
import html
import re
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


def discover_sources(root: Path) -> Iterable[Tuple[str, Path]]:
    for source_path in sorted(
        (root / "content" / "system-design").glob("*/diagrams/*.mmd")
    ):
        yield source_path.parents[1].name, source_path


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    root = args.root.resolve()

    rendered = 0
    for question_id, source_path in discover_sources(root):
        svg = render_source(source_path.read_text(encoding="utf-8"))
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
        raise SystemExit("no Mermaid sources found")
    print(f"rendered {rendered} diagram(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
