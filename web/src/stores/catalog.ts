import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api, describeApiError } from '@/api/client'
import type { Catalog, Instrument } from '@/api/types'

export const useCatalogStore = defineStore('catalog', () => {
  const catalog = ref<Catalog | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let pending: Promise<void> | null = null

  const instrumentsById = computed(() => {
    const map = new Map<string, Instrument>()
    for (const inst of catalog.value?.instruments ?? []) map.set(inst.id, inst)
    return map
  })

  function instrumentName(id: string): string {
    return instrumentsById.value.get(id)?.name ?? id
  }

  function load(force = false): Promise<void> {
    if (catalog.value && !force) return Promise.resolve()
    if (pending) return pending
    loading.value = true
    error.value = null
    pending = api
      .getInstruments()
      .then((data) => {
        catalog.value = data
      })
      .catch((err: unknown) => {
        error.value = describeApiError(err)
      })
      .finally(() => {
        loading.value = false
        pending = null
      })
    return pending
  }

  return { catalog, loading, error, instrumentsById, instrumentName, load }
})
