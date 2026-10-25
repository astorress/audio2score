<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from 'vue'
import type { MidiEntry } from '@/api/types'
import {
  type RollNote,
  extractNotes,
  isBlackKey,
  layoutNotes,
  loadMidi,
  noteName,
  notesDuration,
  pitchRange,
} from '@/lib/midi'

const props = defineProps<{ midi: MidiEntry[] }>()

const selected = ref(props.midi[0]?.instrument ?? '')
const notes = shallowRef<RollNote[]>([])
const loading = ref(false)
const error = ref<string | null>(null)
const canvas = ref<HTMLCanvasElement | null>(null)
const wrapper = ref<HTMLDivElement | null>(null)
const pxPerSec = ref(60)

const KEY_W = 36
const ROW_H = 7

const entry = computed(() =>
  props.midi.find((m) => m.instrument === selected.value)
)
const range = computed(() => pitchRange(notes.value))
const duration = computed(() => Math.max(1, notesDuration(notes.value)))
const percussion = computed(
  () => notes.value.length > 0 && notes.value.every((n) => n.percussion)
)

let resizeObs: ResizeObserver | null = null
let darkQuery: MediaQueryList | null = null

function palette() {
  const dark = darkQuery?.matches ?? false
  return dark
    ? {
        bg: '#0e1018',
        black: '#0a0c12',
        line: '#1f2433',
        bar: '#343c57',
        text: '#8e97b3',
        note: '#7c9cff',
        perc: '#5eead4',
      }
    : {
        bg: '#fffdf8',
        black: '#ece9e0',
        line: '#e1ddd0',
        bar: '#c9c3b0',
        text: '#5d6275',
        note: '#3f5bd8',
        perc: '#0d9488',
      }
}

function draw() {
  const el = canvas.value
  if (!el) return
  const rows = range.value.max - range.value.min + 1
  const width = KEY_W + Math.ceil(duration.value * pxPerSec.value)
  const height = rows * ROW_H
  const dpr = window.devicePixelRatio || 1
  el.width = width * dpr
  el.height = height * dpr
  el.style.width = `${width}px`
  el.style.height = `${height}px`
  const ctx = el.getContext('2d')
  if (!ctx) return
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  const c = palette()

  ctx.fillStyle = c.bg
  ctx.fillRect(0, 0, width, height)

  // Pitch rows (black keys shaded) and octave labels.
  ctx.font = '9px "JetBrains Mono", monospace'
  ctx.textBaseline = 'middle'
  for (let p = range.value.max; p >= range.value.min; p--) {
    const y = (range.value.max - p) * ROW_H
    if (isBlackKey(p)) {
      ctx.fillStyle = c.black
      ctx.fillRect(0, y, width, ROW_H)
    }
    if (p % 12 === 0) {
      ctx.fillStyle = c.bar
      ctx.fillRect(0, y + ROW_H - 0.5, width, 0.5)
      ctx.fillStyle = c.text
      ctx.fillText(noteName(p), 2, y + ROW_H / 2)
    }
  }

  // Second grid.
  ctx.fillStyle = c.line
  for (let s = 0; s <= duration.value; s++) {
    const x = KEY_W + s * pxPerSec.value
    ctx.fillRect(x, 0, s % 5 === 0 ? 1 : 0.5, height)
  }
  ctx.fillStyle = c.bar
  ctx.fillRect(KEY_W - 1, 0, 1, height)

  // Notes.
  const rects = layoutNotes(notes.value, {
    width: duration.value * pxPerSec.value,
    height,
    duration: duration.value,
    range: range.value,
  })
  for (const r of rects) {
    ctx.globalAlpha = 0.35 + 0.65 * r.note.velocity
    ctx.fillStyle = r.note.percussion ? c.perc : c.note
    ctx.fillRect(KEY_W + r.x, r.y + 0.5, r.w, r.h - 1)
  }
  ctx.globalAlpha = 1
}

async function load() {
  const e = entry.value
  notes.value = []
  error.value = null
  if (!e) return
  loading.value = true
  try {
    const midi = await loadMidi(e.url)
    if (entry.value !== e) return
    notes.value = extractNotes(midi)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    loading.value = false
  }
}

watch(selected, () => void load())
watch([notes, pxPerSec], draw)

onMounted(() => {
  darkQuery = window.matchMedia('(prefers-color-scheme: dark)')
  darkQuery.addEventListener('change', draw)
  resizeObs = new ResizeObserver(() => draw())
  if (wrapper.value) resizeObs.observe(wrapper.value)
  void load()
})
onBeforeUnmount(() => {
  darkQuery?.removeEventListener('change', draw)
  resizeObs?.disconnect()
})
</script>

<template>
  <section class="card space-y-4" aria-labelledby="roll-title">
    <div class="flex flex-wrap items-center gap-3">
      <h2 id="roll-title" class="mr-auto text-xl font-semibold">Piano-roll</h2>
      <label class="flex items-center gap-2 text-sm">
        <span>Instrumento</span>
        <select v-model="selected" class="input">
          <option v-for="m in midi" :key="m.instrument" :value="m.instrument">
            {{ m.name }} ({{ m.notes }} notas)
          </option>
        </select>
      </label>
      <label class="flex items-center gap-2 text-sm">
        <span>Zoom</span>
        <input
          v-model.number="pxPerSec"
          type="range"
          min="20"
          max="240"
          step="10"
          aria-label="Píxeles por segundo"
        />
      </label>
    </div>
    <p v-if="loading" class="muted text-sm" role="status">Cargando MIDI…</p>
    <p v-if="error" class="text-sm text-amber dark:text-amber-dk" role="alert">
      {{ error }}
    </p>
    <div
      ref="wrapper"
      class="max-h-[420px] overflow-auto rounded-xl ring-1 ring-line dark:ring-night-line"
    >
      <canvas
        ref="canvas"
        role="img"
        :aria-label="`Piano-roll de ${entry?.name ?? ''}: ${notes.length} notas entre ${noteName(range.min)} y ${noteName(range.max)}, ${duration.toFixed(1)} s`"
      />
    </div>
    <p class="muted text-xs">
      Eje horizontal: tiempo (líneas cada segundo). Eje vertical: altura MIDI.
      La opacidad indica la velocidad (intensidad).
      <template v-if="percussion">
        En batería la altura es la pieza (General MIDI: 36 bombo, 38 caja, 42
        hi-hat…).
      </template>
      Útil para ver qué detectó la transcripción antes de cuantizar.
    </p>
  </section>
</template>
