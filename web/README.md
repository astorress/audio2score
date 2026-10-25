# audio2score · web

SPA en **Vue 3 + TypeScript** para audio2score: subir y recortar un fragmento
de audio (máx. 90 s), seguir el progreso del trabajo y ver el resultado
(mezclador de stems, partitura con OSMD y reproducción MIDI, piano-roll y
descargas). Implementa el contrato de [`docs/api.md`](../docs/api.md).

Stack: Vite · Vue 3 (`<script setup>`) · TypeScript estricto · Pinia · Vue
Router · Tailwind CSS 4 · OpenSheetMusicDisplay · Tone.js + `@tonejs/midi` ·
WaveSurfer.js 7 (plugin Regions) · Vitest · ESLint · Prettier.

## Configuración

Copia `.env.example` a `.env` y ajusta:

| Variable       | Por defecto             | Descripción                                          |
| -------------- | ----------------------- | ---------------------------------------------------- |
| `VITE_API_URL` | `http://localhost:8000` | URL base de la API (API Gateway o la API local)      |
| `VITE_MOCK`    | —                       | `1` monta una API simulada en `/__mock` (solo `dev`) |

> La API y el bucket S3 deben permitir CORS desde el origen de la SPA: el
> navegador hace `fetch` de los stems, MIDI y MusicXML para reproducirlos y
> renderizarlos.

## Comandos

No hace falta Node instalado: todo corre con Docker.

```bash
# alias de conveniencia
alias dnpm='docker run --rm -it -v "$PWD":/web -w /web -p 5173:5173 node:24-bookworm-slim npm'

dnpm install          # dependencias (genera package-lock.json)
dnpm run dev          # servidor de desarrollo en http://localhost:5173
dnpm run dev:mock     # igual, contra la API simulada (web/mock/)
dnpm run build        # vue-tsc --noEmit && vite build → dist/
dnpm test             # pruebas unitarias (Vitest)
dnpm run lint         # ESLint (flat config)
dnpm run format:check # Prettier
```

Con Node 24 local, los mismos comandos funcionan con `npm` directamente.

## Estructura

```text
src/
├── api/          # cliente fetch tipado + tipos espejo de docs/api.md
├── stores/       # Pinia: catálogo de instrumentos y job (polling cada 3 s)
├── views/        # Upload, Job (progreso/resultado), Cómo funciona
├── components/   # WaveformCropper, InstrumentPicker, JobProgress, StemMixer,
│                 # ScoreViewer, PianoRoll, Downloads
└── lib/          # wav.ts (codificador WAV 16 bits), midi.ts, audio.ts, labels.ts
tests/            # Vitest: WAV, orden del FormData de subida, helpers MIDI
mock/             # API simulada solo para desarrollo (VITE_MOCK=1)
```

## Notas

- El recorte se hace en el navegador: el audio se decodifica (remuestreado a
  44,1 kHz), se recorta la región y se codifica a WAV PCM de 16 bits. 90 s en
  estéreo ≈ 15,9 MB.
- La subida es un _presigned POST_ de S3: todos los `fields` y el campo `file`
  al final.
- El cursor de la partitura se sincroniza con el MIDI convirtiendo el
  `currentTimeStamp` de OSMD (en redondas) a segundos con el tempo del
  resultado (`segundos = valor × 4 × 60 / tempo`). Es una aproximación: no
  considera cambios de tempo.
