// Minimal 16-bit PCM WAV encoder (RIFF/WAVE, little-endian).

/** Subset of AudioBuffer used here, so the functions are testable in Node. */
export interface AudioBufferLike {
  readonly sampleRate: number
  readonly numberOfChannels: number
  readonly length: number
  getChannelData(channel: number): Float32Array
}

export const WAV_HEADER_BYTES = 44

/** Byte size of a 16-bit PCM WAV file with the given shape. */
export function wavByteLength(frames: number, channels: number): number {
  return WAV_HEADER_BYTES + frames * channels * 2
}

/** Converts a float sample in [-1, 1] to int16, clipping out-of-range values. */
export function floatToInt16(sample: number): number {
  if (Number.isNaN(sample)) return 0
  const s = Math.max(-1, Math.min(1, sample))
  return s < 0 ? Math.round(s * 0x8000) : Math.round(s * 0x7fff)
}

function writeAscii(view: DataView, offset: number, text: string): void {
  for (let i = 0; i < text.length; i++) {
    view.setUint8(offset + i, text.charCodeAt(i))
  }
}

/**
 * Encodes planar float channels (all the same length) as a 16-bit PCM WAV.
 * Samples are interleaved and clipped to [-1, 1].
 */
export function encodeWav(
  channels: Float32Array[],
  sampleRate: number
): ArrayBuffer {
  if (channels.length === 0) throw new Error('encodeWav: no channels')
  if (!Number.isInteger(sampleRate) || sampleRate <= 0)
    throw new Error('encodeWav: invalid sample rate')
  const frames = channels[0]!.length
  if (channels.some((c) => c.length !== frames))
    throw new Error('encodeWav: channels must have the same length')

  const numChannels = channels.length
  const blockAlign = numChannels * 2
  const dataBytes = frames * blockAlign
  const buffer = new ArrayBuffer(WAV_HEADER_BYTES + dataBytes)
  const view = new DataView(buffer)

  writeAscii(view, 0, 'RIFF')
  view.setUint32(4, 36 + dataBytes, true)
  writeAscii(view, 8, 'WAVE')
  writeAscii(view, 12, 'fmt ')
  view.setUint32(16, 16, true) // fmt chunk size
  view.setUint16(20, 1, true) // PCM
  view.setUint16(22, numChannels, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * blockAlign, true) // byte rate
  view.setUint16(32, blockAlign, true)
  view.setUint16(34, 16, true) // bits per sample
  writeAscii(view, 36, 'data')
  view.setUint32(40, dataBytes, true)

  let offset = WAV_HEADER_BYTES
  for (let i = 0; i < frames; i++) {
    for (let c = 0; c < numChannels; c++) {
      view.setInt16(offset, floatToInt16(channels[c]![i]!), true)
      offset += 2
    }
  }
  return buffer
}

/**
 * Extracts [startSec, endSec) from an audio buffer as planar channels.
 * More than two channels are down-mixed to stereo (L = even, R = odd).
 */
export function cropChannels(
  audio: AudioBufferLike,
  startSec: number,
  endSec: number
): Float32Array[] {
  const sr = audio.sampleRate
  const start = Math.max(0, Math.min(audio.length, Math.floor(startSec * sr)))
  const end = Math.max(start, Math.min(audio.length, Math.round(endSec * sr)))
  const source = Array.from({ length: audio.numberOfChannels }, (_, c) =>
    audio.getChannelData(c).subarray(start, end)
  )
  if (source.length <= 2) return source.map((ch) => new Float32Array(ch))

  const out = [new Float32Array(end - start), new Float32Array(end - start)]
  const counts = [0, 0]
  source.forEach((ch, c) => {
    const target = out[c % 2]!
    counts[c % 2]!++
    for (let i = 0; i < ch.length; i++) target[i]! += ch[i]!
  })
  out.forEach((ch, k) => {
    const n = counts[k]!
    for (let i = 0; i < ch.length; i++) ch[i]! /= n
  })
  return out
}

/** Crops a region and returns it as a WAV Blob ready to upload. */
export function cropToWavBlob(
  audio: AudioBufferLike,
  startSec: number,
  endSec: number
): Blob {
  const channels = cropChannels(audio, startSec, endSec)
  return new Blob([encodeWav(channels, audio.sampleRate)], {
    type: 'audio/wav',
  })
}
