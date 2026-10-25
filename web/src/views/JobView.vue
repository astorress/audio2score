<script setup lang="ts">
import { computed, defineAsyncComponent, onBeforeUnmount, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useJobStore } from '@/stores/job'
import { useCatalogStore } from '@/stores/catalog'
import JobProgress from '@/components/JobProgress.vue'
import StemMixer from '@/components/StemMixer.vue'
import PianoRoll from '@/components/PianoRoll.vue'
import Downloads from '@/components/Downloads.vue'

// OSMD + Tone are heavy: load them only when a result is shown.
const ScoreViewer = defineAsyncComponent(
  () => import('@/components/ScoreViewer.vue')
)

const props = defineProps<{ jobId: string }>()

const jobStore = useJobStore()
const catalog = useCatalogStore()
void catalog.load()

const job = computed(() =>
  jobStore.job?.jobId === props.jobId ? jobStore.job : null
)
const result = computed(() =>
  job.value?.status === 'DONE' ? job.value.result : null
)

const keyLabel = computed(() => {
  const k = result.value?.key
  if (!k) return '—'
  const [tonic, quality] = k.split(' ')
  const q = { major: 'mayor', minor: 'menor' }[quality ?? ''] ?? quality ?? ''
  const t: Record<string, string> = {
    C: 'Do',
    D: 'Re',
    E: 'Mi',
    F: 'Fa',
    G: 'Sol',
    A: 'La',
    B: 'Si',
  }
  const name = tonic
    ? (t[tonic[0]!.toUpperCase()] ?? tonic[0]) +
      tonic.slice(1).replace(/#/g, '♯').replace(/-|b/g, '♭')
    : ''
  return `${name} ${q}`.trim() + ` (${k})`
})

const expiresLabel = computed(() => {
  const iso = job.value?.expiresAt
  if (!iso) return null
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return null
  return d.toLocaleString('es-CO', { dateStyle: 'medium', timeStyle: 'short' })
})

watch(
  () => props.jobId,
  (id) => jobStore.start(id),
  { immediate: true }
)
onBeforeUnmount(() => jobStore.stop())
</script>

<template>
  <div class="space-y-6">
    <div class="flex flex-wrap items-center gap-3">
      <div class="mr-auto">
        <p class="label">Trabajo</p>
        <h1 class="mt-1 text-3xl font-semibold">
          {{ result ? 'Resultado' : 'Procesando tu audio' }}
        </h1>
        <p class="muted mt-1 font-mono text-xs break-all">{{ jobId }}</p>
      </div>
      <RouterLink to="/" class="btn-ghost">Nuevo audio</RouterLink>
    </div>

    <div
      v-if="jobStore.error"
      role="alert"
      class="rounded-xl border border-amber/40 bg-amber/5 px-4 py-3 text-sm text-amber dark:border-amber-dk/40 dark:bg-amber-dk/10 dark:text-amber-dk"
    >
      {{ jobStore.error }}
      <span v-if="!jobStore.notFound"> Reintentando…</span>
    </div>

    <p v-if="!job && !jobStore.notFound" class="muted" role="status">
      Consultando el estado del trabajo…
    </p>

    <JobProgress v-if="job && !result" :job="job" />

    <template v-if="job && result">
      <div
        class="rounded-xl border border-amber/40 bg-amber/5 px-4 py-3 text-sm dark:border-amber-dk/40 dark:bg-amber-dk/10"
        role="note"
      >
        <strong class="text-amber dark:text-amber-dk"
          >Partitura aproximada.</strong
        >
        Se generó automáticamente a partir del audio: puede tener notas
        fantasma, ritmos simplificados o instrumentos confundidos. Úsala como
        punto de partida, no como edición final.
      </div>

      <section class="card" aria-label="Resumen del análisis">
        <dl class="grid grid-cols-2 gap-4 sm:grid-cols-5">
          <div>
            <dt class="label">Tonalidad</dt>
            <dd class="mt-1 font-medium">{{ keyLabel }}</dd>
          </div>
          <div>
            <dt class="label">Tempo</dt>
            <dd class="mt-1 font-mono">{{ Math.round(result.tempo) }} BPM</dd>
          </div>
          <div>
            <dt class="label">Compás</dt>
            <dd class="mt-1 font-mono">{{ result.timeSignature }}</dd>
          </div>
          <div>
            <dt class="label">Ruta</dt>
            <dd class="mt-1">
              {{
                job.resolvedMode === 'orchestra'
                  ? 'Orquesta'
                  : job.resolvedMode === 'rock'
                    ? 'Rock / banda'
                    : job.mode
              }}
            </dd>
          </div>
          <div>
            <dt class="label">Duración</dt>
            <dd class="mt-1 font-mono">
              {{ result.durationSec.toFixed(1) }} s
            </dd>
          </div>
        </dl>
        <div class="mt-4 flex flex-wrap gap-2">
          <span v-for="id in job.instruments" :key="id" class="chip">
            {{ catalog.instrumentName(id) }}
          </span>
        </div>
        <ul
          v-if="job.warnings.length"
          class="mt-4 space-y-1 text-sm"
          aria-label="Advertencias"
        >
          <li
            v-for="(w, i) in job.warnings"
            :key="i"
            class="text-amber dark:text-amber-dk"
          >
            ⚠ {{ w }}
          </li>
        </ul>
        <p v-if="expiresLabel" class="muted mt-4 text-xs">
          Los archivos se borrarán el {{ expiresLabel }}
        </p>
      </section>

      <StemMixer v-if="result.stems.length" :stems="result.stems" />
      <ScoreViewer :key="job.jobId" :result="result" />
      <PianoRoll v-if="result.midi.length" :midi="result.midi" />
      <Downloads :result="result" />
    </template>
  </div>
</template>
