#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from xml.etree import ElementTree as ET


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: update_coverage_badge.py <coverage.xml> <output.svg>", file=sys.stderr)
        return 2

    coverage_xml = Path(sys.argv[1])
    output_svg = Path(sys.argv[2])

    if not coverage_xml.exists():
        print(f"Coverage XML not found: {coverage_xml}", file=sys.stderr)
        return 2

    tree = ET.parse(coverage_xml)
    root = tree.getroot()
    line_rate = float(root.attrib.get("line-rate", "0"))
    percent = max(0, min(100, int(round(line_rate * 100))))

    color = "#4c1" if percent >= 80 else "#dfb317" if percent >= 60 else "#e05d44"
    output_svg.parent.mkdir(parents=True, exist_ok=True)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="128" height="20" role="img" '
        f'aria-label="coverage: {percent}%">\n'
        '  <linearGradient id="b" x2="0" y2="1">\n'
        '    <stop offset="0" stop-color="#bbb" stop-opacity="0.1"/>\n'
        '    <stop offset="1" stop-opacity="0.1"/>\n'
        "  </linearGradient>\n"
        '  <mask id="a">\n'
        '    <rect width="128" height="20" rx="3" fill="#fff"/>\n'
        "  </mask>\n"
        '  <g mask="url(#a)">\n'
        '    <path fill="#555" d="M0 0h61v20H0z"/>\n'
        f'    <path fill="{color}" d="M61 0h67v20H61z"/>\n'
        '    <path fill="url(#b)" d="M0 0h128v20H0z"/>\n'
        "  </g>\n"
        '  <g fill="#fff" text-anchor="middle" '
        'font-family="DejaVu Sans,Verdana,Geneva,sans-serif" font-size="11">\n'
        '    <text x="30.5" y="14">coverage</text>\n'
        f'    <text x="94.5" y="14">{percent}%</text>\n'
        "  </g>\n"
        "</svg>\n"
    )
    output_svg.write_text(svg, encoding="utf-8")
    print(f"Wrote coverage badge to {output_svg} with {percent}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
