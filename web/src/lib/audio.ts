// Browser-only audio helpers (Web Audio API).

/** Sample rate used for decoding and for the uploaded WAV. */
export const TARGET_SAMPLE_RATE = 44100

/**
 * Decodes any browser-supported audio file. Decoding through an
 * OfflineAudioContext resamples to TARGET_SAMPLE_RATE, which keeps the WAV
 * size predictable (90 s stereo ≈ 15.9 MB).
 */
export async function decodeAudioFile(file: Blob): Promise<AudioBuffer> {
  const data = await file.arrayBuffer()
  const ctx = new OfflineAudioContext(2, 1, TARGET_SAMPLE_RATE)
  try {
    return await ctx.decodeAudioData(data)
  } catch {
    throw new Error(
      'El navegador no pudo decodificar este archivo. Prueba con WAV, MP3, FLAC u OGG.'
    )
  }
}

let sharedContext: AudioContext | null = null

/** Lazily created AudioContext shared by the stem mixer. */
export function getAudioContext(): AudioContext {
  if (!sharedContext || sharedContext.state === 'closed') {
    sharedContext = new AudioContext()
  }
  return sharedContext
}
