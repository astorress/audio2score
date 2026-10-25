import type { JobStatus, Stage } from '@/api/types'

export const STAGE_LABELS: Record<Stage, string> = {
  separation: 'Separación de fuentes',
  transcription: 'Transcripción a MIDI',
  engraving: 'Partitura (engraving)',
  export: 'Exportación',
}

export const STAGE_HINTS: Record<Stage, string> = {
  separation: 'Demucs separa voz, batería, bajo, guitarra y piano.',
  transcription: 'Cada pista se convierte en notas MIDI.',
  engraving: 'Limpieza, cuantización, tonalidad, claves y transposición.',
  export: 'MusicXML, MIDI y PDF listos para descargar.',
}

export const STATUS_LABELS: Record<JobStatus, string> = {
  PENDING: 'Esperando el audio',
  QUEUED: 'En cola',
  RUNNING: 'Procesando',
  DONE: 'Listo',
  FAILED: 'Falló',
}

export const ALL_STAGES: Stage[] = [
  'separation',
  'transcription',
  'engraving',
  'export',
]
