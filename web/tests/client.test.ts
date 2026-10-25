import { describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  buildUploadForm,
  createApiClient,
  describeApiError,
} from '../src/api/client'
import type { PresignedPost } from '../src/api/types'

const upload: PresignedPost = {
  url: 'https://bucket.s3.amazonaws.com/',
  fields: {
    key: 'uploads/abc.wav',
    'Content-Type': 'audio/wav',
    policy: 'eyJ...',
    'x-amz-signature': 'sig',
  },
}

describe('buildUploadForm', () => {
  it('appends every field in order and the file last', () => {
    const blob = new Blob([new Uint8Array(8)], { type: 'audio/wav' })
    const form = buildUploadForm(upload, blob, 'fragmento.wav')
    const keys = [...form.keys()]
    expect(keys).toEqual([...Object.keys(upload.fields), 'file'])
    expect(keys.at(-1)).toBe('file')
    expect(form.get('key')).toBe('uploads/abc.wav')
    const file = form.get('file') as File
    expect(file.name).toBe('fragmento.wav')
    expect(file.size).toBe(8)
  })
})

describe('createApiClient', () => {
  it('POSTs the multipart form to upload.url without JSON headers', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    const client = createApiClient(
      'http://api',
      fetchMock as unknown as typeof fetch
    )
    await client.uploadAudio(upload, new Blob(['x']), 'a.wav')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ]
    expect(url).toBe(upload.url)
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect(init.headers).toBeUndefined()
    expect([...(init.body as FormData).keys()].at(-1)).toBe('file')
  })

  it('creates a job with a JSON body', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          JSON.stringify({
            jobId: 'j1',
            status: 'PENDING',
            upload,
            expiresInSec: 600,
          }),
          {
            status: 201,
          }
        )
    )
    const client = createApiClient(
      'http://api',
      fetchMock as unknown as typeof fetch
    )
    const res = await client.createJob({
      mode: 'rock',
      fileName: 'a.wav',
      contentType: 'audio/wav',
      sizeBytes: 100,
      durationSec: 10,
    })
    expect(res.jobId).toBe('j1')
    const [url, init] = fetchMock.mock.calls[0] as unknown as [
      string,
      RequestInit,
    ]
    expect(url).toBe('http://api/jobs')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body as string)).toMatchObject({
      mode: 'rock',
      sizeBytes: 100,
    })
    expect((init.headers as Record<string, string>)['Content-Type']).toBe(
      'application/json'
    )
  })

  it('maps 400 / 429 to ApiError with the server message', async () => {
    for (const status of [400, 429]) {
      const fetchMock = vi.fn(
        async () =>
          new Response(JSON.stringify({ message: `m${status}` }), { status })
      )
      const client = createApiClient(
        'http://api',
        fetchMock as unknown as typeof fetch
      )
      const err = await client.getInstruments().catch((e: unknown) => e)
      expect(err).toBeInstanceOf(ApiError)
      expect((err as ApiError).status).toBe(status)
      expect((err as ApiError).message).toBe(`m${status}`)
    }
    expect(describeApiError(new ApiError(429, 'x'))).toMatch(/cuota diaria/)
    expect(describeApiError(new ApiError(400, 'malo'))).toMatch(/malo/)
  })

  it('reports S3 XML errors from the upload', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(
          '<Error><Code>EntityTooLarge</Code><Message>Too big</Message></Error>',
          {
            status: 400,
          }
        )
    )
    const client = createApiClient(
      'http://api',
      fetchMock as unknown as typeof fetch
    )
    await expect(
      client.uploadAudio(upload, new Blob(['x']), 'a.wav')
    ).rejects.toMatchObject({
      status: 400,
      message: 'Too big',
    })
  })
})
