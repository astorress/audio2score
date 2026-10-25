<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin, {
  type Region,
} from 'wavesurfer.js/dist/plugins/regions.esm.js'
import { formatTime } from '@/lib/midi'

export interface CropRegion {
  start: number
  end: number
}

const props = defineProps<{
  file: File
  audio: AudioBuffer
  maxDurationSec: number
}>()

const region = defineModel<CropRegion>('region', { required: true })

const container = ref<HTMLDivElement | null>(null)
const playing = ref(false)
const currentTime = ref(0)
const ready = ref(false)

let ws: WaveSurfer | null = null
let regions: RegionsPlugin | null = null
let cropRegion: Region | null = null
let objectUrl: string | null = null
let darkQuery: MediaQueryList | null = null

const duration = computed(() => props.audio.duration)
const length = computed(() => region.value.end - region.value.start)

function colors() {
  const dark = darkQuery?.matches ?? false
  return {
    waveColor: dark ? '#343c57' : '#c9c3b0',
    progressColor: dark ? '#7c9cff' : '#3f5bd8',
    cursorColor: dark ? '#5eead4' : '#0d9488',
    regionColor: dark ? 'rgba(124,156,255,0.18)' : 'rgba(63,91,216,0.14)',
  }
}

function clampRegion(start: number, end: number): CropRegion {
  const max = Math.min(props.maxDurationSec, duration.value)
  let s = Math.max(0, Math.min(start, duration.value))
  let e = Math.max(0, Math.min(end, duration.value))
  if (e < s) [s, e] = [e, s]
  if (e - s > max) e = s + max
  if (e - s < 0.5) e = Math.min(duration.value, s + 0.5)
  return { start: s, end: e }
}

function peaksFor(audio: AudioBuffer): Float32Array[] {
  // Down-sample to ~8000 points per channel: plenty for drawing.
  const points = Math.min(8000, audio.length)
  const step = audio.length / points
  const out: Float32Array[] = []
  for (let c = 0; c < Math.min(2, audio.numberOfChannels); c++) {
    const data = audio.getChannelData(c)
    const peaks = new Float32Array(points)
    for (let i = 0; i < points; i++) {
      const from = Math.floor(i * step)
      const to = Math.min(audio.length, Math.floor((i + 1) * step))
      let max = 0
      for (let j = from; j < to; j++) {
        const v = Math.abs(data[j]!)
        if (v > max) max = v
      }
      peaks[i] = max
    }
    out.push(peaks)
  }
  return out
}

function build() {
  destroy()
  if (!container.value) return
  const c = colors()
  objectUrl = URL.createObjectURL(props.file)
  ws = WaveSurfer.create({
    container: container.value,
    url: objectUrl,
    peaks: peaksFor(props.audio),
    duration: duration.value,
    height: 120,
    waveColor: c.waveColor,
    progressColor: c.progressColor,
    cursorColor: c.cursorColor,
    barWidth: 2,
    barGap: 1,
    barRadius: 2,
    normalize: true,
    dragToSeek: true,
  })
  regions = ws.registerPlugin(RegionsPlugin.create())

  ws.on('ready', () => {
    ready.value = true
    const initial = clampRegion(
      0,
      Math.min(duration.value, props.maxDurationSec)
    )
    region.value = initial
    cropRegion = regions!.addRegion({
      start: initial.start,
      end: initial.end,
      color: c.regionColor,
      drag: true,
      resize: true,
      maxLength: props.maxDurationSec,
      minLength: 0.5,
    })
  })
  ws.on('play', () => (playing.value = true))
  ws.on('pause', () => (playing.value = false))
  ws.on('finish', () => (playing.value = false))
  ws.on('timeupdate', (t) => (currentTime.value = t))

  const sync = (r: Region) => {
    const next = clampRegion(r.start, r.end)
    region.value = next
    if (
      Math.abs(next.start - r.start) > 1e-3 ||
      Math.abs(next.end - r.end) > 1e-3
    )
      r.setOptions({ start: next.start, end: next.end })
  }
  regions.on('region-update', sync)
  regions.on('region-updated', sync)
}

function destroy() {
  ws?.destroy()
  ws = null
  regions = null
  cropRegion = null
  ready.value = false
  playing.value = false
  if (objectUrl) URL.revokeObjectURL(objectUrl)
  objectUrl = null
}

function togglePlay() {
  if (!ws || !cropRegion) return
  if (playing.value) {
    ws.pause()
  } else {
    cropRegion.play(true)
  }
}

function setBound(which: 'start' | 'end', value: number) {
  if (!Number.isFinite(value)) return
  const cur = region.value
  // Keep the length when moving the start past the allowed span.
  const next =
    which === 'start'
      ? clampRegion(value, Math.max(cur.end, value + 0.5))
      : clampRegion(Math.max(cur.start, value - props.maxDurationSec), value)
  region.value = next
  cropRegion?.setOptions({ start: next.start, end: next.end })
}

function onInput(which: 'start' | 'end', e: Event) {
  setBound(which, Number((e.target as HTMLInputElement).value))
}

onMounted(() => {
  darkQuery = window.matchMedia('(prefers-color-scheme: dark)')
  build()
})
watch(
  () => props.audio,
  () => build()
)
onBeforeUnmount(destroy)
</script>

<template>
  <div class="space-y-4">
    <div
      ref="container"
      class="min-h-[120px] w-full overflow-hidden rounded-xl bg-paper-2/60 dark:bg-night-2/60"
      role="img"
      :aria-label="`Forma de onda de ${file.name}. Región seleccionada de ${formatTime(region.start)} a ${formatTime(region.end)}.`"
    />

    <div class="flex flex-wrap items-end gap-4">
      <button
        type="button"
        class="btn-primary"
        :disabled="!ready"
        :aria-pressed="playing"
        @click="togglePlay"
      >
        <svg
          v-if="!playing"
          aria-hidden="true"
          viewBox="0 0 24 24"
          class="h-4 w-4"
          fill="currentColor"
        >
          <path d="M8 5v14l11-7z" />
        </svg>
        <svg
          v-else
          aria-hidden="true"
          viewBox="0 0 24 24"
          class="h-4 w-4"
          fill="currentColor"
        >
          <path d="M6 5h4v14H6zM14 5h4v14h-4z" />
        </svg>
        {{ playing ? 'Pausar' : 'Escuchar región' }}
      </button>

      <label class="flex flex-col gap-1 text-sm">
        <span class="label">Inicio (s)</span>
        <input
          class="input w-28 font-mono"
          type="number"
          min="0"
          :max="duration"
          step="0.1"
          :value="region.start.toFixed(1)"
          :disabled="!ready"
          @change="onInput('start', $event)"
        />
      </label>
      <label class="flex flex-col gap-1 text-sm">
        <span class="label">Fin (s)</span>
        <input
          class="input w-28 font-mono"
          type="number"
          min="0"
          :max="duration"
          step="0.1"
          :value="region.end.toFixed(1)"
          :disabled="!ready"
          @change="onInput('end', $event)"
        />
      </label>

      <p class="muted ml-auto font-mono text-sm" aria-live="polite">
        Región: {{ length.toFixed(1) }} s / máx. {{ maxDurationSec }} s · Total:
        {{ formatTime(duration) }}
        <span v-if="playing"> · ▶ {{ formatTime(currentTime) }}</span>
      </p>
    </div>
    <p class="muted text-sm">
      Arrastra la región para moverla o sus bordes para recortarla. Solo se
      envía el fragmento seleccionado (máximo {{ maxDurationSec }} s).
    </p>
  </div>
</template>
