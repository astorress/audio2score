<script setup lang="ts">
import {
  computed,
  onBeforeUnmount,
  onMounted,
  ref,
  shallowRef,
  watch,
} from 'vue'
import type { OpenSheetMusicDisplay } from 'opensheetmusicdisplay'
import type { Midi } from '@tonejs/midi'
import type { JobResult } from '@/api/types'
import {
  formatTime,
  loadMidi,
  stepIndexAt,
  wholeNotesToSeconds,
} from '@/lib/midi'

type ToneModule = typeof import('tone')

const props = defineProps<{ result: JobResult }>()

const FULL = '__full__'
const selection = ref<string>(FULL)

const container = ref<HTMLDivElement | null>(null)
const rendering = ref(false)
const renderError = ref<string | null>(null)
const playError = ref<string | null>(null)
const playing = ref(false)
const preparing = ref(false)
const position = ref(0)
const zoom = ref(1)

let osmd: OpenSheetMusicDisplay | null = null
let Tone: ToneModule | null = null
let stepTimes: number[] = []
let cursorIndex = 0
let raf = 0
let renderToken = 0
let disposeAudio: (() => void) | null = null
const midiDuration = shallowRef(0)

const scoreUrl = computed(() => {
  if (selection.value === FULL) return props.result.score.musicxml
  return props.result.parts.find((p) => p.instrument === selection.value)?.url
})

const midiUrl = computed(() => {
  if (selection.value === FULL) return props.result.midiFull
  return props.result.midi.find((m) => m.instrument === selection.value)?.url
})

const tempo = computed(() =>
  props.result.tempo > 0 ? props.result.tempo : 120
)

async function ensureOsmd(): Promise<OpenSheetMusicDisplay> {
  if (osmd) return osmd
  const { OpenSheetMusicDisplay } = await import('opensheetmusicdisplay')
  osmd = new OpenSheetMusicDisplay(container.value!, {
    autoResize: true,
    backend: 'svg',
    drawTitle: true,
    drawingParameters: 'default',
    followCursor: true,
    cursorsOptions: [{ type: 0, color: '#3f5bd8', alpha: 0.5, follow: true }],
  })
  return osmd
}

/** Precomputes the time (s) of every cursor step from its timestamp. */
function buildStepTimes(o: OpenSheetMusicDisplay) {
  const cursor = o.cursor
  cursor.reset()
  const times: number[] = []
  // Guard against pathological scores.
  for (let i = 0; i < 20000 && !cursor.Iterator.EndReached; i++) {
    times.push(
      wholeNotesToSeconds(
        cursor.Iterator.currentTimeStamp.RealValue,
        tempo.value
      )
    )
    cursor.next()
  }
  cursor.reset()
  stepTimes = times
  cursorIndex = 0
}

async function renderScore() {
  const url = scoreUrl.value
  const token = ++renderToken
  renderError.value = null
  if (!url) {
    renderError.value = 'No hay MusicXML para esta selección.'
    return
  }
  rendering.value = true
  try {
    const res = await fetch(url)
    if (!res.ok)
      throw new Error(`No se pudo descargar el MusicXML (${res.status})`)
    const xml = await res.text()
    const o = await ensureOsmd()
    if (token !== renderToken) return
    o.zoom = zoom.value
    await o.load(xml)
    if (token !== renderToken) return
    o.render()
    o.cursor.show()
    buildStepTimes(o)
  } catch (err) {
    if (token === renderToken)
      renderError.value =
        err instanceof Error
          ? err.message
          : 'No se pudo renderizar la partitura.'
  } finally {
    if (token === renderToken) rendering.value = false
  }
}

function moveCursorTo(index: number) {
  if (!osmd || stepTimes.length === 0) return
  const target = Math.max(0, Math.min(stepTimes.length - 1, index))
  if (target === cursorIndex) return
  const cursor = osmd.cursor
  if (target < cursorIndex) {
    cursor.reset()
    cursorIndex = 0
  }
  while (cursorIndex < target && !cursor.Iterator.EndReached) {
    cursor.next()
    cursorIndex++
  }
}

function tick() {
  if (!Tone || !playing.value) return
  const t = Tone.getTransport().seconds
  position.value = t
  moveCursorTo(stepIndexAt(stepTimes, t))
  if (t >= midiDuration.value + 0.3) {
    stop()
    return
  }
  raf = requestAnimationFrame(tick)
}

function buildAudio(T: ToneModule, midi: Midi) {
  const melodic = new T.PolySynth(T.Synth, {
    oscillator: { type: 'triangle' },
    envelope: { attack: 0.01, decay: 0.15, sustain: 0.35, release: 0.4 },
  }).toDestination()
  melodic.maxPolyphony = 64
  melodic.volume.value = -10
  const kick = new T.MembraneSynth({ volume: -6 }).toDestination()
  const noise = new T.NoiseSynth({
    volume: -18,
    envelope: { attack: 0.001, decay: 0.12, sustain: 0 },
  }).toDestination()

  const parts: { dispose(): void }[] = []
  for (const track of midi.tracks) {
    const percussion = track.channel === 9 || track.instrument.percussion
    const events = track.notes.map((n) => ({
      time: n.time,
      midi: n.midi,
      name: n.name,
      duration: Math.max(0.05, n.duration),
      velocity: n.velocity,
    }))
    if (events.length === 0) continue
    const part = new T.Part((time, ev) => {
      if (!percussion) {
        melodic.triggerAttackRelease(ev.name, ev.duration, time, ev.velocity)
      } else if (ev.midi === 35 || ev.midi === 36) {
        kick.triggerAttackRelease('C1', 0.2, time, ev.velocity)
      } else {
        // Snare, hats, cymbals, toms: a short noise burst is enough.
        noise.triggerAttackRelease(0.08, time, ev.velocity)
      }
    }, events)
    part.start(0)
    parts.push(part)
  }

  return () => {
    parts.forEach((p) => p.dispose())
    melodic.dispose()
    kick.dispose()
    noise.dispose()
  }
}

async function prepareAudio(): Promise<boolean> {
  const url = midiUrl.value
  if (!url) {
    playError.value = 'No hay MIDI para esta selección.'
    return false
  }
  preparing.value = true
  playError.value = null
  try {
    Tone ??= await import('tone')
    await Tone.start()
    const midi = await loadMidi(url)
    const transport = Tone.getTransport()
    transport.stop()
    transport.cancel()
    disposeAudio?.()
    disposeAudio = buildAudio(Tone, midi)
    midiDuration.value = midi.duration
    transport.seconds = 0
    return true
  } catch (err) {
    playError.value =
      err instanceof Error
        ? err.message
        : 'No se pudo preparar la reproducción.'
    return false
  } finally {
    preparing.value = false
  }
}

let preparedFor: string | null = null

async function play() {
  if (preparing.value) return
  if (preparedFor !== midiUrl.value) {
    if (!(await prepareAudio())) return
    preparedFor = midiUrl.value ?? null
  }
  if (!Tone) return
  await Tone.start()
  Tone.getTransport().start()
  playing.value = true
  cancelAnimationFrame(raf)
  raf = requestAnimationFrame(tick)
}

function pause() {
  Tone?.getTransport().pause()
  playing.value = false
  cancelAnimationFrame(raf)
}

function stop() {
  if (Tone) {
    const transport = Tone.getTransport()
    transport.stop()
    transport.seconds = 0
  }
  playing.value = false
  position.value = 0
  cancelAnimationFrame(raf)
  if (osmd && stepTimes.length) {
    osmd.cursor.reset()
    cursorIndex = 0
  }
}

function teardownAudio() {
  stop()
  disposeAudio?.()
  disposeAudio = null
  preparedFor = null
}

function setZoom(delta: number) {
  zoom.value =
    Math.round(Math.min(2, Math.max(0.5, zoom.value + delta)) * 10) / 10
  if (osmd && !rendering.value) {
    osmd.zoom = zoom.value
    osmd.render()
    // render() keeps the cursor but its position must be refreshed.
    const idx = cursorIndex
    osmd.cursor.reset()
    cursorIndex = 0
    moveCursorTo(idx)
    osmd.cursor.show()
  }
}

watch(selection, () => {
  teardownAudio()
  void renderScore()
})

onMounted(() => void renderScore())
onBeforeUnmount(() => {
  renderToken++
  cancelAnimationFrame(raf)
  teardownAudio()
  osmd?.clear()
  osmd = null
})
</script>

<template>
  <section class="card space-y-4" aria-labelledby="score-title">
    <div class="flex flex-wrap items-center gap-3">
      <h2 id="score-title" class="mr-auto text-xl font-semibold">Partitura</h2>
      <label class="flex items-center gap-2 text-sm">
        <span>Ver</span>
        <select v-model="selection" class="input">
          <option :value="FULL">Partitura completa</option>
          <option
            v-for="p in result.parts"
            :key="p.instrument"
            :value="p.instrument"
          >
            Parte: {{ p.name }}
          </option>
        </select>
      </label>
    </div>

    <div
      class="flex flex-wrap items-center gap-2"
      role="group"
      aria-label="Reproducción de la partitura"
    >
      <button
        type="button"
        class="btn-primary"
        :disabled="rendering || preparing || !midiUrl"
        :aria-pressed="playing"
        @click="playing ? pause() : play()"
      >
        {{
          preparing
            ? 'Preparando…'
            : playing
              ? '❚❚ Pausar'
              : '▶ Reproducir MIDI'
        }}
      </button>
      <button
        type="button"
        class="btn-ghost"
        :disabled="rendering"
        aria-label="Detener y volver al inicio"
        @click="stop"
      >
        ■
      </button>
      <span class="font-mono text-sm tabular-nums" aria-live="off">
        {{ formatTime(position)
        }}<template v-if="midiDuration">
          / {{ formatTime(midiDuration) }}</template
        >
      </span>
      <span class="ml-auto flex items-center gap-1">
        <button
          type="button"
          class="btn-ghost h-8 w-8 !p-0"
          aria-label="Alejar"
          :disabled="rendering"
          @click="setZoom(-0.1)"
        >
          −
        </button>
        <span class="w-12 text-center font-mono text-xs"
          >{{ Math.round(zoom * 100) }}%</span
        >
        <button
          type="button"
          class="btn-ghost h-8 w-8 !p-0"
          aria-label="Acercar"
          :disabled="rendering"
          @click="setZoom(0.1)"
        >
          +
        </button>
      </span>
    </div>
    <p
      v-if="playError"
      role="alert"
      class="text-sm text-amber dark:text-amber-dk"
    >
      {{ playError }}
    </p>

    <div
      class="relative overflow-x-auto rounded-xl bg-white text-black ring-1 ring-line dark:ring-night-line"
    >
      <div
        v-if="rendering"
        class="absolute inset-0 z-10 flex items-center justify-center bg-white/70 text-sm text-neutral-600"
        role="status"
      >
        Renderizando partitura…
      </div>
      <p v-if="renderError" role="alert" class="p-6 text-sm text-amber">
        {{ renderError }}
      </p>
      <div
        ref="container"
        class="min-h-48 p-2"
        :aria-busy="rendering"
        aria-label="Partitura renderizada"
        role="img"
      />
    </div>
    <p class="muted text-xs">
      El cursor se sincroniza con la reproducción usando el tempo detectado ({{
        Math.round(tempo)
      }}
      BPM, pulso de negra). Con cambios de tempo o compases irregulares puede
      desfasarse un poco. La reproducción usa un sintetizador simple, no los
      timbres reales.
    </p>
  </section>
</template>
