import type {
  ApiErrorBody,
  Catalog,
  CreateJobRequest,
  CreateJobResponse,
  Job,
  PresignedPost,
} from './types'

export * from './types'

const DEFAULT_API_URL = 'http://localhost:8000'

/** Base URL of the API, without trailing slash. */
export const API_URL: string = (
  import.meta.env.VITE_API_URL || DEFAULT_API_URL
).replace(/\/+$/, '')

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

type FetchLike = typeof fetch

async function readError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as Partial<ApiErrorBody>
    if (body && typeof body.message === 'string') return body.message
  } catch {
    // body was not JSON
  }
  return res.statusText || `HTTP ${res.status}`
}

/** Human readable (Spanish) message for an API error. */
export function describeApiError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429)
      return `Se agotó la cuota diaria de trabajos para tu conexión. Intenta de nuevo mañana. (${err.message})`
    if (err.status === 400) return `Solicitud inválida: ${err.message}`
    if (err.status === 404)
      return 'No se encontró el trabajo. Puede que haya expirado (los archivos se borran a las 24 h).'
    return `Error del servidor (${err.status}): ${err.message}`
  }
  if (err instanceof TypeError)
    return 'No se pudo conectar con la API. Revisa tu conexión o la configuración de VITE_API_URL.'
  if (err instanceof Error) return err.message
  return 'Error desconocido'
}

/**
 * Builds the multipart body for an S3 presigned POST: every `fields` entry in
 * order and, last, the `file` field (S3 ignores fields after `file`).
 */
export function buildUploadForm(
  upload: PresignedPost,
  file: Blob,
  fileName: string
): FormData {
  const form = new FormData()
  for (const [key, value] of Object.entries(upload.fields)) {
    form.append(key, value)
  }
  form.append('file', file, fileName)
  return form
}

export function createApiClient(
  baseUrl: string = API_URL,
  fetchImpl: FetchLike = (...args) => fetch(...args)
) {
  async function request<T>(path: string, init?: RequestInit): Promise<T> {
    const res = await fetchImpl(`${baseUrl}${path}`, {
      ...init,
      headers: {
        Accept: 'application/json',
        ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
        ...init?.headers,
      },
    })
    if (!res.ok) throw new ApiError(res.status, await readError(res))
    return (await res.json()) as T
  }

  return {
    getInstruments(signal?: AbortSignal): Promise<Catalog> {
      return request<Catalog>('/instruments', { signal })
    },

    createJob(body: CreateJobRequest): Promise<CreateJobResponse> {
      return request<CreateJobResponse>('/jobs', {
        method: 'POST',
        body: JSON.stringify(body),
      })
    },

    getJob(jobId: string, signal?: AbortSignal): Promise<Job> {
      return request<Job>(`/jobs/${encodeURIComponent(jobId)}`, { signal })
    },

    /** Uploads the audio with the presigned POST returned by createJob. */
    async uploadAudio(
      upload: PresignedPost,
      file: Blob,
      fileName: string
    ): Promise<void> {
      const res = await fetchImpl(upload.url, {
        method: 'POST',
        body: buildUploadForm(upload, file, fileName),
      })
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        const s3Message = /<Message>([^<]*)<\/Message>/.exec(text)?.[1]
        throw new ApiError(
          res.status,
          s3Message || text.slice(0, 200) || 'Falló la subida del audio'
        )
      }
    },
  }
}

export type ApiClient = ReturnType<typeof createApiClient>

export const api: ApiClient = createApiClient()
