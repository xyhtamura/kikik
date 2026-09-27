"""assemble_txt — write the submission .txt: title, grid, then the note.

Renders the grid with the same defaults as kikik_pdf.py (48 rows x 60
columns, seed 1), so the .txt and the PDF carry the same text. The note is
copied from NOTE.md without its first line, which is a file heading.

Usage:
    python text/assemble_txt.py F:/Eggs2/kikik/Cicada.swarm.mid
    python text/assemble_txt.py swarm.mid --rows 48 --seed 1 -o text/out/kikik.txt
"""

import argparse
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kikik_text import HERE, build, read_hits  # noqa: E402


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("midi")
    ap.add_argument("--lyrics", default=str(HERE / "lyrics.txt"))
    ap.add_argument("--note", default=str(HERE / "NOTE.md"))
    ap.add_argument("--rows", type=int, default=48)
    ap.add_argument("--width", type=int, default=60)
    ap.add_argument("--seed", default="1")
    ap.add_argument("--title", default="kíkik")
    ap.add_argument("-o", "--out", default=str(HERE / "out" / "kikik.txt"))
    a = ap.parse_args(argv)

    lines = [l.strip() for l in Path(a.lyrics).read_text(encoding="utf-8").splitlines() if l.strip()]
    grid, _ = build(read_hits(a.midi), lines, a.width, a.rows, 0.35, 1.5, a.seed)
    note = Path(a.note).read_text(encoding="utf-8").split("\n", 1)[1].strip()
    lines_out = [l.rstrip() for l in f"{a.title}\n\n{grid.rstrip()}\n\n\n{note}\n".split("\n")]
    # NFC keeps accented letters as one character, so they take one cell.
    text = unicodedata.normalize("NFC", "\n".join(lines_out))
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(text, encoding="utf-8", newline="\r\n")  # CRLF for Windows viewers
    print(a.out)


if __name__ == "__main__":
    main()
