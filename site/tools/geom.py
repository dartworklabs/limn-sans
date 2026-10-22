"""Outline geometry the build measures with (shapely): the white a glyph encloses, and outline hygiene.

  counters(p)            the widest circle that fits each counter (diameter), largest first
  open_counters(p, d, c) a counter narrower than d is opened by thinning the ink around it, never by more than c
  spikes(p)              ink narrower than 1.5 units reaching out more than 6 (a spike or a sliver, zero-width ones
                         included), white narrower than that reaching in (a crack)
  despike(p)             p without them: opened and closed with a 0.75-unit pen, only where there is one

Every counter a glyph keeps must stay open at text sizes: build_font opens the ones under COUNTER_MIN = 0.35 S by at
most 0.12 S, and the audit's gate is 0.3 S (tools/audit.py).
"""
import math

import pathops
from shapely import maximum_inscribed_circle
from shapely.geometry import Polygon

from weights import _flat, _soff

R_SPIKE, L_SPIKE = 0.75, 6.0


def shape(p, steps=8):
    """shapely geometry of a pathops outline (the contours of a simplified path do not overlap: even-odd = XOR)."""
    g = Polygon()
    for c in p.contours:
        pts = _flat(c, steps)
        if len(pts) < 3: continue
        q = Polygon(pts).buffer(0)
        if not q.is_empty:
            g = g.symmetric_difference(q)
    return g


def _pieces(g):
    return [q for q in getattr(g, "geoms", [g]) if q.geom_type == "Polygon" and not q.is_empty]


def counters(p):
    """[(diameter of the largest inscribed circle, white polygon)] of every counter, widest first."""
    g = shape(p); out = []
    for q in _pieces(g):
        for ring in q.interiors:
            wh = Polygon(ring).difference(g)
            if wh.is_empty or wh.area < 0.01:
                out.append((0.0, wh)); continue
            out.append((2 * maximum_inscribed_circle(wh, 0.05).length, wh))
    return sorted(out, key=lambda t: -t[0])


def open_counters(p, dmin, cap):
    """Thin the ink round every counter narrower than dmin until it is dmin wide (the hole grows by at most cap)."""
    for _ in range(4):
        cs = list(p.contours)
        if len(cs) < 2: return p
        big = max(cs, key=lambda c: abs(c.area))
        grown = pathops.Path(); changed = False
        for c in cs:
            if c.clockwise == big.clockwise: continue
            h = pathops.Path(); h.addPath(c); h.simplify()
            d = min_counter_of_hole(h)
            if d is None or d >= dmin - 0.5: continue
            delta = min(cap, (dmin - d) / 2 + 0.5)
            grown = pathops.op(grown, _soff(h, delta, delta), pathops.PathOp.UNION) if list(grown.contours) else _soff(h, delta, delta)
            changed = True
        if not changed: return p
        q = pathops.op(p, grown, pathops.PathOp.DIFFERENCE)
        if len(list(q.contours)) != len(cs): return p          # never cut through a stroke
        p = q
    return p


def min_counter_of_hole(h):
    g = shape(h)
    if g.is_empty: return None
    return 2 * maximum_inscribed_circle(g, 0.05).length


def _reversals(p):
    """Zero-width spikes: the outline turns straight back (more than 175 degrees) on arms longer than 2 units."""
    n = 0
    for c in p.contours:
        pts = _flat(c, 8)
        pts = [q for i, q in enumerate(pts) if i == 0 or math.dist(q, pts[i - 1]) > 1e-6]
        m = len(pts)
        for i in range(m):
            a, b, e = pts[i - 1], pts[i], pts[(i + 1) % m]
            u, v = (b[0] - a[0], b[1] - a[1]), (e[0] - b[0], e[1] - b[1])
            lu, lv = math.hypot(*u), math.hypot(*v)
            if min(lu, lv) > 2 and (u[0] * v[0] + u[1] * v[1]) / (lu * lv) < -0.9962:
                n += 1
    return n


def spikes(p):
    """[(kind, length)] of the spikes and cracks of p."""
    out = [("spike", 0.0)] * _reversals(p)
    g = shape(p)
    if g.is_empty: return out
    opened = g.buffer(-R_SPIKE, join_style="mitre").buffer(R_SPIKE, join_style="round")
    closed = g.buffer(R_SPIKE, join_style="round").buffer(-R_SPIKE, join_style="mitre")
    for kind, geo in (("spike", g.difference(opened)), ("crack", closed.difference(g))):
        for q in _pieces(geo) if not geo.is_empty else []:
            b = q.bounds; L = math.hypot(b[2] - b[0], b[3] - b[1])
            if L > L_SPIKE and q.area > 0.5 and q.area / L > 0.05: out.append((kind, L))   # not the buffers' own rounding
    return out


def despike(p):
    """p opened and closed with a pen of R_SPIKE, where its simplified outline (what the font files take) has a spike
    or a crack (a 0.75-unit round on its corners and nothing else changes); p itself otherwise."""
    s = pathops.Path(p); s.simplify()
    if not spikes(s): return p
    p = s
    q = _soff(_soff(p, -R_SPIKE, -R_SPIKE), R_SPIKE, R_SPIKE)
    q = _soff(_soff(q, R_SPIKE, R_SPIKE), -R_SPIKE, -R_SPIKE)
    q.simplify()
    if len(list(q.contours)) != len(list(p.contours)) or abs(abs(q.area) - abs(p.area)) > 0.01 * abs(p.area) + 20:
        return p
    return q
