# kíkik

**Swarm dequantizer — the recording as the score.**

An onset analyzer and hit-seeded granulator, sibling to **binlod**
(`../binlod/`): binlod sprays grain clouds around the note-ons of an authored
MIDI score; kíkik derives the score itself from a field recording. Every
micro-peak in the audio becomes a **hit**, and the hits feed two sinks at
once — a swarm of MIDI notes, and a granulation that drops one grain (cut
from any sounds you feed it) on each hit. Audio in; MIDI and audio out.

*Kíkik* — Hiligaynon for cicada / cricket. Onomatopoeic: the name is the
call. Keeps the register of the family (binlod = seed/grain, tabota = 田) and,
like binlod's rice pun, it is load-bearing: the tool's whole move is that the
insect's stridulation — thousands of micro-attacks — is already a score,
waiting to be read.

Capability matrix, completed (binlod's, plus the row it was missing):

| | output: MIDI | output: audio |
|---|---|---|
| **input: MIDI** | binlod (lossy corner) | — |
| **input: Tabota** | binlod (high-fidelity) | binlod (master, planned) |
| **input: audio** | **kíkik** (analyzer) | **kíkik** (granulator) |

---

## The piece (context, not spec)

Kíkik is both this tool and the piece it was built to realize. In Filipino
and Japanese cultures alike, cicadas act as clocks: they announce seasons, an
hour of day, the particular trees and heat of a place. The source recording
is *Platypleura fulvigera* outside a former home near Diliman, 2016 — made
knowing it would become an archive of a place later left. The piece maps the
individual attacks of the cicada calls and uses them to trigger grains cut
from a multilingual Ilonggo / Japanese / English poem (the sung line quotes
"Dandansoy," a traditional Ilonggo folk song about leaving). The swarm
mediates the voice — it speaks through the singer, or the singer through it.

The tool generalizes the gesture: **any recording is a clock; any sound can
speak through it.**

---

## Philosophy

- **The recording is the score.** Binlod's note-ons were authored; kíkik's
  hits are *found*. Detection is not cleanup before the music — it is the
  authoring surface. The detect knobs (threshold, floor, gap) are
  compositional controls: they decide how fine-grained the found score is.
- **Hits are seed points, lens-relative.** One hit list, two readings: under
  the MIDI lens a hit is a note (strength → velocity, spectral colour →
  pitch); under the grain lens it is an anchor a grain drops on. Same
  structural object as binlod's anchor pin — meaning is lens-relative.
- **Baked and deterministic.** Like binlod, nothing is live or ephemeral. The
  scatter is keyed per-hit to a stable id (binlod's `heapSeed`, here
  `hitSeed`), so the same seed always lands the same swarm, and re-rolling
  never reshuffles what you already liked. Offline render, infinite
  lookahead, reproducible.
- **The export does not invert.** MIDI out samples the swarm; audio out
  renders it. Neither recovers the detector settings or the recording that
  birthed them — the recording stays the master, the exports are its shadows.
  (Rosetta pointed downstream, again.)

---

## Pipeline

```
field recording (audio file)
  → detect: micro-peaks → hits [{t, strength, centroid?}]
  → sink A: MIDI swarm   (one note per hit)        → .kikik.mid
  → sink B: granulation  (one grain per hit,
            cut from separate grain-source files)  → .kikik.wav
```

One analysis, two sinks — the generator → events → sink abstraction from
binlod §2, with the generator replaced by an *analyzer*.

---

## Detection (the found score)

Mono mixdown, then per sample: one-pole highpass → rectify → asymmetric
envelope follower (fixed ~0.8 ms attack; **smooth** is the release), sampled
down to a ~1.5 kHz control rate `E[i]`. The onset function is the
half-rectified derivative `O[i] = max(0, E[i] − E[i−1])` — energy arriving,
not energy present. A hit fires where all of:

- `O[i]` is a local maximum;
- `O[i] > thresh × ⟨O⟩±0.35s` — adaptive threshold, a moving mean so a loud
  passage doesn't swallow its own onsets;
- `E[i] > floor` (dBFS gate — kills room-tone false positives);
- at least **min gap** since the last hit (refractory period; this is the
  micro/macro dial — 3 ms reads every wing-click, 150 ms reads phrases).

Per hit: `strength` = envelope peak in the following 8 ms, normalized over
the take to `s01 ∈ [0,1]`; `centroid` = spectral centroid of a 2048-point
Hann window at the hit (computed lazily, only when the MIDI pitch mode wants
it).

| knob | default | what it decides |
|---|---|---|
| highpass | 1200 Hz | what counts as signal (cicada clicks live high) |
| smooth | 2 ms | envelope release — how fast E lets go |
| thresh | 2.0× | salience above the local mean |
| floor | −50 dB | absolute gate |
| min gap | 10 ms | finest allowed inter-onset interval |

Defaults are tuned for *Platypleura*: bright, dense, broadband clicks.

## MIDI sink (the swarm as notes)

One note per hit, `t` from the hit, velocity `1 + 126·s01^γ`, fixed note
length. Pitch modes:

- **fixed** — one note number; the swarm is pure rhythm.
- **centroid** — `69 + 12·log₂(centroid/440)`, clamped to [range lo, range
  hi]: each hit's spectral colour *is* its pitch. The clamp matters — cicada
  clicks centroid in the kHz range, so the range sliders are the
  transposition instrument.
- **random** — uniform in the range, seeded per hit (same `hitSeed` stream,
  xor-tweaked), so it re-rolls with the grain seed.

SMF format 0, 480 ppq, 120 bpm fixed (times are seconds; tempo is carrier,
not content).

## Grain sink (the swarm as voice)

One grain per hit, cut from the **grain sources** — any number of audio
files, chosen per hit by *cycle* or seeded *random*. Per hit, a fresh
`mulberry32(hitSeed(seed, hit.id))` draws, in fixed order: probability gate,
source pick, length jitter, pitch jitter, position, pan. Fixed draw order =
changing one knob never re-randomizes the others' draws.

- **length** ± jitter; **pitch** ±24 st ± jitter (playback rate).
- **position** — where in the source the grain is cut:
  - *random* — anywhere, every hit;
  - *follow* — hit time maps proportionally into the source (± jitter): the
    source is read through at the recording's pace, so a text stays roughly
    in order — this is the mode that lets a poem speak through the swarm;
  - *walk* — a clamped random walk (step = pos jit): local coherence,
    global drift.
- **envelope** — hann / expodec (attack-forward) / rev (swell); 129-point
  gain curve per grain. For expodec/rev, **attack** (ramp fraction) and
  **decay** (falloff steepness) are exposed as knobs; hann is symmetric and
  ignores them.
- **gain** — master × (optionally) `0.25 + 0.75·s01^0.8`: the cicada's
  dynamics ride through to the voice.
- **prob** thins the swarm; **spread** pans it, seeded per hit.

Preview plays live (capped at 8000 grains — the render is uncapped); render
is an `OfflineAudioContext` at the field's sample rate, stereo,
`field + tail` long, with an optional **dry mix** of the recording under the
grains. WAV out, 16-bit.

---

## Relation to binlod (the fold-in path)

Kíkik's hits are structurally binlod's note-on anchors — a hit is an anchor
pin with strength instead of velocity. The planned fold-in is therefore an
*input* fold, not a feature merge: detection becomes an audio-in front end
that emits the event list binlod already granulates, and kíkik's per-hit
grain params become per-heap overrides binlod already has. What kíkik has
that binlod doesn't (audio sink, grain sources, follow/walk position) is the
audio column of the shared matrix; what binlod has that kíkik doesn't
(editing shell, per-heap overrides, undo) is the part a fold-in gets free.

Shared code today (hand-copied, not stamped — see `../DEPENDENCIES.md`):
Tabota Roll CSS substrate; binlod's `smf.build` (write half); binlod's
stable-id seeding (`heapSeed` → `hitSeed`). If binlod's SMF writer or seeding
changes, re-copy by hand.

## Implementation notes

- Single file, `index.html`, vanilla JS, no deps. Third accent colour:
  **chitin** `#7a8c2e`, alongside binlod's husk.
- View: waveform + detection envelope (tide) + hit ticks (ember, height =
  strength) + grain strip (chitin dots, y = position-in-source). Ctrl-wheel
  zoom, drag scroll.
- Drop order: first audio file dropped = field recording; later drops = grain
  sources.
- Console/test surface: `window.kikik` exposes state, params, and the pure
  cores (`detect`, `planGrains`, `midiNotes`, `renderToBuffer`, `smfBuild`,
  `wavEncode`).

## Open forks

1. **Manual hit editing** — add/delete/nudge hits on the waveform (binlod's
   select/add chrome ports directly). Detection proposes; the author disposes.
2. **Per-hit overrides** — binlod's scope-door (select hits, edit their
   grain params locally). Wants (1) first.
3. **Tabota out** — hits as a `.tabota` event list, making the found score a
   first-class citizen of the Roll. This is the real fold-in.
4. **Segment-aware grains** — grain source position keyed to hit features
   (centroid → which vowel), not just time. The voice answering the insect
   in kind.

## Work log

2026-07-31 — Codex — Investigated a report that pitch jitter did not work.
Verified the control and planner with a 20-hit synthetic recording and a
steady-tone grain source through the root server. At 0 st, all planned
playback rates were 1.0; at ±12 st, rates ranged from 0.600 to 1.859. No
production code changed. During preview, all grains are scheduled when
playback starts, so pitch and jitter changes apply to the next preview or
render, not the preview already playing. Left undone: decide whether grain
controls should restart or reschedule an active preview.

---

2026-09-27 — Claude Code — Added `text/kikik_text.py`, a text version of the piece aimed at Navy Pen Issue V: NOISE (poetry, max 3 pages, due 2026-10-10). The script reads `F:/Eggs2/kikik/Cicada.swarm.mid` (22,639 hits, all on pitch 96, about 11 ms apart, 283 s). It divides time into character cells, and a cell prints a letter when its loudest hit clears a velocity threshold. The letter comes from a read head that sweeps the current line of `text/lyrics.txt`, with a seeded Gaussian jitter. Each lyric line gets an equal share of the MIDI's duration. CJK glyphs take two cells. `--norm global` uses one threshold, so after about 190 s, where velocity drops from about 76 to about 45, "it's 8 o'clock" prints two letters and "summer na naman" prints none. `--norm line` sets a threshold per line, so every line reads. Checked by rendering both modes at 48 rows × 60 columns (`text/out/`); both are deterministic under `--seed`.
Undone: lines are not yet aligned to where 01–06.wav sit in `kikik.rpp` (48.5 s to 226 s), and it has not been confirmed that the MIDI's timeline matches the arrangement's. No PDF layout yet. Visual fragmentation of glyphs, the user's second idea, has not been started.

2026-09-27 — Claude Code — `kikik_text.py`: per-line thresholds (`--norm line`) are now the default, at the user's direction. The text does not need to follow the rpp, so each line keeps an equal share of time and every line reads. Every letter of a line is now guaranteed to appear: a letter the jitter never picked replaces the nearest printed cell of the same width, and only when that cell's letter has another copy. Checked by sweeping 540 renders (20 seeds × 3 densities × 3 jitters × 3 page sizes). The only misses were at 24 rows × 40 columns × density 0.05, where a line gets about 8 printed cells for up to 22 distinct letters, so full coverage is impossible. The script warns in that case. Undone: a row with no printed cells inside a stanza renders as an empty line and reads like a stanza break. No PDF layout yet, and no glyph fragmentation.

2026-09-27 — Claude Code — `kikik_text.py` now writes one continuous block with no stanza breaks, at the user's request. Around each line boundary the outgoing and incoming lines cross-fade (`--fade`, in line-lengths, default 0.6; 0 is a hard cut). Each printed cell picks its line by weight, then reads from that line's head. The head sweeps each line's whole time span, fades included. The per-line threshold is now measured over a sliding window (`--window`, in rows, default 1). With a window one line long, the loud-to-quiet drop in the recording near 190 s printed a nearly full row followed by nearly empty ones, because the window straddled the drop. One row keeps every row between 11 and 27 printed characters at 48 × 60 (seed 1), with no empty rows. The coverage guarantee now works per line, over the whole stream. Checked by sweeping 360 renders (10 seeds × 2 densities × 3 jitters × 3 fades × 2 page sizes): no unplaceable-letter warnings. Undone: PDF layout, glyph fragmentation.

2026-09-27 — Claude Code — Added `text/kikik_pdf.py`, which sets the grid on one Letter page (612 × 792 pt, the same size as `XYH_DESCRIPTION.pdf`) with the heading "kíkik". Each glyph is placed at its own cell: 10.5 pt, a 6.3 pt cell, 13.1 pt row pitch, 48 rows × 60 columns in a 378 × 630 pt block. Latin is Noto Sans Mono and Japanese is Noto Sans JP (both SIL OFL 1.1, from `C:/Windows/Fonts`, embedded as subsets). PyMuPDF cannot draw the CFF-based Noto Sans JP: `subset_fonts()` turned the glyphs into boxes and left a 3.9 MB file, and embedding the raw subset drew nothing. The script subsets the font with fontTools and converts it to TrueType outlines first. The output is `text/out/kikik.pdf`, 18 KB. Checked by rasterising at 110 and 300 dpi and reading the images (Japanese glyphs present and centred across two cells), and by text extraction (195 Japanese glyphs recovered). Undone: page 2 (process note, original text and translations, following `XYH_DESCRIPTION.pdf`); whether the author's name goes on the page (the saved call text does not state Navy Pen's file rules; check the Submittable form); glyph fragmentation.

2026-09-27 — Claude Code — Added `text/assemble_txt.py`, which writes the Navy Pen submission file `text/out/kikik.txt`: the title, the 48 × 60 grid (seed 1, the same defaults as the PDF), then `NOTE.md` without its heading line. The file is UTF-8 without a BOM, with CRLF line endings and NFC normalisation. Xyh revised `NOTE.md`; I fixed two typos ("transferring", a stray comma). Checked by decoding the file: 5,289 bytes, 69 lines, no bare LFs, no combining marks, and the grid is line-for-line identical to `kikik_text.py --rows 48`. Decided against Hiligaynon diacritics in the lyrics: everyday Hiligaynon and printed "Dandansoy" lyrics are unmarked, and I could not supply correct stress marks. Undone: whether to add a "best viewed in a monospaced font" line or a BOM; submitting through Submittable (Xyh's to do, due 2026-10-10).

2026-09-27 — Claude Code — At Xyh's direction the submission is now the PDF rather than the .txt, and `kikik_pdf.py` makes two pages. Page 1 has the title "kíkik" (Noto Serif Light, 26 pt) and "xyh" (Noto Serif Light Italic; the name as it appears in `XYH BIO.pdf`), then the monospaced grid, unchanged. Page 2 is `NOTE.md` in Noto Serif Light 10.5 pt, with the poem's lines and translations as two parallel columns parsed from the "original — translation" block. "it's 8 o'clock" leaves the right column empty. Two font workarounds. Noto Serif JP (CFF) has to be converted to TrueType, like Noto Sans JP. MuPDF's HTML engine sends glyphs missing from the first font to its built-in Droid Sans Fallback instead of using the CSS fallback list, so Japanese runs are wrapped in a span that names the Japanese font, and shifted up 0.25 em to share the Latin baseline. Checked by listing each page's fonts (Noto only, no Droid), by span origins (the translation-table baselines match to 0.01 pt, at an even 17.75 pt pitch), and by rasterising both pages. 68 KB; page 2 has 118 pt spare. `assemble_txt.py` and `kikik.txt` are kept as the plain-text version. Undone: straight quotes and apostrophes in NOTE.md are left as Xyh typed them; submission through Submittable.

2026-09-27 — Claude Code — `NOTE.md` now uses curly quotes and apostrophes throughout, which also makes the note's "it’s 8 o’clock" match `lyrics.txt`. Rebuilt the PDF and `kikik.txt`: no straight quotes remain in the .txt. The page-2 translation table is centred as a block, with its text left-aligned in each column. MuPDF ignores `margin: auto` on tables, so the script measures both columns with the note fonts and sets the left margin. The first attempt measured correctly but still sat 10 pt left of centre: the table shrank to fit beside the margin, and "Dandansoy, I will leave you" wrapped. The cells are now `white-space: nowrap`. Checked from the line bounding boxes: the table spans 162.1–449.4 pt, centred at 305.8 against the page's 306, and every row is a single line. Page 2 has no heading, at Xyh's decision.

2026-09-27 — Claude Code — The public and CV descriptions of kíkik now say it is also a poem in electroacoustic and text versions (data.js, the commented-out index.html entry, cv.md, portfolio.md). The ROADMAP entry's Mechanism line described a boids swarm simulation, which matches nothing in this folder. It now describes the onset analyzer, the granulator, and `text/`. Next in Dev is set to the open question from the grain-pitch entry: whether changing grain controls restarts or reschedules an active preview.

2026-10-23 — Codex — Built the presentation page in `../xyhtamura.github.io/kikik/` using the finished text outputs and existing site MP3. Retained `text/audio-statement.pdf`, copied from `F:/Eggs2/kikik/XYH_DESCRIPTION.pdf`, and its page-marked Markdown extraction for future editing. Source statement wording was preserved on the page; the PDF translation table was reconstructed as six HTML rows. Edge checked playback, downloads, and desktop/mobile overflow; inspected the mobile screenshot. No tool behavior or planned work changed. Undone: site publication.

2026-10-23 — Codex — Xyh moved the presentation page from the site repository into this repository’s `kikik/` subfolder and edited its prose. Consolidated that page into one shared statement and translation table, with separate musical and text processes beside the outputs. Updated the local audio/home links for the move. Edge checked the section structure, audio metadata, image and download responses, and lack of horizontal overflow at 1440 and 390 px; inspected the desktop rendering. Tool behavior and roadmap plans are unchanged. Undone: publication and final deployment paths; original downloadable PDF/text notes are unchanged.

2026-10-23 — Codex — Added a tool slot and description before the two outputs on `kikik/index.html`, linking to the working tool at `../index.html`. Described the implemented detection, MIDI/grain sinks, position modes, seed, and exports. Edge checked section order, media loading, and no overflow at desktop/mobile widths; inspected the desktop rendering and checked the link target's page title over HTTP. Tool behavior and roadmap plans are unchanged. Undone: publication and deployment paths as recorded in the page notes.
