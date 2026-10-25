import { describe, expect, it } from 'vitest'
import { Midi } from '@tonejs/midi'
import {
  extractNotes,
  isBlackKey,
  layoutNotes,
  noteName,
  notesDuration,
  parseMidi,
  pitchRange,
  stepIndexAt,
  wholeNotesToSeconds,
} from '../src/lib/midi'

function sampleMidi(): Midi {
  const midi = new Midi()
  midi.header.setTempo(120)
  const melody = midi.addTrack()
  melody.addNote({ midi: 60, time: 0, duration: 0.5, velocity: 0.8 })
  melody.addNote({ midi: 64, time: 0.5, duration: 0.5, velocity: 0.6 })
  melody.addNote({ midi: 67, time: 1, duration: 1, velocity: 1 })
  const drums = midi.addTrack()
  drums.channel = 9
  drums.addNote({ midi: 36, time: 0, duration: 0.1 })
  // Round-trip through bytes, like a downloaded file.
  return parseMidi(midi.toArray())
}

describe('midi helpers', () => {
  it('names notes', () => {
    expect(noteName(60)).toBe('C4')
    expect(noteName(69)).toBe('A4')
    expect(noteName(21)).toBe('A0')
    expect(isBlackKey(61)).toBe(true)
    expect(isBlackKey(64)).toBe(false)
  })

  it('extracts sorted notes with percussion flags', () => {
    const notes = extractNotes(sampleMidi())
    expect(notes).toHaveLength(4)
    expect(notes.map((n) => n.pitch)).toEqual([36, 60, 64, 67])
    expect(notes[0]!.percussion).toBe(true)
    expect(notes[1]!.percussion).toBe(false)
    expect(notes[1]!.start).toBeCloseTo(0)
    expect(notes[3]!.duration).toBeCloseTo(1, 2)
    expect(notesDuration(notes)).toBeCloseTo(2, 2)
  })

  it('computes a padded pitch range with a minimum span', () => {
    const notes = extractNotes(sampleMidi()).filter((n) => !n.percussion)
    expect(pitchRange(notes)).toEqual({ min: 58, max: 70 })
    const single = [{ ...notes[0]!, pitch: 60 }]
    const r = pitchRange(single, 0, 12)
    expect(r.max - r.min).toBe(12)
    expect(pitchRange([])).toEqual({ min: 48, max: 72 })
  })

  it('lays out notes as rectangles (time → x, pitch → y)', () => {
    const notes = extractNotes(sampleMidi()).filter((n) => !n.percussion)
    const range = { min: 60, max: 67 } // 8 rows
    const rects = layoutNotes(notes, {
      width: 200,
      height: 80,
      duration: 2,
      range,
    })
    expect(rects).toHaveLength(3)
    const [c4, e4, g4] = rects
    expect(c4!.x).toBeCloseTo(0)
    expect(c4!.w).toBeCloseTo(50, 0)
    expect(c4!.y).toBeCloseTo(70) // lowest row
    expect(c4!.h).toBeCloseTo(10)
    expect(e4!.x).toBeCloseTo(50, 0)
    expect(g4!.y).toBeCloseTo(0) // highest row
    expect(
      layoutNotes(notes, { width: 0, height: 80, duration: 2, range })
    ).toEqual([])
    // Notes outside the range are dropped.
    expect(
      layoutNotes(notes, {
        width: 200,
        height: 80,
        duration: 2,
        range: { min: 62, max: 66 },
      })
    ).toHaveLength(1)
  })

  it('converts OSMD whole-note timestamps to seconds', () => {
    expect(wholeNotesToSeconds(1, 120)).toBeCloseTo(2) // a 4/4 bar at 120 BPM
    expect(wholeNotesToSeconds(0.25, 60)).toBeCloseTo(1) // a quarter at 60 BPM
    expect(wholeNotesToSeconds(1, 0)).toBe(0)
  })

  it('finds the cursor step for a playback time', () => {
    const times = [0, 0.5, 1, 1.5]
    expect(stepIndexAt(times, -0.1)).toBe(-1)
    expect(stepIndexAt(times, 0)).toBe(0)
    expect(stepIndexAt(times, 0.74)).toBe(1)
    expect(stepIndexAt(times, 1)).toBe(2)
    expect(stepIndexAt(times, 99)).toBe(3)
    expect(stepIndexAt([], 1)).toBe(-1)
  })
})
