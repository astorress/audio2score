// Helpers around @tonejs/midi: note extraction, piano-roll layout and
// score-time ↔ seconds conversion. Pure functions (no DOM) so they are testable.

import { Midi } from '@tonejs/midi'

export interface RollNote {
  pitch: number
  start: number
  duration: number
  velocity: number
  track: number
  percussion: boolean
}

export interface PitchRange {
  min: number
  max: number
}

export interface RollRect {
  x: number
  y: number
  w: number
  h: number
  note: RollNote
}

export interface RollLayout {
  width: number
  height: number
  duration: number
  range: PitchRange
}

const NOTE_NAMES = [
  'C',
  'C#',
  'D',
  'D#',
  'E',
  'F',
  'F#',
  'G',
  'G#',
  'A',
  'A#',
  'B',
]

/** MIDI number → scientific name ("C4" = 60). */
export function noteName(pitch: number): string {
  const p = Math.round(pitch)
  return `${NOTE_NAMES[((p % 12) + 12) % 12]}${Math.floor(p / 12) - 1}`
}

export function isBlackKey(pitch: number): boolean {
  return [1, 3, 6, 8, 10].includes(((pitch % 12) + 12) % 12)
}

export function parseMidi(data: ArrayBuffer | Uint8Array): Midi {
  return new Midi(data)
}

export async function fetchMidi(url: string, signal?: AbortSignal) {
  const res = await fetch(url, { signal })
  if (!res.ok) throw new Error(`No se pudo descargar el MIDI (${res.status})`)
  return parseMidi(await res.arrayBuffer())
}

const midiCache = new Map<string, Promise<Midi>>()

/** fetchMidi with an in-memory cache (the score and the piano-roll share files). */
export function loadMidi(url: string): Promise<Midi> {
  let p = midiCache.get(url)
  if (!p) {
    p = fetchMidi(url)
    p.catch(() => midiCache.delete(url))
    midiCache.set(url, p)
  }
  return p
}

/** Flattens every track of a parsed MIDI into a time-sorted note list. */
export function extractNotes(midi: Pick<Midi, 'tracks'>): RollNote[] {
  const notes: RollNote[] = []
  midi.tracks.forEach((track, t) => {
    const percussion = track.channel === 9 || track.instrument.percussion
    for (const n of track.notes) {
      notes.push({
        pitch: n.midi,
        start: n.time,
        duration: n.duration,
        velocity: n.velocity,
        track: t,
        percussion,
      })
    }
  })
  return notes.sort((a, b) => a.start - b.start || a.pitch - b.pitch)
}

/** Pitch range of the notes, padded and with a minimum span (one octave). */
export function pitchRange(
  notes: RollNote[],
  padding = 2,
  minSpan = 12
): PitchRange {
  if (notes.length === 0) return { min: 48, max: 72 }
  let min = Infinity
  let max = -Infinity
  for (const n of notes) {
    if (n.pitch < min) min = n.pitch
    if (n.pitch > max) max = n.pitch
  }
  min -= padding
  max += padding
  const missing = minSpan - (max - min)
  if (missing > 0) {
    min -= Math.floor(missing / 2)
    max += Math.ceil(missing / 2)
  }
  return { min: Math.max(0, min), max: Math.min(127, max) }
}

export function notesDuration(notes: RollNote[]): number {
  return notes.reduce((acc, n) => Math.max(acc, n.start + n.duration), 0)
}

/**
 * Maps notes to rectangles: x = time, y = pitch (high pitches on top).
 * Each pitch row has height `height / (max - min + 1)`.
 */
export function layoutNotes(notes: RollNote[], layout: RollLayout): RollRect[] {
  const { width, height, duration, range } = layout
  if (duration <= 0 || width <= 0 || height <= 0) return []
  const rows = range.max - range.min + 1
  const rowH = height / rows
  const pxPerSec = width / duration
  return notes
    .filter((n) => n.pitch >= range.min && n.pitch <= range.max)
    .map((note) => ({
      x: note.start * pxPerSec,
      y: (range.max - note.pitch) * rowH,
      w: Math.max(1, note.duration * pxPerSec),
      h: rowH,
      note,
    }))
}

/**
 * OSMD timestamps are fractions of a whole note. With a quarter-note beat at
 * `tempo` BPM, a whole note lasts 4 * 60 / tempo seconds.
 */
export function wholeNotesToSeconds(realValue: number, tempo: number): number {
  if (!(tempo > 0)) return 0
  return (realValue * 4 * 60) / tempo
}

/**
 * Index of the last step whose time is <= t (binary search). `times` must be
 * sorted ascending. Returns -1 when t is before the first step.
 */
export function stepIndexAt(times: number[], t: number): number {
  let lo = 0
  let hi = times.length - 1
  let ans = -1
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (times[mid]! <= t + 1e-6) {
      ans = mid
      lo = mid + 1
    } else {
      hi = mid - 1
    }
  }
  return ans
}

export function formatTime(sec: number): string {
  if (!Number.isFinite(sec) || sec < 0) sec = 0
  const m = Math.floor(sec / 60)
  const s = Math.floor(sec % 60)
  return `${m}:${s.toString().padStart(2, '0')}`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
