<script setup lang="ts">
import type { JobResult } from '@/api/types'

defineProps<{ result: JobResult }>()
</script>

<template>
  <section class="card space-y-5" aria-labelledby="downloads-title">
    <div>
      <h2 id="downloads-title" class="text-xl font-semibold">Descargas</h2>
      <p class="muted mt-1 text-sm">
        Los enlaces son temporales (1 h) y los archivos se borran a las 24 h. Si
        un enlace expiró, recarga la página.
      </p>
    </div>

    <div class="grid gap-5 md:grid-cols-2">
      <div>
        <h3 class="label mb-2">Partitura</h3>
        <ul class="space-y-1.5 text-sm">
          <li>
            <a class="dl" :href="result.score.musicxml" download
              >MusicXML · partitura completa</a
            >
          </li>
          <li v-if="result.score.pdf">
            <a
              class="dl"
              :href="result.score.pdf"
              download
              target="_blank"
              rel="noopener"
              >PDF · partitura completa</a
            >
          </li>
          <li v-else class="muted">PDF no disponible para este trabajo.</li>
          <li v-for="p in result.parts" :key="p.instrument">
            <a class="dl" :href="p.url" download
              >MusicXML · parte de {{ p.name }}</a
            >
          </li>
        </ul>
      </div>

      <div>
        <h3 class="label mb-2">MIDI</h3>
        <ul class="space-y-1.5 text-sm">
          <li>
            <a class="dl" :href="result.midiFull" download
              >MIDI · todas las pistas</a
            >
          </li>
          <li v-for="m in result.midi" :key="m.instrument">
            <a class="dl" :href="m.url" download>MIDI · {{ m.name }}</a>
            <span class="muted font-mono text-xs"> ({{ m.notes }} notas)</span>
          </li>
        </ul>
      </div>

      <div v-if="result.stems.length" class="md:col-span-2">
        <h3 class="label mb-2">Stems (audio separado)</h3>
        <ul class="flex flex-wrap gap-2 text-sm">
          <li v-for="s in result.stems" :key="s.name">
            <a class="dl chip !font-sans !text-sm" :href="s.url" download>{{
              s.label
            }}</a>
          </li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.dl {
  color: var(--color-accent);
  text-underline-offset: 3px;
}
.dl:hover {
  text-decoration: underline;
}
@media (prefers-color-scheme: dark) {
  .dl {
    color: var(--color-accent-dk);
  }
}
</style>
