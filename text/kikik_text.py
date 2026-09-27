"""kikik_text — granulate lyric lines on the hits of a kíkik swarm MIDI.

The text version of kíkik. Each character cell is one slice of time. A slice
whose loudest hit clears the threshold prints a letter; the rest print a space.
The letter comes from a read head that moves through the current lyric line
over that line's share of the recording, with a seeded jitter around the head,
so a line is sprayed from left to right rather than spelled. Time is split
evenly between lines. Every letter of a line is guaranteed to appear: a letter
the jitter never picked takes over the printed cell nearest its own place in
the sweep.

Usage:
    python text/kikik_text.py F:/Eggs2/kikik/Cicada.swarm.mid
    python text/kikik_text.py swarm.mid --lyrics text/lyrics.txt --width 60 \
        --rows 120 --density 0.35 --jitter 1.5 --seed 1 -o text/out/kikik.txt

Parameters that change the result:
    --rows     total rows across all stanzas; sets how much time one cell is
    --width    characters per row
    --density  fraction of cells that print, measured over the whole piece,
               so a quieter passage prints fewer letters than a loud one
    --norm     line (default): a threshold per lyric line, so every line
               reads at --density
               global: one threshold for the piece (quiet sections thin out)
    --jitter   spread of the read head, in characters (Gaussian sigma)
    --seed     same seed, same text
"""

import argparse
import math
import random
import sys
import unicodedata
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


def force_missing(cells, starts, letters, cells_per_line, line):
    """Place each letter that never printed at the nearest printed cell of the
    same width, so the row layout does not shift."""
    placed = set()
    for p, ch in enumerate(letters):
        if ch in cells:
            continue
        target = (p + 0.5) / len(letters) * cells_per_line
        pool = [
            k for k, c in enumerate(cells)
            if c != " " and k not in placed and is_wide(c) == is_wide(ch)
            and cells.count(c) > 1  # never remove another letter's last copy
        ]
        if not pool:
            print(f"warning: could not place {ch!r} in {line!r}: fewer printed cells "
                  "than letters; raise --density or --rows", file=sys.stderr)
            continue
        k = min(pool, key=lambda k: abs(starts[k] - target))
        cells[k] = ch
        placed.add(k)


def build(hits, lines, width, rows, density, jitter, seed, norm="line"):
    end = hits[-1][0]
    rows_per_line = max(1, rows // len(lines))
    cells_per_line = rows_per_line * width
    cell_dur = end / (cells_per_line * len(lines))

    # Loudest hit in each cell across the whole piece.
    n_cells = cells_per_line * len(lines)
    peak = [0] * n_cells
    for t, v in hits:
        i = min(int(t / cell_dur), n_cells - 1)
        peak[i] = max(peak[i], v)

    def threshold_of(span):
        ranked = sorted(span, reverse=True)
        k = max(0, min(len(ranked) - 1, int(density * len(ranked)) - 1))
        return max(1, ranked[k])

    # global keeps loudness differences between sections; line flattens them.
    if norm == "line":
        thresholds = [threshold_of(peak[i * cells_per_line:(i + 1) * cells_per_line]) for i in range(len(lines))]
    else:
        thresholds = [threshold_of(peak)] * len(lines)

    stanzas = []
    for li, line in enumerate(lines):
        letters = [c for c in line if not c.isspace()]
        cells, starts = [], []
        base = li * cells_per_line
        threshold = thresholds[li]
        j = 0
        while j < cells_per_line:
            ci = base + j
            if peak[ci] < threshold:
                cells.append(" ")
                starts.append(j)
                j += 1
                continue
            rng = random.Random(f"{seed}:{ci}")  # keyed per cell, like hitSeed
            head = j / cells_per_line * len(letters)
            pos = int(math.floor(head + rng.gauss(0, jitter)))
            ch = letters[max(0, min(len(letters) - 1, pos))]
            col = j % width
            if is_wide(ch):
                if col == width - 1:  # no room for a double-width glyph
                    cells.append(" ")
                    starts.append(j)
                    j += 1
                    continue
                cells.append(ch)
                starts.append(j)
                j += 2
            else:
                cells.append(ch)
                starts.append(j)
                j += 1
        force_missing(cells, starts, letters, cells_per_line, line)
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
        stanzas.append("\n".join(out))

    meta = {
        "cell_ms": round(cell_dur * 1000, 1),
        "threshold_velocity": thresholds,
        "rows_per_line": rows_per_line,
        "seconds_per_line": round(end / len(lines), 1),
    }
    return "\n\n".join(stanzas) + "\n", meta


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
    ap.add_argument("--seed", default="1")
    ap.add_argument("-o", "--out")
    a = ap.parse_args(argv)

    lines = [l.strip() for l in Path(a.lyrics).read_text(encoding="utf-8").splitlines() if l.strip()]
    text, meta = build(read_hits(a.midi), lines, a.width, a.rows, a.density, a.jitter, a.seed, a.norm)
    if a.out:
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    print(meta, file=sys.stderr)


if __name__ == "__main__":
    main()
