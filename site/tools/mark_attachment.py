"""Transport Limn's frozen combining drawings into explicit OpenType attachment layout.

The semantic coordinates come from accents.py: an o-wide reference before the
origin, optical top/bottom ink bands, separate attached marks and baseline overlay.
This module only emits features; it never changes a drawing, advance or hint.
"""

import unicodedata

import pathops
from fontTools.misc.roundTools import otRound
from fontTools.pens.basePen import BasePen

__all__ = ["attachment_features"]

ABOVE = frozenset(range(0x0300, 0x030D)) | {0x0312}
BELOW = frozenset({0x0323, 0x0326, 0x0327, 0x0328})
ROLES = {
    **dict.fromkeys(ABOVE, "above"),
    **dict.fromkeys(BELOW, "below"),
    0x031B: "horn",
    0x0328: "ogonek",
    0x0335: "overlay",
}


class _FlatPen(BasePen):
    """Flatten final quadratic outlines for the source rule's 24-step optical slices."""

    def __init__(self, glyph):
        """Read a simple exported glyph without modifying its coordinates."""
        super().__init__(None)
        self.polygons = []
        self.current = []
        glyph.draw(self, None)

    def _moveTo(self, point):
        """Start one contour; close/end stores it for even-odd slicing."""
        self.current = [point]

    def _lineTo(self, point):
        """Retain a line endpoint exactly."""
        self.current.append(point)

    def _qCurveToOne(self, control, end):
        """Sample a quadratic using the same resolution as build_font.polylines."""
        start = self.current[-1]
        for index in range(1, 25):
            t = index / 24
            self.current.append(
                tuple((1 - t) ** 2 * start[k] + 2 * (1 - t) * t * control[k] + t * t * end[k] for k in (0, 1))
            )

    def _closePath(self):
        """Finish a closed contour; glyph outlines never carry open contours."""
        self.polygons.append(self.current)
        self.current = []

    def _endPath(self):
        """Retain an explicit end contour for the same bounded slice operation."""
        self._closePath()


def _slice(polygons, y):
    """Return even-odd ink intervals at y, matching accents.py's source sampling."""
    xs = []
    for polygon in polygons:
        for index, (x0, y0) in enumerate(polygon):
            x1, y1 = polygon[(index + 1) % len(polygon)]
            if y0 <= y < y1 or y1 <= y < y0:
                xs.append(x0 + (y - y0) * (x1 - x0) / (y1 - y0))
    xs.sort()
    return list(zip(xs[::2], xs[1::2]))


def _band(polygons, y0, y1, fallback):
    """Find the optical centre of seven source-rule slices, falling back only for empty bands."""
    xs = [x for k in range(7) for interval in _slice(polygons, y0 + (y1 - y0) * (k + 0.5) / 7) for x in interval]
    return (min(xs) + max(xs)) / 2 if xs else fallback


def _top_x(glyph, char, polygons, xheight):
    """Use the a/g bowl counter or the source's top-quarter ink band."""
    if char in "ag":
        path = pathops.Path()
        glyph.draw(path.getPen(), None)
        contours = list(path.contours)
        if len(contours) > 1:
            outer = max(contours, key=lambda contour: abs(contour.area))
            holes = [contour for contour in contours if contour.clockwise != outer.clockwise]
            if holes:
                bounds = max(holes, key=lambda contour: abs(contour.area)).bounds
                return (bounds[0] + bounds[2]) / 2
    return _band(polygons, glyph.yMax - 0.25 * xheight, glyph.yMax - 1, (glyph.xMin + glyph.xMax) / 2)


def _horn(glyph, char, polygons, stem):
    """Locate the top-right stroke's centre, the horn_of construction's actual join point."""
    if char in "oO":
        x = glyph.xMax - 0.30 * (glyph.xMax - glyph.xMin)
    else:
        intervals = _slice(polygons, glyph.yMax - 0.5 * stem - 2)
        x = max(((a + b) / 2 for a, b in intervals), default=(glyph.xMin + glyph.xMax) / 2)
    # Transpose the existing flattened polygons to sample the vertical ink column.
    intervals = _slice([[(y, px) for px, y in polygon] for polygon in polygons], x)
    low, high = max(intervals, key=lambda interval: interval[1], default=(glyph.yMax - stem, glyph.yMax))
    return x, (low + high) / 2 if char in "oO" else high - 0.5 * stem


def _anchor(point):
    """Quantize semantic source coordinates once using the exporter/OpenType rounding rule."""
    return f"<anchor {otRound(point[0])} {otRound(point[1])}>"


def attachment_features(glyphs: dict, chars: dict[str, str], data: dict) -> str:
    """Emit mark/mkmk and pin-replacing ccmp for the existing admitted glyphs.

    Inputs are the Weight's final simple glyphs and source metadata. Unknown Mn
    drawings are rejected rather than silently receiving a guessed attachment.
    Empty/space, modern Hangul syllables and conjoining jamo receive no new rules.
    """
    marks = {name: ROLES[ord(char)] for name, char in chars.items() if unicodedata.category(char) == "Mn"}
    if not marks:
        return ""
    xh, gap, stem = data["xh"], data["pin"]["dotgap"], data["s"]
    reference_x, reference_y = -data["glyphs"]["o"]["adv"] / 2, xh + gap
    names = {char: name for name, char in chars.items() if "." not in name}
    polygons = {
        name: _FlatPen(glyph).polygons for name, glyph in glyphs.items() if glyph.numberOfContours and name != ".notdef"
    }
    o = glyphs[names["o"]]
    horn_x, horn_y = _horn(o, "o", polygons[names["o"]], stem)
    references = {
        "above": (reference_x, reference_y),
        "below": (reference_x, 0),
        "horn": (horn_x - data["glyphs"]["o"]["adv"], horn_y),
        "overlay": (reference_x, xh / 2),
    }
    anchors = {}
    for name, role in marks.items():
        char = chars[name]
        anchors[name] = (
            (-0.2 * data["glyphs"]["o"]["adv"] - 0.87 * stem / 2, 0.87 * stem / 2)
            if char == "\u0328"
            else references[role]
        )
    out = []
    for role in ("above", "below", "ogonek", "horn", "overlay"):
        group = sorted(name for name, value in marks.items() if value == role)
        if group:
            out.append(f"@{role}Marks = [{' '.join(group)}];")
        for name in group:
            out.append(f"markClass {name} {_anchor(anchors[name])} @{role};")
    if "above" in marks.values():
        out += ["feature ccmp {", "  lookup remove_pin {", "    lookupflag UseMarkFilteringSet @aboveMarks;"]
        # Shapers may first compose i+below into į/ị. Decompose only in this
        # above-mark context, reusing the encoded dotless and below glyphs.
        for char, name in names.items():
            decomposition = unicodedata.normalize("NFD", char)
            if (
                len(decomposition) > 1
                and decomposition[0] in "ij"
                and all(ord(mark) in BELOW and mark in names for mark in decomposition[1:])
            ):
                dotless = "ı" if decomposition[0] == "i" else "ȷ"
                if dotless in names:
                    replacement = [names[dotless]] + [names[mark] for mark in decomposition[1:]]
                    out.append(f"    sub {name}' @aboveMarks by {' '.join(replacement)};")
        for char, dotless in (("i", "ı"), ("j", "ȷ")):
            if char in names and dotless in names:
                out.append(f"    sub {names[char]}' @aboveMarks by {names[dotless]};")
        out += ["  } remove_pin;", "} ccmp;"]
    out.append("feature mark {")
    for name, glyph in glyphs.items():
        if (
            name not in polygons
            or name in marks
            or any(0x1100 <= ord(c) <= 0x11FF or 0xAC00 <= ord(c) <= 0xD7AF for c in chars.get(name, ""))
        ):
            continue
        char = chars.get(name, "")
        plain = unicodedata.normalize("NFD", char)[:1]
        bare_name = names.get(plain, name) if "." not in name else name
        bare = glyphs[bare_name]
        above_x = _top_x(bare, plain, polygons[bare_name], xh)
        # Precomposed letters retain their own ink: an additional mark clears it.
        precomposed = len(unicodedata.normalize("NFD", char)) > 1
        if precomposed:
            above_y = glyph.yMax + gap
        elif char.isupper():
            above_y = data["cap"] + 0.75 * gap
        elif glyph.yMax > (data["xo"] + data["cap"]) / 2:
            above_y = glyph.yMax + 0.75 * gap
        else:
            above_y = reference_y
        floor = glyph.yMin if glyph.yMin < -0.1 * xh else 0
        below_x = _band(polygons[name], floor + 1, floor + 0.2 * xh, (glyph.xMin + glyph.xMax) / 2)
        join = _slice(polygons[name], floor + 0.87 * stem / 2)
        ogonek_x = max((b for _, b in join), default=glyph.xMax) - 0.87 * stem / 2
        horn = _horn(glyph, char, polygons[name], stem)
        out.append(f"  pos base {name}")
        for role in sorted(set(marks.values())):
            point = {
                "above": (above_x, above_y),
                "below": (below_x, floor),
                "horn": horn,
                "ogonek": (ogonek_x, floor + 0.87 * stem / 2),
                "overlay": ((glyph.xMin + glyph.xMax) / 2, (glyph.yMin + glyph.yMax) / 2),
            }[role]
            out.append(f"    {_anchor(point)} mark @{role}")
        out[-1] += ";"
    out.append("} mark;")
    # Each attachment role filters out other roles so above/below can interleave.
    white = max(0.35 * gap, 0.25 * stem)
    out.append("feature mkmk {")
    families = {"above": {"above", "horn"}, "below": {"below", "ogonek"}, "horn": {"horn"}}
    for role in ("above", "below", "horn"):
        incoming = {"above": {"above"}, "below": {"below", "ogonek"}, "horn": {"horn"}}[role] & set(marks.values())
        group = [name for name, value in marks.items() if value in families[role]]
        if not group or not incoming:
            continue
        out += [f"  lookup stack_{role} {{", f"    lookupflag UseMarkFilteringSet [{' '.join(sorted(group))}];"]
        for name in group:
            glyph = glyphs[name]
            x, y = anchors[name]
            out.append(f"    pos mark {name}")
            for target in sorted(incoming):
                next_marks = [n for n, value in marks.items() if value == target]
                if role == "above":
                    delta = min(glyphs[n].yMin - anchors[n][1] for n in next_marks)
                    point = (reference_x, glyph.yMax + white - delta)
                elif role == "below":
                    delta = max(glyphs[n].yMax - anchors[n][1] for n in next_marks)
                    point = (x, glyph.yMin - white - delta)
                else:
                    point = (x + glyph.xMax - glyph.xMin + white, y)
                out.append(f"      {_anchor(point)} mark @{target}")
            out[-1] += ";"
        out.append(f"  }} stack_{role};")
    out.append("} mkmk;")
    return "\n".join(out)
