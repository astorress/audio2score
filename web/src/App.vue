<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'

const links = [
  { to: '/', label: 'Transcribir' },
  { to: '/como-funciona', label: 'Cómo funciona' },
]
</script>

<template>
  <a
    href="#main"
    class="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded focus:bg-card focus:px-3 focus:py-2"
  >
    Saltar al contenido
  </a>
  <header
    class="sticky top-0 z-20 border-b border-line/70 bg-paper/80 backdrop-blur-md dark:border-night-line/70 dark:bg-night/80"
  >
    <div class="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
      <RouterLink
        to="/"
        class="mr-auto flex items-center gap-2 font-serif text-xl font-bold"
      >
        <svg
          aria-hidden="true"
          viewBox="0 0 64 64"
          class="h-7 w-7 rounded-lg bg-accent p-1 text-white dark:bg-accent-dk dark:text-night"
        >
          <path
            d="M40 12v28.5a8 8 0 1 1-4-6.9V20l-12 3v21.5a8 8 0 1 1-4-6.9V16z"
            fill="currentColor"
          />
        </svg>
        <span
          >audio<span class="text-teal dark:text-teal-dk">2</span>score</span
        >
      </RouterLink>
      <nav aria-label="Principal" class="flex gap-1 text-sm">
        <RouterLink
          v-for="link in links"
          :key="link.to"
          :to="link.to"
          class="rounded-full px-2.5 py-1.5 whitespace-nowrap text-muted sm:px-3 hover:bg-paper-2 hover:text-ink dark:text-fog dark:hover:bg-night-2 dark:hover:text-snow"
          exact-active-class="bg-paper-2 text-ink dark:bg-night-2 dark:text-snow"
        >
          {{ link.label }}
        </RouterLink>
      </nav>
    </div>
  </header>

  <main id="main" class="mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
    <RouterView />
  </main>

  <footer
    class="mx-auto max-w-6xl px-4 pb-10 text-sm text-muted sm:px-6 dark:text-fog"
  >
    <p>
      Proyecto personal de Sebastián Torres. Los audios y resultados se borran a
      las 24 h; no hay galería pública. Las partituras son aproximadas.
    </p>
  </footer>
</template>
