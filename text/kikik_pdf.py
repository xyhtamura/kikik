"""kikik_pdf — set the kíkik text on a PDF page, one glyph per grid cell.

Renders the same grid as kikik_text.py. Every glyph is placed at its own cell,
so a Japanese glyph spans exactly two cells whatever the fonts' own advance
widths are. Latin is Noto Sans Mono, Japanese is Noto Sans JP (both SIL OFL
1.1, embedded as subsets).

Usage:
    python text/kikik_pdf.py F:/Eggs2/kikik/Cicada.swarm.mid -o text/out/kikik.pdf
    python text/kikik_pdf.py swarm.mid --rows 48 --width 60 --seed 1 --size 10.5

The grid options (--rows, --width, --density, --jitter, --norm, --fade,
--window, --seed) are the same as kikik_text.py and give the same text.
"""

import argparse
import io
import sys
from pathlib import Path

import pymupdf
from fontTools import subset
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.ttLib import newTable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kikik_text import HERE, build, is_wide, read_hits  # noqa: E402

FONTS = Path("C:/Windows/Fonts")
LATIN = FONTS / "NotoSansMono-Regular.ttf"
CJK = FONTS / "NotoSansJP-Regular.otf"
PAGE = pymupdf.paper_rect("letter")  # 612 x 792 pt, as XYH_DESCRIPTION.pdf


def grid_rows(text):
    """Yield rows as [(column, char)], columns counted in cells."""
    for line in text.rstrip("\n").split("\n"):
        row, col = [], 0
        for ch in line:
            if ch != " ":
                row.append((col, ch))
            col += 2 if is_wide(ch) else 1
        yield row


def cjk_subset(chars):
    """Subset Noto Sans JP to the glyphs used and convert it to TrueType.

    PyMuPDF does not draw this CFF-flavoured OTF: its own subset_fonts()
    turns the glyphs into boxes, and embedding the raw subset draws nothing.
    Converting the outlines to quadratic TrueType (glyf) makes it render, so
    the font is cut down and converted here before PyMuPDF sees it."""
    opts = subset.Options()
    font = subset.load_font(str(CJK), opts)
    sub = subset.Subsetter(opts)
    sub.populate(text="".join(sorted(chars)))
    sub.subset(font)

    glyphs = font.getGlyphSet()
    glyf = {}
    for name in font.getGlyphOrder():
        pen = TTGlyphPen(glyphs)
        glyphs[name].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
        glyf[name] = pen.glyph()
    font["loca"] = newTable("loca")
    table = font["glyf"] = newTable("glyf")
    table.glyphOrder = font.getGlyphOrder()
    table.glyphs = glyf
    for g in glyf.values():
        g.recalcBounds(table)
    del font["CFF "]
    if "VORG" in font:
        del font["VORG"]
    maxp = font["maxp"]
    maxp.tableVersion = 0x00010000
    for field in ("maxPoints", "maxContours", "maxCompositePoints", "maxCompositeContours",
                  "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
                  "maxStackElements", "maxSizeOfInstructions", "maxComponentElements",
                  "maxComponentDepth"):
        setattr(maxp, field, 0)
    maxp.maxZones = 1
    maxp.recalc(font)
    font["head"].glyphDataFormat = 0
    font["post"].formatType = 3.0
    font.sfntVersion = bytes((0, 1, 0, 0)).decode("latin-1")  # TrueType
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def render(text, width, out, size, title):
    latin = pymupdf.Font(fontfile=str(LATIN))
    cjk = pymupdf.Font(fontbuffer=cjk_subset({c for c in text if is_wide(c)}))
    rows = list(grid_rows(text))

    cell_w = latin.glyph_advance(ord("a")) * size
    pitch = size * 1.25
    block_w = cell_w * width
    block_h = pitch * len(rows)
    title_gap = pitch * 3 if title else 0
    x0 = (PAGE.width - block_w) / 2
    y0 = (PAGE.height - block_h - title_gap) / 2 + title_gap
    if y0 - title_gap < 36:
        sys.exit(f"grid is {block_h + title_gap:.0f} pt tall; the page holds "
                 f"{PAGE.height - 72:.0f}. Lower --size or --rows.")

    doc = pymupdf.open()
    page = doc.new_page(width=PAGE.width, height=PAGE.height)
    tw = pymupdf.TextWriter(PAGE)
    if title:
        tw.append((x0, y0 - title_gap + size), title, font=latin, fontsize=size)
    for r, row in enumerate(rows):
        base = y0 + r * pitch + size  # baseline of this row
        for col, ch in row:
            x = x0 + col * cell_w
            if is_wide(ch):
                # Centre the glyph across its two cells; nudge the baseline so
                # the CJK body sits on the Latin x-height band.
                adv = cjk.glyph_advance(ord(ch)) * size
                tw.append((x + (2 * cell_w - adv) / 2, base + size * 0.08), ch, font=cjk, fontsize=size)
            else:
                tw.append((x, base), ch, font=latin, fontsize=size)
    tw.write_text(page)
    doc.set_metadata({"title": title or "kíkik", "creator": "kikik_pdf.py"})
    doc.subset_fonts()  # Latin only; the CJK font is already a subset
    doc.save(out, garbage=4, deflate=True)
    return {"cell_pt": round(cell_w, 2), "pitch_pt": round(pitch, 2),
            "block_pt": (round(block_w), round(block_h)), "top_pt": round(y0 - title_gap)}


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("midi")
    ap.add_argument("--lyrics", default=str(HERE / "lyrics.txt"))
    ap.add_argument("--width", type=int, default=60)
    ap.add_argument("--rows", type=int, default=48)
    ap.add_argument("--density", type=float, default=0.35)
    ap.add_argument("--jitter", type=float, default=1.5)
    ap.add_argument("--norm", choices=["global", "line"], default="line")
    ap.add_argument("--fade", type=float, default=0.6)
    ap.add_argument("--window", type=float, default=1.0)
    ap.add_argument("--seed", default="1")
    ap.add_argument("--size", type=float, default=10.5, help="font size in pt")
    ap.add_argument("--title", default="kíkik", help='heading above the grid; "" for none')
    ap.add_argument("-o", "--out", default=str(HERE / "out" / "kikik.pdf"))
    a = ap.parse_args(argv)

    lines = [l.strip() for l in Path(a.lyrics).read_text(encoding="utf-8").splitlines() if l.strip()]
    text, meta = build(read_hits(a.midi), lines, a.width, a.rows, a.density,
                       a.jitter, a.seed, a.norm, a.fade, a.window)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    layout = render(text, a.width, a.out, a.size, a.title)
    print({**meta, **layout}, file=sys.stderr)


if __name__ == "__main__":
    main()
