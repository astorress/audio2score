<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { Job, Stage } from '@/api/types'
import {
  ALL_STAGES,
  STAGE_HINTS,
  STAGE_LABELS,
  STATUS_LABELS,
} from '@/lib/labels'

const props = defineProps<{ job: Job }>()

const now = ref(Date.now())
const stageSince = ref<number>(Date.now())
let ticker: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  ticker = setInterval(() => (now.value = Date.now()), 1000)
})
onBeforeUnmount(() => {
  if (ticker) clearInterval(ticker)
})

watch(
  () => props.job.stage,
  () => (stageSince.value = Date.now())
)

const stages = computed<Stage[]>(() => {
  const mode = props.job.resolvedMode ?? props.job.mode
  return mode === 'orchestra'
    ? ALL_STAGES.filter((s) => s !== 'separation')
    : ALL_STAGES
})

type StepState = 'done' | 'current' | 'pending' | 'failed'

function stateOf(stage: Stage): StepState {
  const job = props.job
  if (job.status === 'DONE') return 'done'
  if (job.stage === stage) return job.status === 'FAILED' ? 'failed' : 'current'
  if (job.stages[stage] !== undefined) return 'done'
  const idx = stages.value.indexOf(stage)
  const cur = job.stage ? stages.value.indexOf(job.stage) : -1
  if (cur >= 0 && idx < cur) return 'done'
  return 'pending'
}

const totalElapsed = computed(() => {
  const created = Date.parse(props.job.createdAt)
  if (Number.isNaN(created)) return null
  return Math.max(0, Math.round((now.value - created) / 1000))
})

const currentElapsed = computed(() =>
  Math.max(0, Math.round((now.value - stageSince.value) / 1000))
)

function fmtSec(s: number | undefined): string {
  if (s === undefined) return ''
  return s < 60
    ? `${s.toFixed(1)} s`
    : `${Math.floor(s / 60)} min ${Math.round(s % 60)} s`
}

function fmtClock(s: number): string {
  const m = Math.floor(s / 60)
  return m ? `${m} min ${s % 60} s` : `${s} s`
}
</script>

<template>
  <section class="card space-y-6" aria-labelledby="progress-title">
    <div class="flex flex-wrap items-baseline gap-3">
      <h2 id="progress-title" class="mr-auto text-2xl font-semibold">
        {{ STATUS_LABELS[job.status] }}
      </h2>
      <span
        v-if="totalElapsed !== null"
        class="chip"
        title="Tiempo desde que se creó el trabajo"
      >
        ⏱ {{ fmtClock(totalElapsed) }}
      </span>
      <span class="chip"> modo: {{ job.resolvedMode ?? job.mode }} </span>
    </div>

    <div
      v-if="job.status === 'PENDING'"
      class="rounded-xl bg-paper-2 px-4 py-3 text-sm dark:bg-night-2"
    >
      Esperando a que el audio termine de llegar al almacenamiento. Si esto dura
      más de un par de minutos, la subida probablemente falló: vuelve a
      intentarlo desde el inicio.
    </div>

    <div
      v-if="job.status === 'QUEUED'"
      class="rounded-xl border border-accent/30 bg-accent/5 px-4 py-3 text-sm dark:border-accent-dk/30 dark:bg-accent-dk/10"
    >
      <p class="font-medium">Tu audio está en la cola del worker GPU.</p>
      <p class="mt-1">
        Para ahorrar costos, la GPU se apaga cuando nadie la usa (escala a
        cero). Si estaba apagada, arrancarla puede tardar
        <strong>varios minutos</strong> (arranque en frío). Puedes dejar esta
        pestaña abierta: la página se actualiza sola cada pocos segundos.
      </p>
    </div>

    <div
      v-if="job.status === 'FAILED'"
      role="alert"
      class="rounded-xl border border-amber/40 bg-amber/5 px-4 py-3 text-sm text-amber dark:border-amber-dk/40 dark:bg-amber-dk/10 dark:text-amber-dk"
    >
      <p class="font-medium">El procesamiento falló.</p>
      <p class="mt-1 font-mono">{{ job.error ?? 'Sin detalle del error.' }}</p>
    </div>

    <ol
      class="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      aria-label="Etapas del procesamiento"
    >
      <li
        v-for="(stage, i) in stages"
        :key="stage"
        class="relative rounded-xl border p-4 transition"
        :class="{
          'border-teal bg-teal/5 dark:border-teal-dk dark:bg-teal-dk/10':
            stateOf(stage) === 'done',
          'border-accent bg-accent/5 shadow-md dark:border-accent-dk dark:bg-accent-dk/10':
            stateOf(stage) === 'current',
          'border-amber bg-amber/5 dark:border-amber-dk':
            stateOf(stage) === 'failed',
          'border-line opacity-70 dark:border-night-line':
            stateOf(stage) === 'pending',
        }"
        :aria-current="stateOf(stage) === 'current' ? 'step' : undefined"
      >
        <div class="flex items-center gap-2">
          <span
            class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full font-mono text-xs font-semibold"
            :class="{
              'bg-teal text-white dark:bg-teal-dk dark:text-night':
                stateOf(stage) === 'done',
              'bg-accent text-white dark:bg-accent-dk dark:text-night':
                stateOf(stage) === 'current',
              'bg-amber text-white dark:bg-amber-dk dark:text-night':
                stateOf(stage) === 'failed',
              'bg-paper-2 dark:bg-night-2': stateOf(stage) === 'pending',
            }"
            aria-hidden="true"
          >
            <template v-if="stateOf(stage) === 'done'">✓</template>
            <template v-else-if="stateOf(stage) === 'failed'">!</template>
            <template v-else>{{ i + 1 }}</template>
          </span>
          <span class="font-medium">{{ STAGE_LABELS[stage] }}</span>
          <span
            v-if="stateOf(stage) === 'current'"
            class="ml-auto h-2.5 w-2.5 animate-pulse rounded-full bg-accent dark:bg-accent-dk"
            aria-hidden="true"
          />
        </div>
        <p class="muted mt-2 text-sm">{{ STAGE_HINTS[stage] }}</p>
        <p class="mt-2 font-mono text-xs">
          <template v-if="job.stages[stage] !== undefined">
            {{ fmtSec(job.stages[stage]) }}
          </template>
          <template v-else-if="stateOf(stage) === 'current'">
            en curso · {{ fmtClock(currentElapsed) }}
          </template>
          <template v-else-if="stateOf(stage) === 'pending'"
            >pendiente</template
          >
        </p>
        <span class="sr-only">
          Estado:
          {{
            {
              done: 'terminada',
              current: 'en curso',
              pending: 'pendiente',
              failed: 'falló',
            }[stateOf(stage)]
          }}
        </span>
      </li>
    </ol>

    <ul v-if="job.warnings.length" class="space-y-1 text-sm">
      <li v-for="(w, i) in job.warnings" :key="i" class="muted">⚠ {{ w }}</li>
    </ul>
  </section>
</template>
