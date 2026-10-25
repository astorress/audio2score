import { describe, expect, it } from 'vitest'
import {
  WAV_HEADER_BYTES,
  cropChannels,
  encodeWav,
  floatToInt16,
  wavByteLength,
  type AudioBufferLike,
} from '../src/lib/wav'

function ascii(view: DataView, offset: number, length: number): string {
  let s = ''
  for (let i = 0; i < length; i++)
    s += String.fromCharCode(view.getUint8(offset + i))
  return s
}

function fakeBuffer(
  channels: Float32Array[],
  sampleRate: number
): AudioBufferLike {
  return {
    sampleRate,
    numberOfChannels: channels.length,
    length: channels[0]!.length,
    getChannelData: (c) => channels[c]!,
  }
}

describe('encodeWav', () => {
  it('writes a canonical 44-byte PCM header', () => {
    const left = new Float32Array(100)
    const right = new Float32Array(100)
    const buf = encodeWav([left, right], 44100)
    const v = new DataView(buf)
    expect(ascii(v, 0, 4)).toBe('RIFF')
    expect(v.getUint32(4, true)).toBe(36 + 100 * 4)
    expect(ascii(v, 8, 4)).toBe('WAVE')
    expect(ascii(v, 12, 4)).toBe('fmt ')
    expect(v.getUint32(16, true)).toBe(16)
    expect(v.getUint16(20, true)).toBe(1) // PCM
    expect(v.getUint16(22, true)).toBe(2) // channels
    expect(v.getUint32(24, true)).toBe(44100)
    expect(v.getUint32(28, true)).toBe(44100 * 4) // byte rate
    expect(v.getUint16(32, true)).toBe(4) // block align
    expect(v.getUint16(34, true)).toBe(16) // bits
    expect(ascii(v, 36, 4)).toBe('data')
    expect(v.getUint32(40, true)).toBe(100 * 4)
  })

  it('has the expected total length', () => {
    const mono = new Float32Array(1234)
    expect(encodeWav([mono], 22050).byteLength).toBe(
      WAV_HEADER_BYTES + 1234 * 2
    )
    expect(wavByteLength(1234, 1)).toBe(WAV_HEADER_BYTES + 1234 * 2)
    // 90 s stereo at 44.1 kHz, as in docs/api.md
    expect(wavByteLength(90 * 44100, 2)).toBe(15876044)
  })

  it('interleaves channels', () => {
    const l = Float32Array.from([0.5, -0.5])
    const r = Float32Array.from([1, -1])
    const v = new DataView(encodeWav([l, r], 8000))
    expect(v.getInt16(44, true)).toBe(floatToInt16(0.5))
    expect(v.getInt16(46, true)).toBe(32767)
    expect(v.getInt16(48, true)).toBe(floatToInt16(-0.5))
    expect(v.getInt16(50, true)).toBe(-32768)
  })

  it('clips out-of-range samples and maps NaN to silence', () => {
    expect(floatToInt16(2)).toBe(32767)
    expect(floatToInt16(-3)).toBe(-32768)
    expect(floatToInt16(Number.NaN)).toBe(0)
    expect(floatToInt16(0)).toBe(0)
    const v = new DataView(encodeWav([Float32Array.from([1.7, -1.2])], 8000))
    expect(v.getInt16(44, true)).toBe(32767)
    expect(v.getInt16(46, true)).toBe(-32768)
  })

  it('rejects invalid input', () => {
    expect(() => encodeWav([], 44100)).toThrow()
    expect(() =>
      encodeWav([new Float32Array(2), new Float32Array(3)], 44100)
    ).toThrow()
    expect(() => encodeWav([new Float32Array(2)], 0)).toThrow()
  })
})

describe('cropChannels', () => {
  const sr = 10
  const ramp = Float32Array.from({ length: 50 }, (_, i) => i / 50)

  it('extracts the requested region', () => {
    const [ch] = cropChannels(fakeBuffer([ramp], sr), 1, 2.5)
    expect(ch!.length).toBe(15)
    expect(ch![0]).toBeCloseTo(10 / 50)
  })

  it('clamps the region to the buffer', () => {
    const [ch] = cropChannels(fakeBuffer([ramp], sr), 4, 99)
    expect(ch!.length).toBe(10)
    expect(cropChannels(fakeBuffer([ramp], sr), -5, 0.5)[0]!.length).toBe(5)
  })

  it('down-mixes more than two channels to stereo', () => {
    const ones = new Float32Array(20).fill(1)
    const zeros = new Float32Array(20)
    const out = cropChannels(fakeBuffer([ones, zeros, ones, ones], sr), 0, 2)
    expect(out).toHaveLength(2)
    expect(out[0]![0]).toBeCloseTo(1) // (1 + 1) / 2
    expect(out[1]![0]).toBeCloseTo(0.5) // (0 + 1) / 2
  })
})
