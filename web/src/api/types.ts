// Types mirroring docs/api.md (the HTTP contract between web/ and the backend).

export type ModeId = 'auto' | 'rock' | 'orchestra'
export type ResolvedMode = Exclude<ModeId, 'auto'>
export type Quantization = string // e.g. "1/16"; the catalog lists the valid ones

export interface Instrument {
  id: string
  name: string
  family: string
  modes: ResolvedMode[]
  clef: string
  /** Written → sounding interval in music21 notation ("M-2": sounds a major
   * second below what is written), or null. */
  transposition: string | null
  range: [string, string]
  /** The part is reduced to a single line. */
  monophonic: boolean
}

export interface Family {
  id: string
  name: string
}

export interface Mode {
  id: ModeId
  name: string
}

export interface Limits {
  maxDurationSec: number
  maxUploadBytes: number
  contentTypes: string[]
}

export interface Catalog {
  instruments: Instrument[]
  families: Family[]
  modes: Mode[]
  defaults: Record<ResolvedMode, string[]>
  limits: Limits
  quantizations: Quantization[]
}

export interface JobOptions {
  quantization: Quantization
  allowTriplets: boolean
  exportPdf: boolean
}

export interface CreateJobRequest {
  mode: ModeId
  instruments?: string[]
  options?: JobOptions
  fileName: string
  contentType: string
  sizeBytes: number
  durationSec: number
}

export interface PresignedPost {
  url: string
  fields: Record<string, string>
}

export interface CreateJobResponse {
  jobId: string
  status: JobStatus
  upload: PresignedPost
  expiresInSec: number
}

export type JobStatus = 'PENDING' | 'QUEUED' | 'RUNNING' | 'DONE' | 'FAILED'
export type Stage = 'separation' | 'transcription' | 'engraving' | 'export'

export interface Stem {
  name: string
  label: string
  url: string
}

export interface MidiEntry {
  instrument: string
  name: string
  url: string
  notes: number
}

export interface PartEntry {
  instrument: string
  name: string
  url: string
}

export interface JobResult {
  durationSec: number
  tempo: number
  timeSignature: string
  key: string
  stems: Stem[]
  midi: MidiEntry[]
  midiFull: string
  score: { musicxml: string; pdf: string | null }
  parts: PartEntry[]
}

export interface Job {
  jobId: string
  status: JobStatus
  mode: ModeId
  resolvedMode: ResolvedMode | null
  instruments: string[]
  options: JobOptions
  createdAt: string
  updatedAt: string
  expiresAt: string
  stage: Stage | null
  stages: Partial<Record<Stage, number>>
  warnings: string[]
  error: string | null
  result: JobResult | null
}

export interface ApiErrorBody {
  message: string
}
