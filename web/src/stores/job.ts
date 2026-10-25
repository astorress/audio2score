import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, api, describeApiError } from '@/api/client'
import type { Job } from '@/api/types'

export const POLL_INTERVAL_MS = 3000

/** Holds the job being viewed and polls GET /jobs/{id} until it settles. */
export const useJobStore = defineStore('job', () => {
  const job = ref<Job | null>(null)
  const error = ref<string | null>(null)
  const notFound = ref(false)
  const lastPolledAt = ref<number | null>(null)
  let timer: ReturnType<typeof setTimeout> | null = null
  let controller: AbortController | null = null
  let activeId: string | null = null

  const isFinal = computed(
    () => job.value?.status === 'DONE' || job.value?.status === 'FAILED'
  )

  async function poll(jobId: string): Promise<void> {
    controller = new AbortController()
    try {
      const data = await api.getJob(jobId, controller.signal)
      if (activeId !== jobId) return
      job.value = data
      error.value = null
      lastPolledAt.value = Date.now()
    } catch (err) {
      if (activeId !== jobId) return
      if (err instanceof DOMException && err.name === 'AbortError') return
      if (err instanceof ApiError && err.status === 404) {
        notFound.value = true
        error.value = describeApiError(err)
        stop()
        return
      }
      // Transient errors: keep polling, show the message.
      error.value = describeApiError(err)
    }
    if (activeId === jobId && !isFinal.value) {
      timer = setTimeout(() => void poll(jobId), POLL_INTERVAL_MS)
    }
  }

  function start(jobId: string): void {
    stop()
    if (job.value?.jobId !== jobId) job.value = null
    activeId = jobId
    error.value = null
    notFound.value = false
    void poll(jobId)
  }

  function stop(): void {
    activeId = null
    if (timer) clearTimeout(timer)
    timer = null
    controller?.abort()
    controller = null
  }

  return { job, error, notFound, lastPolledAt, isFinal, start, stop }
})
