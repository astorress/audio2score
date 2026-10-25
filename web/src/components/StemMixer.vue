<script setup lang="ts">
import {
  computed,
  markRaw,
  onBeforeUnmount,
  onMounted,
  reactive,
  ref,
} from 'vue'
import type { Stem } from '@/api/types'
import { getAudioContext } from '@/lib/audio'
import { formatTime } from '@/lib/midi'

const props = defineProps<{ stems: Stem[] }>()

interface Track {
  stem: Stem
  buffer: AudioBuffer | null
  gain: GainNode | null
  source: AudioBufferSourceNode | null
  volume: number
  muted: boolean
  solo: boolean
  error: string | null
}

const tracks = reactive<Track[]>(
  props.stems.map((stem) => ({
    stem,
    buffer: null,
    gain: null,
    source: null,
    volume: 0.8,
    muted: false,
    solo: false,
    error: null,
  }))
)

const loading = ref(true)
const playing = ref(false)
const position = ref(0)
let ctx: AudioContext | null = null
let master: GainNode | null = null
let startedAt = 0 // ctx time when playback (re)started
let offsetAt = 0 // song position at startedAt
let raf = 0
const controller = new AbortController()

const duration = computed(() =>
  tracks.reduce((acc, t) => Math.max(acc, t.buffer?.duration ?? 0), 0)
)
const anySolo = computed(() => tracks.some((t) => t.solo))
const loadedCount = computed(() => tracks.filter((t) => t.buffer).length)

function effectiveGain(t: Track): number {
  if (t.muted) return 0
  if (anySolo.value && !t.solo) return 0
  return t.volume
}

function applyGains() {
  if (!ctx) return
  for (const t of tracks) {
    t.gain?.gain.setTargetAtTime(effectiveGain(t), ctx.currentTime, 0.015)
  }
}

async function loadAll() {
  ctx = getAudioContext()
  master = ctx.createGain()
  master.connect(ctx.destination)
  await Promise.all(
    tracks.map(async (t) => {
      try {
        const res = await fetch(t.stem.url, { signal: controller.signal })
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const data = await res.arrayBuffer()
        // markRaw: native Web Audio objects must not be wrapped in proxies.
        t.buffer = markRaw(await ctx!.decodeAudioData(data))
        t.gain = markRaw(ctx!.createGain())
        t.gain.gain.value = effectiveGain(t)
        t.gain.connect(master!)
      } catch (err) {
        if (controller.signal.aborted) return
        t.error = err instanceof Error ? err.message : String(err)
      }
    })
  )
  loading.value = false
}

function currentPosition(): number {
  if (!ctx || !playing.value) return position.value
  return Math.min(duration.value, offsetAt + (ctx.currentTime - startedAt))
}

function stopSources() {
  for (const t of tracks) {
    if (t.source) {
      t.source.onended = null
      try {
        t.source.stop()
      } catch {
        // already stopped
      }
      t.source.disconnect()
      t.source = null
    }
  }
}

function tick() {
  position.value = currentPosition()
  if (playing.value && position.value >= duration.value - 0.01) {
    pause()
    position.value = 0
    return
  }
  if (playing.value) raf = requestAnimationFrame(tick)
}

async function play(from = position.value) {
  if (!ctx || loadedCount.value === 0) return
  if (ctx.state === 'suspended') await ctx.resume()
  stopSources()
  const when = ctx.currentTime + 0.05
  for (const t of tracks) {
    if (!t.buffer || !t.gain) continue
    const src = ctx.createBufferSource()
    src.buffer = t.buffer
    src.connect(t.gain)
    if (from < t.buffer.duration) src.start(when, from)
    t.source = markRaw(src)
  }
  startedAt = when
  offsetAt = from
  playing.value = true
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(tick)
}

function pause() {
  position.value = currentPosition()
  stopSources()
  playing.value = false
  cancelAnimationFrame(raf)
}

function toggle() {
  if (playing.value) pause()
  else void play()
}

function seek(sec: number) {
  const target = Math.max(0, Math.min(duration.value, sec))
  position.value = target
  if (playing.value) void play(target)
}

function onSeekInput(e: Event) {
  seek(Number((e.target as HTMLInputElement).value))
}

function onKey(e: KeyboardEvent) {
  const target = e.target as HTMLElement | null
  if (target?.closest('button, input, select')) return
  if (e.key === ' ' || e.key === 'k') {
    e.preventDefault()
    toggle()
  }
}

function setVolume(t: Track, e: Event) {
  t.volume = Number((e.target as HTMLInputElement).value)
  applyGains()
}
function toggleMute(t: Track) {
  t.muted = !t.muted
  applyGains()
}
function toggleSolo(t: Track) {
  t.solo = !t.solo
  applyGains()
}

onMounted(() => void loadAll())
onBeforeUnmount(() => {
  controller.abort()
  cancelAnimationFrame(raf)
  stopSources()
  for (const t of tracks) t.gain?.disconnect()
  master?.disconnect()
})
</script>

<template>
  <section
    class="card space-y-4"
    aria-labelledby="mixer-title"
    tabindex="-1"
    @keydown="onKey"
  >
    <div class="flex flex-wrap items-center gap-3">
      <h2 id="mixer-title" class="mr-auto text-xl font-semibold">
        Mezclador de stems
      </h2>
      <span v-if="loading" class="muted text-sm" role="status">
        Cargando stems… {{ loadedCount }}/{{ tracks.length }}
      </span>
    </div>

    <div
      class="flex flex-wrap items-center gap-3"
      role="group"
      aria-label="Transporte del mezclador"
    >
      <button
        type="button"
        class="btn-primary"
        :disabled="loading || loadedCount === 0"
        :aria-pressed="playing"
        @click="toggle"
      >
        {{ playing ? '❚❚ Pausar' : '▶ Reproducir' }}
      </button>
      <button
        type="button"
        class="btn-ghost"
        :disabled="loading"
        aria-label="Volver al inicio"
        @click="seek(0)"
      >
        ⏮
      </button>
      <input
        class="min-w-40 flex-1"
        type="range"
        min="0"
        :max="duration || 0"
        step="0.01"
        :value="position"
        :disabled="loading || !duration"
        aria-label="Posición de reproducción"
        :aria-valuetext="`${formatTime(position)} de ${formatTime(duration)}`"
        @input="onSeekInput"
      />
      <span class="font-mono text-sm tabular-nums" aria-hidden="true">
        {{ formatTime(position) }} / {{ formatTime(duration) }}
      </span>
    </div>

    <ul class="divide-y divide-line dark:divide-night-line" aria-label="Pistas">
      <li
        v-for="t in tracks"
        :key="t.stem.name"
        class="flex flex-wrap items-center gap-3 py-3"
        role="group"
        :aria-label="`Pista ${t.stem.label}`"
      >
        <span class="w-28 shrink-0 font-medium">{{ t.stem.label }}</span>
        <button
          type="button"
          class="btn-ghost h-8 w-8 !p-0 font-mono"
          :class="
            t.muted
              ? '!bg-amber !text-white dark:!bg-amber-dk dark:!text-night'
              : ''
          "
          :aria-pressed="t.muted"
          :aria-label="`Silenciar ${t.stem.label}`"
          :disabled="!t.buffer"
          @click="toggleMute(t)"
        >
          M
        </button>
        <button
          type="button"
          class="btn-ghost h-8 w-8 !p-0 font-mono"
          :class="
            t.solo
              ? '!bg-teal !text-white dark:!bg-teal-dk dark:!text-night'
              : ''
          "
          :aria-pressed="t.solo"
          :aria-label="`Solo ${t.stem.label}`"
          :disabled="!t.buffer"
          @click="toggleSolo(t)"
        >
          S
        </button>
        <input
          class="min-w-32 flex-1"
          type="range"
          min="0"
          max="1"
          step="0.01"
          :value="t.volume"
          :disabled="!t.buffer"
          :aria-label="`Volumen de ${t.stem.label}`"
          :aria-valuetext="`${Math.round(t.volume * 100)} %`"
          @input="setVolume(t, $event)"
        />
        <span
          class="w-12 text-right font-mono text-xs tabular-nums"
          aria-hidden="true"
        >
          {{ Math.round(t.volume * 100) }}%
        </span>
        <span v-if="effectiveGain(t) === 0 && t.buffer" class="muted text-xs">
          (no suena)
        </span>
        <p
          v-if="t.error"
          class="w-full text-xs text-amber dark:text-amber-dk"
          role="alert"
        >
          No se pudo cargar: {{ t.error }}
        </p>
      </li>
    </ul>
    <p class="muted text-xs">
      M = silenciar, S = solo. Barra espaciadora o K: reproducir/pausar (con el
      foco en el mezclador, fuera de los controles).
    </p>
  </section>
</template>
