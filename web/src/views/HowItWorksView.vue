<script setup lang="ts">
import { RouterLink } from 'vue-router'

interface FlowStep {
  title: string
  detail: string
}

const rockFlow: FlowStep[] = [
  { title: 'Mezcla', detail: 'tu fragmento (≤ 90 s)' },
  {
    title: 'Demucs',
    detail: 'htdemucs_6s → voz, batería, bajo, guitarra, piano, otros',
  },
  {
    title: 'Transcripción',
    detail: 'Basic Pitch por stem · modelo de batería',
  },
  { title: 'music21', detail: 'cuantización, tonalidad, claves → MusicXML' },
]

const orchestraFlow: FlowStep[] = [
  { title: 'Mezcla', detail: 'tu fragmento (≤ 90 s)' },
  {
    title: 'AMT multi-instrumento',
    detail: 'modelo extremo a extremo condicionado por instrumentos',
  },
  { title: 'MIDI multipista', detail: 'agrupado por familias' },
  { title: 'music21', detail: 'transposición, claves, partes → MusicXML' },
]

const engraving: FlowStep[] = [
  {
    title: 'Limpieza de notas',
    detail:
      'Se eliminan notas de menos de 50 ms o de velocidad muy baja y se fusionan repeticiones muy cercanas: el ruido típico de la transcripción.',
  },
  {
    title: 'Filtro por rango',
    detail:
      'Cada instrumento tiene un rango real (trombón tenor ≈ Mi2–Fa5, violín desde Sol3). Lo que cae fuera se descarta o se reasigna.',
  },
  {
    title: 'Beat tracking',
    detail:
      'Se estima el tempo y los tiempos fuertes para construir la grilla métrica (4/4 por defecto, 3/4 si la autocorrelación lo sugiere).',
  },
  {
    title: 'Cuantización',
    detail:
      'Cada ataque se lleva a la subdivisión más cercana de la grilla elegida (1/8, 1/16, 1/32), penalizando ritmos innecesariamente complejos.',
  },
  {
    title: 'Tonalidad',
    detail:
      'Algoritmo de Krumhansl-Schmuckler: se correlaciona el histograma de duraciones por clase de altura con los perfiles de cada tonalidad mayor y menor.',
  },
  {
    title: 'Deletreo y claves',
    detail:
      'Do♯ o Re♭ según la tonalidad; clave de Sol, Fa o Do según el instrumento (Do en 3ª para la viola).',
  },
  {
    title: 'Transposición',
    detail:
      'Los instrumentos transpositores se escriben en su altura escrita: trompeta y clarinete en Si♭ una 2ª mayor arriba, corno en Fa una 5ª justa arriba, contrabajo y guitarra una 8ª arriba.',
  },
  {
    title: 'Exportación',
    detail:
      'MusicXML de la partitura general y de cada parte, MIDI por instrumento y, si se pidió, PDF con MuseScore.',
  },
]

const aws: FlowStep[] = [
  {
    title: 'S3 (subida firmada)',
    detail:
      'El navegador crea el trabajo (POST /jobs) y sube el WAV directo a S3 con un presigned POST que limita el tamaño.',
  },
  {
    title: 'Lambda',
    detail:
      'El evento de S3 dispara una Lambda que encola el trabajo. Lambda no tiene GPU, así que no procesa el audio.',
  },
  {
    title: 'SageMaker Async (GPU)',
    detail:
      'Un endpoint asíncrono con GPU y escalado a cero hace separación, transcripción y engraving. Si estaba apagado, arranca en frío (varios minutos).',
  },
  {
    title: 'SNS',
    detail: 'Al terminar (o fallar), SageMaker publica una notificación.',
  },
  {
    title: 'DynamoDB',
    detail:
      'Otra Lambda actualiza el estado del trabajo y los tiempos por etapa.',
  },
  {
    title: 'Polling',
    detail:
      'Esta página consulta GET /jobs/{id} cada 3 s y, al terminar, descarga los resultados con URLs firmadas.',
  },
]
</script>

<template>
  <article class="prose-a2s mx-auto max-w-3xl">
    <p class="label">Cómo funciona</p>
    <h1 class="mt-2 text-4xl font-semibold sm:text-5xl">
      Del audio a la partitura, paso a paso
    </h1>
    <p class="muted text-lg">
      audio2score es un "sous-chef" que prueba un plato y te escribe una receta
      aproximada: no es la receta original del chef, pero te dice qué
      ingredientes hay, en qué cantidad y en qué orden. Suficiente para que un
      músico lo reproduzca razonablemente bien.
    </p>

    <nav aria-label="En esta página" class="card my-8 !p-4 text-sm">
      <p class="label mb-2">En esta página</p>
      <ol class="!my-0 columns-1 sm:columns-2">
        <li><a href="#rutas">Las dos rutas</a></li>
        <li><a href="#orquesta">Por qué no se separa la orquesta</a></li>
        <li><a href="#engraving">Del MIDI a la partitura</a></li>
        <li><a href="#arquitectura">Arquitectura en AWS</a></li>
        <li><a href="#limites">Límites y privacidad</a></li>
        <li><a href="#metricas">Métricas</a></li>
      </ol>
    </nav>

    <h2 id="rutas">Las dos rutas</h2>
    <p>
      El problema tiene tres partes: <strong>separar fuentes</strong> (aislar
      cada instrumento de la mezcla), <strong>transcribir</strong> (convertir
      audio en notas con altura, ataque, duración e instrumento) y
      <strong>escribir la partitura</strong> (pasar de segundos a compases y
      figuras). Según el género se combinan de forma distinta.
    </p>

    <h3>Rock / banda: en cascada</h3>
    <ol class="!list-none !pl-0 grid gap-2 sm:grid-cols-4">
      <li v-for="(s, i) in rockFlow" :key="s.title" class="flow-step">
        <span class="font-mono text-xs text-accent dark:text-accent-dk">{{
          i + 1
        }}</span>
        <strong class="block">{{ s.title }}</strong>
        <span class="muted text-sm">{{ s.detail }}</span>
      </li>
    </ol>
    <p>
      <strong>Demucs</strong> (HTDemucs de 6 stems) separa voz, batería, bajo,
      guitarra y piano. Cada stem melódico se transcribe con
      <strong>Basic Pitch</strong> de Spotify, que no necesita saber qué
      instrumento es: la etiqueta la da el stem. La batería va por un
      transcriptor de percusión que asigna bombo, caja, hi-hat y platillos a
      General MIDI. Al final, <strong>music21</strong> arma la partitura.
    </p>

    <h3>Orquesta: extremo a extremo</h3>
    <ol class="!list-none !pl-0 grid gap-2 sm:grid-cols-4">
      <li v-for="(s, i) in orchestraFlow" :key="s.title" class="flow-step">
        <span class="font-mono text-xs text-teal dark:text-teal-dk">{{
          i + 1
        }}</span>
        <strong class="block">{{ s.title }}</strong>
        <span class="muted text-sm">{{ s.detail }}</span>
      </li>
    </ol>
    <p>
      Un modelo de <strong>transcripción multi-instrumento</strong> lee la
      mezcla completa y produce notas etiquetadas con el instrumento, guiado por
      la lista de instrumentos que eliges. Luego se agrupan por familias
      (maderas, metales, percusión, cuerdas) y se ordenan como en una partitura
      orquestal.
    </p>
    <p>
      En modo <em>automático</em>, un clasificador ligero de instrumentación
      decide la ruta; siempre puedes forzarla.
    </p>

    <h2 id="orquesta">Por qué no se separa la orquesta</h2>
    <p>
      No hay modelos de separación orquestal confiables: veinte violines, dos
      oboes y un corno se solapan en frecuencia y en tiempo de formas que los
      separadores entrenados con música pop no saben deshacer. Separar mal
      <strong>inyecta artefactos</strong> que el transcriptor interpreta como
      notas falsas.
    </p>
    <blockquote>
      Es como fotocopiar una fotocopia: cada etapa con pérdidas degrada la
      entrada de la siguiente. Por eso, en orquesta, es mejor transcribir
      directo desde la mezcla original.
    </blockquote>

    <h2 id="engraving">Del MIDI a la partitura (engraving)</h2>
    <p>
      La transcripción entrega algo parecido a un <em>log</em> de eventos con
      marcas de tiempo en milisegundos. El engraving convierte ese log en un
      <strong>horario escolar</strong>: bloques fijos, nombres legibles y todo
      acomodado en una cuadrícula que un músico entienda de un vistazo.
    </p>
    <ol class="!list-none !pl-0 space-y-3">
      <li v-for="(s, i) in engraving" :key="s.title" class="flex gap-3">
        <span
          class="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-paper-2 font-mono text-xs dark:bg-night-2"
          >{{ i + 1 }}</span
        >
        <div>
          <strong>{{ s.title }}.</strong>
          <span class="muted"> {{ s.detail }}</span>
        </div>
      </li>
    </ol>

    <h2 id="arquitectura">Arquitectura en AWS</h2>
    <p>
      La inferencia necesita GPU, y una GPU encendida todo el día cuesta. Por
      eso el worker <strong>escala a cero</strong>: solo se paga mientras
      procesa, a cambio de un arranque en frío de varios minutos cuando estaba
      apagado.
    </p>
    <ol class="!list-none !pl-0 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
      <li v-for="(s, i) in aws" :key="s.title" class="flow-step">
        <span class="font-mono text-xs text-amber dark:text-amber-dk">{{
          i + 1
        }}</span>
        <strong class="block">{{ s.title }}</strong>
        <span class="muted text-sm">{{ s.detail }}</span>
      </li>
    </ol>
    <p>
      El frontend (esta app en Vue) se sirve desde S3 + CloudFront. En el
      navegador se recorta el fragmento y se codifica a WAV antes de subirlo, se
      renderiza la partitura con OpenSheetMusicDisplay y se reproduce el MIDI
      con Tone.js.
    </p>

    <h2 id="limites">Límites y privacidad</h2>
    <ul>
      <li>Fragmentos de máximo <strong>90 segundos</strong>.</li>
      <li>
        Audio y resultados se <strong>borran a las 24 horas</strong>; los
        enlaces de descarga duran 1 hora.
      </li>
      <li>
        <strong>No hay galería pública</strong>: solo quien tiene el enlace del
        trabajo ve el resultado.
      </li>
      <li>Cuota diaria de trabajos por IP, para contener el costo de GPU.</li>
      <li>
        Las partituras son <strong>aproximadas</strong>: no incluyen dinámicas,
        articulaciones ni letras, y el ritmo puede simplificarse (sobre todo con
        rubato).
      </li>
    </ul>

    <h2 id="metricas">Métricas</h2>
    <div class="card">
      <p class="font-medium">Próximamente.</p>
      <p class="muted mt-1 text-sm">
        Los resultados se publicarán a partir de la evaluación de la Fase 3: SDR
        para la separación (Slakh2100), F1 de onset y F1 multi-instrumento para
        la transcripción (Slakh2100, URMP) y tasa de compases con duración
        correcta para el engraving, además de un ablation sobre si separar antes
        de transcribir mejora el resultado en rock y en orquesta.
      </p>
    </div>

    <p class="mt-10">
      <RouterLink to="/" class="btn-primary !no-underline"
        >Probar con un audio</RouterLink
      >
    </p>
  </article>
</template>

<style scoped>
.flow-step {
  border: 1px solid var(--color-line);
  border-radius: 0.75rem;
  padding: 0.75rem;
  background: var(--color-card);
}
@media (prefers-color-scheme: dark) {
  .flow-step {
    border-color: var(--color-night-line);
    background: var(--color-night-card);
  }
}
</style>
