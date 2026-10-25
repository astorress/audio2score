<script setup lang="ts">
import { computed, onMounted, ref, shallowRef, watch } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import { api, describeApiError } from '@/api/client'
import type { ModeId, Quantization } from '@/api/types'
import { useCatalogStore } from '@/stores/catalog'
import { decodeAudioFile } from '@/lib/audio'
import { cropToWavBlob, wavByteLength } from '@/lib/wav'
import { formatBytes, formatTime } from '@/lib/midi'
import WaveformCropper, {
  type CropRegion,
} from '@/components/WaveformCropper.vue'
import InstrumentPicker from '@/components/InstrumentPicker.vue'

/** Hard cap on the original file to avoid decoding huge files in memory. */
const MAX_SOURCE_BYTES = 300 * 1024 * 1024

const router = useRouter()
const catalogStore = useCatalogStore()
const catalog = computed(() => catalogStore.catalog)

const file = shallowRef<File | null>(null)
const audio = shallowRef<AudioBuffer | null>(null)
const decoding = ref(false)
const dragOver = ref(false)
const fileInput = ref<HTMLInputElement | null>(null)

const region = ref<CropRegion>({ start: 0, end: 0 })
const mode = ref<ModeId>('auto')
const instruments = ref<string[]>([])
const quantization = ref<Quantization>('1/16')
const allowTriplets = ref(false)
const exportPdf = ref(true)

type Step = 'idle' | 'encoding' | 'creating' | 'uploading'
const step = ref<Step>('idle')
const error = ref<string | null>(null)

const maxDurationSec = computed(
  () => catalog.value?.limits.maxDurationSec ?? 90
)
const maxUploadBytes = computed(
  () => catalog.value?.limits.maxUploadBytes ?? 25 * 1024 * 1024
)

const regionDuration = computed(() => region.value.end - region.value.start)
const estimatedBytes = computed(() => {
  if (!audio.value) return 0
  const frames = Math.round(regionDuration.value * audio.value.sampleRate)
  return wavByteLength(frames, Math.min(2, audio.value.numberOfChannels))
})
const tooBig = computed(() => estimatedBytes.value > maxUploadBytes.value)
const tooLong = computed(
  () => regionDuration.value > maxDurationSec.value + 0.05
)
const busy = computed(() => step.value !== 'idle')
const canSubmit = computed(
  () =>
    !!audio.value &&
    !!catalog.value &&
    !busy.value &&
    regionDuration.value > 0 &&
    !tooBig.value &&
    !tooLong.value
)

const stepLabel: Record<Step, string> = {
  idle: '',
  encoding: 'Recortando y codificando a WAV…',
  creating: 'Creando el trabajo…',
  uploading: 'Subiendo el audio…',
}

function defaultsFor(m: ModeId): string[] {
  if (!catalog.value || m === 'auto') return []
  return [...catalog.value.defaults[m]]
}

function resetInstruments() {
  instruments.value = defaultsFor(mode.value)
}

watch(mode, (m) => {
  instruments.value = defaultsFor(m)
})

watch(catalog, (c) => {
  if (!c) return
  if (!c.quantizations.includes(quantization.value) && c.quantizations[0])
    quantization.value = c.quantizations.includes('1/16')
      ? '1/16'
      : c.quantizations[0]
  resetInstruments()
})

onMounted(() => {
  void catalogStore.load().then(() => {
    if (catalog.value) resetInstruments()
  })
})

async function setFile(f: File | undefined | null) {
  error.value = null
  if (!f) return
  if (f.size > MAX_SOURCE_BYTES) {
    error.value = `El archivo pesa ${formatBytes(f.size)}; el máximo para procesarlo en el navegador es ${formatBytes(MAX_SOURCE_BYTES)}.`
    return
  }
  decoding.value = true
  audio.value = null
  file.value = f
  try {
    audio.value = await decodeAudioFile(f)
  } catch (err) {
    file.value = null
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    decoding.value = false
  }
}

function onPick(e: Event) {
  const input = e.target as HTMLInputElement
  void setFile(input.files?.[0])
  input.value = ''
}

function onDrop(e: DragEvent) {
  dragOver.value = false
  void setFile(e.dataTransfer?.files?.[0])
}

function wavName(original: string): string {
  const base =
    original
      .replace(/\.[^.]+$/, '')
      .normalize('NFD')
      .replace(/[̀-ͯ]/g, '')
      .replace(/[^a-zA-Z0-9_-]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 60) || 'fragmento'
  return `${base}.wav`
}

async function submit() {
  if (!canSubmit.value || !audio.value || !file.value) return
  error.value = null
  try {
    step.value = 'encoding'
    // Let the UI paint the status before the synchronous encode.
    await new Promise((r) => setTimeout(r, 30))
    const blob = cropToWavBlob(
      audio.value,
      region.value.start,
      region.value.end
    )
    if (blob.size > maxUploadBytes.value) {
      throw new Error(
        `El WAV recortado pesa ${formatBytes(blob.size)} y el máximo es ${formatBytes(maxUploadBytes.value)}. Acorta la región.`
      )
    }
    const fileName = wavName(file.value.name)

    step.value = 'creating'
    const created = await api.createJob({
      mode: mode.value,
      ...(instruments.value.length ? { instruments: instruments.value } : {}),
      options: {
        quantization: quantization.value,
        allowTriplets: allowTriplets.value,
        exportPdf: exportPdf.value,
      },
      fileName,
      contentType: 'audio/wav',
      sizeBytes: blob.size,
      durationSec: Math.round(regionDuration.value * 1000) / 1000,
    })

    step.value = 'uploading'
    await api.uploadAudio(created.upload, blob, fileName)

    await router.push({ name: 'job', params: { jobId: created.jobId } })
  } catch (err) {
    error.value = describeApiError(err)
  } finally {
    step.value = 'idle'
  }
}
</script>

<template>
  <div class="space-y-8">
    <section class="max-w-3xl">
      <p class="label">Audio → stems → MIDI → partitura</p>
      <h1 class="mt-2 text-4xl leading-tight font-semibold sm:text-5xl">
        Convierte un fragmento de audio en
        <em class="text-accent dark:text-accent-dk">partituras</em> por
        instrumento
      </h1>
      <p class="muted mt-4 text-lg">
        Sube hasta {{ maxDurationSec }} s de rock o música orquestal. Separamos
        las fuentes (en rock), transcribimos cada instrumento a MIDI y generamos
        MusicXML y PDF.
        <RouterLink
          to="/como-funciona"
          class="text-accent underline-offset-2 hover:underline dark:text-accent-dk"
        >
          ¿Cómo funciona?
        </RouterLink>
      </p>
    </section>

    <div
      v-if="catalogStore.error"
      role="alert"
      class="card border-amber/50 text-amber dark:border-amber-dk/50 dark:text-amber-dk"
    >
      <p class="font-medium">No se pudo cargar el catálogo de instrumentos.</p>
      <p class="mt-1 text-sm">{{ catalogStore.error }}</p>
      <button
        type="button"
        class="btn-ghost mt-3"
        @click="catalogStore.load(true)"
      >
        Reintentar
      </button>
    </div>

    <form class="space-y-6" @submit.prevent="submit">
      <!-- 1. File -->
      <section class="card space-y-4" aria-labelledby="step-file">
        <h2 id="step-file" class="text-xl font-semibold">1. Elige el audio</h2>
        <div
          class="flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-4 py-10 text-center transition"
          :class="
            dragOver
              ? 'border-accent bg-accent/5 dark:border-accent-dk dark:bg-accent-dk/10'
              : 'border-line dark:border-night-line'
          "
          @dragenter.prevent="dragOver = true"
          @dragover.prevent="dragOver = true"
          @dragleave.prevent="dragOver = false"
          @drop.prevent="onDrop"
        >
          <svg
            aria-hidden="true"
            viewBox="0 0 24 24"
            class="h-10 w-10 text-muted dark:text-fog"
            fill="none"
            stroke="currentColor"
            stroke-width="1.5"
          >
            <path d="M9 18V5l12-2v13" />
            <circle cx="6" cy="18" r="3" />
            <circle cx="18" cy="16" r="3" />
          </svg>
          <p>
            Arrastra un archivo aquí o
            <button
              type="button"
              class="font-medium text-accent underline underline-offset-2 dark:text-accent-dk"
              @click="fileInput?.click()"
            >
              búscalo en tu equipo
            </button>
          </p>
          <p class="muted text-sm">
            WAV, MP3, FLAC, OGG o M4A. Se decodifica en tu navegador.
          </p>
          <label class="sr-only" for="audio-file">Archivo de audio</label>
          <input
            id="audio-file"
            ref="fileInput"
            type="file"
            accept="audio/*,.wav,.mp3,.flac,.ogg,.m4a"
            class="sr-only"
            @change="onPick"
          />
        </div>
        <p v-if="decoding" class="muted text-sm" role="status">
          Decodificando {{ file?.name }}…
        </p>
        <p v-else-if="file && audio" class="text-sm">
          <span class="font-medium">{{ file.name }}</span>
          <span class="muted font-mono">
            · {{ formatTime(audio.duration) }} ·
            {{ audio.numberOfChannels }} canal{{
              audio.numberOfChannels === 1 ? '' : 'es'
            }}
            · {{ formatBytes(file.size) }}</span
          >
        </p>
      </section>

      <!-- 2. Crop -->
      <section
        v-if="file && audio"
        class="card space-y-4"
        aria-labelledby="step-crop"
      >
        <h2 id="step-crop" class="text-xl font-semibold">
          2. Recorta el fragmento
        </h2>
        <WaveformCropper
          v-model:region="region"
          :file="file"
          :audio="audio"
          :max-duration-sec="maxDurationSec"
        />
        <p class="muted font-mono text-sm">
          WAV a subir: ≈ {{ formatBytes(estimatedBytes) }} (máx.
          {{ formatBytes(maxUploadBytes) }})
        </p>
        <p
          v-if="tooBig"
          role="alert"
          class="text-sm text-amber dark:text-amber-dk"
        >
          El fragmento supera el tamaño máximo de subida. Acorta la región.
        </p>
      </section>

      <!-- 3. Mode + instruments -->
      <section
        v-if="catalog"
        class="card space-y-5"
        aria-labelledby="step-mode"
      >
        <h2 id="step-mode" class="text-xl font-semibold">
          3. Modo e instrumentos
        </h2>
        <fieldset>
          <legend class="label mb-2">Modo</legend>
          <div class="flex flex-wrap gap-2">
            <label
              v-for="m in catalog.modes"
              :key="m.id"
              class="flex cursor-pointer items-center gap-2 rounded-full border px-4 py-2 text-sm transition has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-teal dark:has-[:focus-visible]:ring-teal-dk"
              :class="
                mode === m.id
                  ? 'border-accent bg-accent/10 dark:border-accent-dk dark:bg-accent-dk/15'
                  : 'border-line hover:border-line-hi dark:border-night-line dark:hover:border-night-line-hi'
              "
            >
              <input
                v-model="mode"
                type="radio"
                name="mode"
                :value="m.id"
                class="sr-only"
              />
              {{ m.name }}
            </label>
          </div>
          <p class="muted mt-2 text-sm">
            <template v-if="mode === 'auto'"
              >El sistema decide entre la ruta rock y la orquestal según el
              contenido del audio.</template
            >
            <template v-else-if="mode === 'rock'"
              >Separa stems con Demucs y transcribe cada uno. Solo instrumentos
              con stem propio.</template
            >
            <template v-else
              >Transcripción multi-instrumento directa sobre la mezcla (sin
              separar).</template
            >
          </p>
        </fieldset>

        <div>
          <p class="label mb-2">Instrumentos</p>
          <InstrumentPicker
            v-model="instruments"
            :catalog="catalog"
            :mode="mode"
            @reset="resetInstruments"
          />
        </div>
      </section>

      <!-- 4. Options -->
      <section
        v-if="catalog"
        class="card space-y-4"
        aria-labelledby="step-options"
      >
        <h2 id="step-options" class="text-xl font-semibold">
          4. Opciones de partitura
        </h2>
        <div class="flex flex-wrap items-center gap-6">
          <label class="flex items-center gap-2 text-sm">
            <span>Cuantización</span>
            <select v-model="quantization" class="input font-mono">
              <option v-for="q in catalog.quantizations" :key="q" :value="q">
                {{ q }}
              </option>
            </select>
          </label>
          <label class="flex items-center gap-2 text-sm">
            <input v-model="allowTriplets" type="checkbox" />
            Permitir tresillos
          </label>
          <label class="flex items-center gap-2 text-sm">
            <input v-model="exportPdf" type="checkbox" />
            Exportar PDF
          </label>
        </div>
        <p class="muted text-sm">
          La cuantización es la figura más corta de la grilla rítmica: 1/16 es
          una semicorchea. Una grilla más fina capta más detalle pero produce
          partituras más difíciles de leer.
        </p>
      </section>

      <div class="flex flex-wrap items-center gap-4">
        <button
          type="submit"
          class="btn-primary px-6 py-3 text-base"
          :disabled="!canSubmit"
        >
          {{ busy ? 'Enviando…' : 'Generar partituras' }}
        </button>
        <p v-if="busy" class="muted text-sm" role="status">
          {{ stepLabel[step] }}
        </p>
        <p v-else-if="!audio" class="muted text-sm">
          Primero elige un archivo de audio.
        </p>
      </div>
      <p
        v-if="error"
        role="alert"
        class="rounded-xl border border-amber/40 bg-amber/5 px-4 py-3 text-sm text-amber dark:border-amber-dk/40 dark:bg-amber-dk/10 dark:text-amber-dk"
      >
        {{ error }}
      </p>
    </form>
  </div>
</template>
