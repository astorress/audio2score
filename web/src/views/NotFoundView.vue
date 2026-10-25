<script setup lang="ts">
import { RouterLink } from 'vue-router'
</script>

<template>
  <section class="py-20 text-center">
    <p class="label">404</p>
    <h1 class="mt-2 text-4xl font-semibold">Esta página no existe</h1>
    <p class="muted mt-3">Puede que el enlace esté mal escrito.</p>
    <RouterLink to="/" class="btn-primary mt-6">Volver al inicio</RouterLink>
  </section>
</template>
