// Dev-only mock of the audio2score API (docs/api.md), mounted at /__mock when
// VITE_MOCK=1. It simulates the job lifecycle and serves synthetic results
// (sine-tone stems, a generated MIDI and MusicXML) for manual UI testing.
// Never included in production builds.

import type { IncomingMessage, ServerResponse } from 'node:http'
import type { Plugin } from 'vite'
import { randomUUID } from 'node:crypto'
import { createRequire } from 'node:module'
import { encodeWav } from '../src/lib/wav.ts'
import catalogJson from './catalog.json' with { type: 'json' }
import type {
  Catalog,
  CreateJobRequest,
  Job,
  ResolvedMode,
  Stage,
} from '../src/api/types.ts'

// @tonejs/midi is CommonJS for Node: named ESM imports fail, so require it.
const { Midi } = createRequire(import.meta.url)(
  '@tonejs/midi'
) as typeof import('@tonejs/midi')

const BASE = '/__mock'
const TEMPO = 120
const BARS = 8

// Generated from src/contract (python3 -m src.scripts.export_catalog), so the
// mock never drifts from the real catalog.
const catalog = catalogJson as Catalog

interface MockJob {
  job: Job
  uploadedAt: number | null
  durationSec: number
}

const jobs = new Map<string, MockJob>()

// E natural minor riff, one pitch per quarter note (MIDI numbers, octave 4).
const RIFF = [64, 67, 69, 71, 69, 67, 66, 64, 62, 64, 67, 64, 71, 69, 67, 66]

function octaveFor(id: string): number {
  const inst = catalog.instruments.find((i) => i.id === id)
  if (!inst) return 0
  if (['bass', 'contrabass', 'tuba'].includes(id)) return -24
  if (inst.clef === 'bass' || id === 'viola' || id === 'guitar') return -12
  if (['flute', 'violin'].includes(id)) return 12
  return 0
}

function pitchesFor(id: string): number[] {
  const shift = octaveFor(id)
  const offset = id.length % 4 // small variation between parts
  return Array.from(
    { length: BARS * 4 },
    (_, i) => RIFF[(i + offset) % RIFF.length]! + shift
  )
}

const STEPS = ['C', 'C', 'D', 'D', 'E', 'F', 'F', 'G', 'G', 'A', 'A', 'B']
const ALTERS = [0, 1, 0, 1, 0, 0, 1, 0, 1, 0, 1, 0]

function clefXml(clef: string): string {
  switch (clef) {
    case 'bass':
      return '<clef><sign>F</sign><line>4</line></clef>'
    case 'alto':
      return '<clef><sign>C</sign><line>3</line></clef>'
    case 'percussion':
      return '<clef><sign>percussion</sign></clef>'
    default:
      return '<clef><sign>G</sign><line>2</line></clef>'
  }
}

function partXml(id: string, index: number): { header: string; body: string } {
  const inst = catalog.instruments.find((i) => i.id === id)!
  const pid = `P${index + 1}`
  const header = `<score-part id="${pid}"><part-name>${inst.name}</part-name></score-part>`
  const pitches = pitchesFor(id)
  let measures = ''
  for (let m = 0; m < BARS; m++) {
    let notes = ''
    for (let b = 0; b < 4; b++) {
      if (id === 'drums') {
        const display =
          b % 2 === 0
            ? '<display-step>F</display-step><display-octave>4</display-octave>'
            : '<display-step>C</display-step><display-octave>5</display-octave>'
        notes += `<note><unpitched>${display}</unpitched><duration>1</duration><type>quarter</type></note>`
        continue
      }
      const p = pitches[m * 4 + b]!
      const step = STEPS[p % 12]!
      const alter = ALTERS[p % 12]!
      const octave = Math.floor(p / 12) - 1
      notes += `<note><pitch><step>${step}</step>${alter ? `<alter>${alter}</alter>` : ''}<octave>${octave}</octave></pitch><duration>1</duration><type>quarter</type>${alter ? '<accidental>sharp</accidental>' : ''}</note>`
    }
    const attrs =
      m === 0
        ? `<attributes><divisions>1</divisions><key><fifths>1</fifths><mode>minor</mode></key><time><beats>4</beats><beat-type>4</beat-type></time>${clefXml(inst.clef)}</attributes><direction placement="above"><direction-type><metronome><beat-unit>quarter</beat-unit><per-minute>${TEMPO}</per-minute></metronome></direction-type><sound tempo="${TEMPO}"/></direction>`
        : ''
    measures += `<measure number="${m + 1}">${attrs}${notes}</measure>`
  }
  return { header, body: `<part id="${pid}">${measures}</part>` }
}

function musicXml(ids: string[]): string {
  const parts = ids.map(partXml)
  return `<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE score-partwise PUBLIC "-//Recordare//DTD MusicXML 4.0 Partwise//EN" "http://www.musicxml.org/dtds/partwise.dtd">
<score-partwise version="4.0"><work><work-title>Fragmento (mock)</work-title></work><part-list>${parts.map((p) => p.header).join('')}</part-list>${parts.map((p) => p.body).join('')}</score-partwise>`
}

function midiFile(ids: string[]): Uint8Array {
  const midi = new Midi()
  midi.header.setTempo(TEMPO)
  const beat = 60 / TEMPO
  for (const id of ids) {
    const track = midi.addTrack()
    track.name = id
    if (id === 'drums') {
      track.channel = 9
      for (let i = 0; i < BARS * 4; i++) {
        track.addNote({
          midi: i % 2 === 0 ? 36 : 38,
          time: i * beat,
          duration: 0.1,
          velocity: 0.8,
        })
        track.addNote({
          midi: 42,
          time: i * beat + beat / 2,
          duration: 0.05,
          velocity: 0.5,
        })
      }
      continue
    }
    pitchesFor(id).forEach((p, i) => {
      track.addNote({
        midi: p,
        time: i * beat,
        duration: beat * 0.9,
        velocity: 0.6 + 0.3 * (i % 4 === 0 ? 1 : 0),
      })
    })
  }
  return midi.toArray()
}

function stemWav(id: string): ArrayBuffer {
  const sr = 22050
  const beat = 60 / TEMPO
  const total = Math.round(BARS * 4 * beat * sr)
  const data = new Float32Array(total)
  const pitches = pitchesFor(id)
  for (let i = 0; i < total; i++) {
    const t = i / sr
    const k = Math.floor(t / beat)
    const local = t - k * beat
    const env = Math.exp(-local * 4)
    if (id === 'drums') {
      data[i] =
        local < 0.08 ? (Math.random() * 2 - 1) * 0.5 * Math.exp(-local * 40) : 0
    } else {
      const f = 440 * 2 ** ((pitches[k % pitches.length]! - 69) / 12)
      data[i] = 0.3 * env * Math.sin(2 * Math.PI * f * t)
    }
  }
  return encodeWav([data], sr)
}

function resolveMode(req: CreateJobRequest): ResolvedMode {
  if (req.mode !== 'auto') return req.mode
  const ids = req.instruments ?? []
  return ids.some(
    (id) =>
      !catalog.instruments.find((i) => i.id === id)?.modes.includes('rock')
  )
    ? 'orchestra'
    : 'rock'
}

function send(
  res: ServerResponse,
  status: number,
  body?: unknown,
  type = 'application/json'
) {
  res.statusCode = status
  res.setHeader('Access-Control-Allow-Origin', '*')
  if (body === undefined) return res.end()
  if (type === 'application/json') {
    res.setHeader('Content-Type', type)
    return res.end(JSON.stringify(body))
  }
  res.setHeader('Content-Type', type)
  res.end(body as Buffer | string)
}

async function readBody(req: IncomingMessage): Promise<Buffer> {
  const chunks: Buffer[] = []
  for await (const chunk of req) chunks.push(chunk as Buffer)
  return Buffer.concat(chunks)
}

const STAGE_SEC = 3
const QUEUE_SEC = 5

function refresh(mock: MockJob, origin: string): Job {
  const job = mock.job
  if (mock.uploadedAt === null || job.status === 'FAILED') return job
  const elapsed = (Date.now() - mock.uploadedAt) / 1000
  const order: Stage[] =
    job.resolvedMode === 'orchestra'
      ? ['transcription', 'engraving', 'export']
      : ['separation', 'transcription', 'engraving', 'export']
  if (elapsed < QUEUE_SEC) {
    job.status = 'QUEUED'
    job.stage = null
    return job
  }
  const idx = Math.floor((elapsed - QUEUE_SEC) / STAGE_SEC)
  job.stages = {}
  order
    .slice(0, idx)
    .forEach(
      (s, i) => (job.stages[s] = Math.round((STAGE_SEC + i * 0.37) * 100) / 100)
    )
  job.updatedAt = new Date().toISOString()
  if (idx < order.length) {
    job.status = 'RUNNING'
    job.stage = order[idx]!
    return job
  }
  job.status = 'DONE'
  job.stage = null
  const base = `${origin}${BASE}/files/${job.jobId}`
  const ids = job.instruments
  const name = (id: string) =>
    catalog.instruments.find((i) => i.id === id)?.name ?? id
  job.warnings = [
    'Partitura aproximada: datos sintéticos del mock de desarrollo.',
  ]
  job.result = {
    durationSec: Math.min(mock.durationSec, 90),
    tempo: TEMPO,
    timeSignature: '4/4',
    key: 'E minor',
    stems:
      job.resolvedMode === 'rock'
        ? ids.map((id) => ({
            name: id,
            label: name(id),
            url: `${base}/stems/${id}.wav`,
          }))
        : [],
    midi: ids.map((id) => ({
      instrument: id,
      name: name(id),
      url: `${base}/midi/${id}.mid`,
      notes: id === 'drums' ? BARS * 8 : BARS * 4,
    })),
    midiFull: `${base}/score.mid`,
    score: { musicxml: `${base}/score.musicxml`, pdf: null },
    parts: ids.map((id) => ({
      instrument: id,
      name: name(id),
      url: `${base}/parts/${id}.musicxml`,
    })),
  }
  return job
}

export function mockApiPlugin(): Plugin {
  return {
    name: 'audio2score-mock-api',
    apply: 'serve',
    configureServer(server) {
      server.middlewares.use(BASE, (req, res) => {
        void (async () => {
          const url = new URL(req.url ?? '/', 'http://mock')
          const origin = `http://${req.headers.host ?? 'localhost:5173'}`
          const path = url.pathname
          const method = req.method ?? 'GET'

          if (method === 'GET' && path === '/instruments')
            return send(res, 200, catalog)

          if (method === 'POST' && path === '/jobs') {
            const body = JSON.parse(
              (await readBody(req)).toString() || '{}'
            ) as CreateJobRequest
            if (body.durationSec > catalog.limits.maxDurationSec)
              return send(res, 400, {
                message: `durationSec supera ${catalog.limits.maxDurationSec} s`,
              })
            if (body.sizeBytes > catalog.limits.maxUploadBytes)
              return send(res, 400, { message: 'sizeBytes supera el máximo' })
            const resolvedMode = resolveMode(body)
            const instruments = body.instruments?.length
              ? body.instruments
              : catalog.defaults[resolvedMode]
            const jobId = randomUUID()
            const now = new Date()
            const job: Job = {
              jobId,
              status: 'PENDING',
              mode: body.mode,
              resolvedMode,
              instruments,
              options: body.options ?? {
                quantization: '1/16',
                allowTriplets: false,
                exportPdf: true,
              },
              createdAt: now.toISOString(),
              updatedAt: now.toISOString(),
              expiresAt: new Date(now.getTime() + 86400e3).toISOString(),
              stage: null,
              stages: {},
              warnings: [],
              error: null,
              result: null,
            }
            jobs.set(jobId, {
              job,
              uploadedAt: null,
              durationSec: body.durationSec,
            })
            return send(res, 201, {
              jobId,
              status: 'PENDING',
              upload: {
                url: `${origin}${BASE}/upload/${jobId}`,
                fields: {
                  key: `uploads/${jobId}.wav`,
                  'Content-Type': 'audio/wav',
                  policy: 'mock-policy',
                  'x-amz-signature': 'mock',
                },
              },
              expiresInSec: 600,
            })
          }

          const upload = /^\/upload\/([\w-]+)$/.exec(path)
          if (method === 'POST' && upload) {
            const mock = jobs.get(upload[1]!)
            const raw = await readBody(req)
            if (!mock) return send(res, 404, { message: 'Job not found' })
            // Sanity check of the presigned-POST contract: `file` must be the last field.
            const text = raw.toString('latin1')
            const lastField = [
              ...text.matchAll(/form-data; name="([^"]+)"/g),
            ].pop()?.[1]
            if (lastField !== 'file')
              return send(
                res,
                400,
                '<Error><Message>file must be the last field</Message></Error>',
                'application/xml'
              )
            mock.uploadedAt = Date.now()
            return send(res, 204)
          }

          const jobMatch = /^\/jobs\/([\w-]+)$/.exec(path)
          if (method === 'GET' && jobMatch) {
            const mock = jobs.get(jobMatch[1]!)
            if (!mock) return send(res, 404, { message: 'Job not found' })
            return send(res, 200, refresh(mock, origin))
          }

          const file = /^\/files\/([\w-]+)\/(.+)$/.exec(path)
          if (method === 'GET' && file) {
            const mock = jobs.get(file[1]!)
            if (!mock) return send(res, 404, { message: 'Not found' })
            const ids = mock.job.instruments
            const rest = file[2]!
            if (rest === 'score.musicxml')
              return send(
                res,
                200,
                musicXml(ids),
                'application/vnd.recordare.musicxml+xml'
              )
            if (rest === 'score.mid')
              return send(res, 200, Buffer.from(midiFile(ids)), 'audio/midi')
            let m = /^parts\/(.+)\.musicxml$/.exec(rest)
            if (m)
              return send(
                res,
                200,
                musicXml([m[1]!]),
                'application/vnd.recordare.musicxml+xml'
              )
            m = /^midi\/(.+)\.mid$/.exec(rest)
            if (m)
              return send(
                res,
                200,
                Buffer.from(midiFile([m[1]!])),
                'audio/midi'
              )
            m = /^stems\/(.+)\.wav$/.exec(rest)
            if (m)
              return send(res, 200, Buffer.from(stemWav(m[1]!)), 'audio/wav')
          }

          send(res, 404, { message: 'Not found' })
        })().catch((err: unknown) => send(res, 500, { message: String(err) }))
      })
    },
  }
}
