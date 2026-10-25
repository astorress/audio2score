<script setup lang="ts">
import { computed } from 'vue'
import type { Catalog, Instrument, ModeId } from '@/api/types'

const props = defineProps<{
  catalog: Catalog
  mode: ModeId
}>()

const selected = defineModel<string[]>({ required: true })

defineEmits<{ reset: [] }>()

interface Group {
  id: string
  name: string
  instruments: Instrument[]
}

function allowed(inst: Instrument): boolean {
  return props.mode !== 'rock' || inst.modes.includes('rock')
}

const groups = computed<Group[]>(() => {
  const byFamily = new Map<string, Instrument[]>()
  for (const inst of props.catalog.instruments) {
    const list = byFamily.get(inst.family) ?? []
    list.push(inst)
    byFamily.set(inst.family, list)
  }
  const known = props.catalog.families
    .filter((f) => byFamily.has(f.id))
    .map((f) => ({ id: f.id, name: f.name, instruments: byFamily.get(f.id)! }))
  const unknown = [...byFamily.keys()]
    .filter((id) => !props.catalog.families.some((f) => f.id === id))
    .map((id) => ({ id, name: id, instruments: byFamily.get(id)! }))
  return [...known, ...unknown]
})

function toggle(id: string, checked: boolean) {
  const set = new Set(selected.value)
  if (checked) set.add(id)
  else set.delete(id)
  // Keep the catalog order for a stable request body.
  selected.value = props.catalog.instruments
    .map((i) => i.id)
    .filter((i) => set.has(i))
}

function toggleFamily(group: Group, checked: boolean) {
  const set = new Set(selected.value)
  for (const inst of group.instruments) {
    if (!allowed(inst)) continue
    if (checked) set.add(inst.id)
    else set.delete(inst.id)
  }
  selected.value = props.catalog.instruments
    .map((i) => i.id)
    .filter((i) => set.has(i))
}

function familyState(group: Group): 'all' | 'some' | 'none' {
  const enabled = group.instruments.filter(allowed)
  const n = enabled.filter((i) => selected.value.includes(i.id)).length
  if (n === 0) return 'none'
  return n === enabled.length ? 'all' : 'some'
}

function clefLabel(clef: string): string {
  return (
    {
      treble: 'Sol',
      bass: 'Fa',
      alto: 'Do 3ª',
      tenor: 'Do 4ª',
      percussion: 'Perc.',
    }[clef] ?? clef
  )
}
</script>

<template>
  <div class="space-y-4">
    <div class="flex flex-wrap items-center gap-2">
      <p class="muted mr-auto text-sm" aria-live="polite">
        <template v-if="selected.length === 0 && mode === 'auto'">
          Sin selección: se usarán los instrumentos predeterminados de la ruta
          que elija el modo automático.
        </template>
        <template v-else>
          {{ selected.length }} instrumento{{
            selected.length === 1 ? '' : 's'
          }}
          seleccionado{{ selected.length === 1 ? '' : 's' }}
        </template>
      </p>
      <button type="button" class="btn-ghost" @click="$emit('reset')">
        Predeterminados
      </button>
      <button type="button" class="btn-ghost" @click="selected = []">
        Ninguno
      </button>
    </div>

    <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      <fieldset
        v-for="group in groups"
        :key="group.id"
        class="rounded-xl border border-line p-3 dark:border-night-line"
      >
        <legend class="px-1">
          <label class="flex items-center gap-2 text-sm font-semibold">
            <input
              type="checkbox"
              :checked="familyState(group) === 'all'"
              :indeterminate="familyState(group) === 'some'"
              :disabled="!group.instruments.some(allowed)"
              @change="
                toggleFamily(group, ($event.target as HTMLInputElement).checked)
              "
            />
            {{ group.name }}
          </label>
        </legend>
        <ul class="mt-1 space-y-1">
          <li v-for="inst in group.instruments" :key="inst.id">
            <label
              class="flex items-center gap-2 rounded-md px-1 py-0.5 text-sm"
              :class="
                allowed(inst)
                  ? 'cursor-pointer hover:bg-paper-2 dark:hover:bg-night-2'
                  : 'cursor-not-allowed opacity-45'
              "
              :title="
                allowed(inst)
                  ? `Rango ${inst.range[0]}–${inst.range[1]}`
                  : 'No disponible en modo rock (no hay stem para este instrumento)'
              "
            >
              <input
                type="checkbox"
                :value="inst.id"
                :checked="selected.includes(inst.id)"
                :disabled="!allowed(inst)"
                @change="
                  toggle(inst.id, ($event.target as HTMLInputElement).checked)
                "
              />
              <span class="mr-auto">{{ inst.name }}</span>
              <span class="muted font-mono text-[0.7rem]">
                {{ clefLabel(inst.clef) }}
                <template v-if="inst.transposition">
                  · {{ inst.transposition }}
                </template>
              </span>
            </label>
          </li>
        </ul>
      </fieldset>
    </div>
  </div>
</template>
