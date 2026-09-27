"""kikik_text — granulate lyric lines on the hits of a kíkik swarm MIDI.

The text version of kíkik. Each character cell is one slice of time. A slice
whose loudest hit clears the threshold prints a letter; the rest print a space.
The letter comes from a read head that moves through the current lyric line
over that line's share of the recording, with a seeded jitter around the head,
so a line is sprayed from left to right rather than spelled. The output is one
continuous block with no stanza breaks. Time is split evenly between lines, and
around each boundary the outgoing and incoming lines cross-fade: each printed
cell picks its line by weight, so the next line's letters thicken as the last
one's thin out. Every letter of every line is guaranteed to appear: a letter
the jitter never picked takes over the printed cell nearest its own place in
the sweep.

Usage:
    python text/kikik_text.py F:/Eggs2/kikik/Cicada.swarm.mid
    python text/kikik_text.py swarm.mid --lyrics text/lyrics.txt --width 60 \
        --rows 120 --density 0.35 --jitter 1.5 --seed 1 -o text/out/kikik.txt

Parameters that change the result:
    --rows     total rows; sets how much time one cell is
    --width    characters per row
    --density  fraction of cells that print, measured over the whole piece,
               so a quieter passage prints fewer letters than a loud one
    --norm     line (default): a threshold measured over --window rows of
               time around each cell, so the whole text reads at --density
               global: one threshold for the piece (quiet sections thin out)
    --window   rows of time the line threshold is measured over (default 1)
    --fade     length of each cross-fade, in line-lengths (0 = hard cut,
               1 = no line is ever heard alone)
    --jitter   spread of the read head, in characters (Gaussian sigma)
    --seed     same seed, same text
"""

import argparse
import math
import random
import sys
import unicodedata
from collections import Counter
from pathlib import Path

import mido

HERE = Path(__file__).resolve().parent


def read_hits(path):
    """Return [(seconds, velocity)] for every note-on in the file."""
    mid = mido.MidiFile(path)
    hits, t = [], 0.0
    for msg in mid:  # iterating a MidiFile yields delta times in seconds
        t += msg.time
        if msg.type == "note_on" and msg.velocity > 0:
            hits.append((t, msg.velocity))
    return hits


def is_wide(ch):
    return unicodedata.east_asian_width(ch) in ("W", "F")


def weights(u, n, fade):
    """Weight of each line at time u, measured in line-lengths (0..n).

    Each line holds full weight in the middle of its share of time and ramps
    linearly across `fade` line-lengths centred on each boundary, where the
    two neighbours meet at 0.5 each. fade=0 is a hard cut."""
    out = []
    for i in range(n):
        lo_edge = math.inf if i == 0 else u - i
        hi_edge = math.inf if i == n - 1 else i + 1 - u
        d = min(lo_edge, hi_edge)
        if fade <= 0:
            out.append(1.0 if d >= 0 else 0.0)
        else:
            out.append(max(0.0, min(1.0, (d + fade / 2) / fade)))
    return out


def support(i, n, fade):
    """Span of time, in line-lengths, over which line i can sound."""
    return max(0.0, i - fade / 2), min(float(n), i + 1 + fade / 2)


def force_missing(cells, owner, starts, lines, letters, cells_per_unit, fade):
    """Place each letter that never printed at the nearest printed cell of the
    same width, so the row layout does not shift. Cells of the letter's own
    line are preferred; a cell is only taken if its letter has another copy
    from the same line."""
    n = len(lines)
    copies = Counter((o, c) for o, c in zip(owner, cells) if c != " ")
    placed = set()
    for li in range(n):
        lo, hi = support(li, n, fade)
        for p, ch in enumerate(letters[li]):
            if copies[(li, ch)]:
                continue
            target = (lo + (p + 0.5) / len(letters[li]) * (hi - lo)) * cells_per_unit
            pool = [
                k for k, c in enumerate(cells)
                if c != " " and k not in placed and is_wide(c) == is_wide(ch)
                and copies[(owner[k], c)] > 1
            ]
            own = [k for k in pool if owner[k] == li]
            if not pool:
                print(f"warning: could not place {ch!r} from {lines[li]!r}: fewer printed "
                      "cells than letters; raise --density or --rows", file=sys.stderr)
                continue
            k = min(own or pool, key=lambda k: abs(starts[k] - target))
            copies[(owner[k], cells[k])] -= 1
            cells[k], owner[k] = ch, li
            copies[(li, ch)] += 1
            placed.add(k)


def build(hits, lines, width, rows, density, jitter, seed, norm="line", fade=0.6, window=1.0):
    n = len(lines)
    end = hits[-1][0]
    n_cells = rows * width
    cell_dur = end / n_cells
    cells_per_unit = n_cells / n  # cells in one line's share of time
    letters = [[c for c in line if not c.isspace()] for line in lines]

    # Loudest hit in each cell.
    peak = [0] * n_cells
    for t, v in hits:
        i = min(int(t / cell_dur), n_cells - 1)
        peak[i] = max(peak[i], v)

    def threshold_of(span):
        ranked = sorted(span, reverse=True)
        k = max(0, min(len(ranked) - 1, int(density * len(ranked)) - 1))
        return max(1, ranked[k])

    # global keeps loudness differences across the piece. line measures a
    # window `window` rows wide centred on each cell. The recording drops from
    # loud to quiet within about one row near 190 s; a window much longer than
    # that straddles the step and prints a dense burst then a gap.
    if norm == "line":
        half = max(1, int(window * width / 2))
        local = [threshold_of(peak[max(0, j - half):j + half + 1]) for j in range(n_cells)]
    else:
        local = [threshold_of(peak)] * n_cells

    cells, owner, starts = [], [], []
    j = 0
    while j < n_cells:
        u = (j + 0.5) / cells_per_unit
        w = weights(u, n, fade)
        if peak[j] < local[j]:
            cells.append(" "); owner.append(None); starts.append(j)
            j += 1
            continue
        rng = random.Random(f"{seed}:{j}")  # keyed per cell, like hitSeed
        # Choose the sounding line by weight, then read from its head.
        r = rng.random() * sum(w)
        li = 0
        while r > w[li]:
            r -= w[li]
            li += 1
        lo, hi = support(li, n, fade)
        head = min(1.0, max(0.0, (u - lo) / (hi - lo))) * len(letters[li])
        pos = int(math.floor(head + rng.gauss(0, jitter)))
        ch = letters[li][max(0, min(len(letters[li]) - 1, pos))]
        if is_wide(ch) and (j % width == width - 1 or j == n_cells - 1):
            cells.append(" "); owner.append(None); starts.append(j)  # no room for a double-width glyph
            j += 1
            continue
        cells.append(ch); owner.append(li); starts.append(j)
        j += 2 if is_wide(ch) else 1

    force_missing(cells, owner, starts, lines, letters, cells_per_unit, fade)

    # Re-flow into rows by display width.
    out, row, w = [], "", 0
    for ch in cells:
        cw = 2 if is_wide(ch) else 1
        if w + cw > width:
            out.append(row.rstrip())
            row, w = "", 0
        row += ch
        w += cw
    out.append(row.rstrip())

    meta = {
        "cell_ms": round(cell_dur * 1000, 1),
        "threshold_velocity": [min(local), max(local)],
        "rows_per_line": round(rows / n, 1),
        "seconds_per_line": round(end / n, 1),
    }
    return "\n".join(out) + "\n", meta


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("midi")
    ap.add_argument("--lyrics", default=str(HERE / "lyrics.txt"))
    ap.add_argument("--width", type=int, default=60)
    ap.add_argument("--rows", type=int, default=120)
    ap.add_argument("--density", type=float, default=0.35)
    ap.add_argument("--jitter", type=float, default=1.5)
    ap.add_argument("--norm", choices=["global", "line"], default="line")
    ap.add_argument("--fade", type=float, default=0.6)
    ap.add_argument("--window", type=float, default=1.0)
    ap.add_argument("--seed", default="1")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)

    lines = [l.strip() for l in Path(a.lyrics).read_text(encoding="utf-8").splitlines() if l.strip()]
    text, meta = build(read_hits(a.midi), lines, a.width, a.rows, a.density, a.jitter, a.seed, a.norm, a.fade, a.window)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    print(meta, file=sys.stderr)


if __name__ == "__main__":
    main()
