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
