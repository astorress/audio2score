# audio2score 🎼

- [audio2score 🎼](#audio2score-)
  - [Resumen](#resumen)
    - [Cómo funciona](#cómo-funciona)
    - [Estructura](#estructura)
    - [Estado por fases](#estado-por-fases)
  - [Configuración](#configuración)
    - [Contenedor de desarrollo](#contenedor-de-desarrollo)
    - [Variables de entorno](#variables-de-entorno)
    - [Desarrollo local (sin AWS)](#desarrollo-local-sin-aws)
    - [Despliegue en AWS](#despliegue-en-aws)
    - [Actualizaciones](#actualizaciones)
    - [Operación](#operación)
    - [Evaluación](#evaluación)
    - [Eliminación](#eliminación)
  - [Guías de contribución](#guías-de-contribución)
  - [Glosario](#glosario)

---

## Resumen

Subes un fragmento de audio (máximo 90 s) y la app devuelve:

1. **Stems** separados para escuchar y mezclar (ruta rock).
2. **MIDI** por instrumento.
3. **Partitura** completa y por instrumento (MusicXML y PDF), visible y reproducible en el navegador.

> Las partituras son **aproximadas**: sirven para tocar y estudiar, no son una edición de calidad editorial.

Plan completo (formulación, modelos, arquitectura, fases y riesgos): [`docs/PLAN.md`](docs/PLAN.md). Contrato HTTP: [`docs/api.md`](docs/api.md). Arquitectura en AWS: [`docs/arquitectura.md`](docs/arquitectura.md) y el diagrama [`docs/architecture.drawio`](docs/architecture.drawio). Detalle de cada etapa: [`docs/pipeline.md`](docs/pipeline.md). Problemas comunes: [`docs/problemas.md`](docs/problemas.md).

### Cómo funciona

```text
ROCK (cascada)
  audio ─► Demucs htdemucs_6s ─┬─► voz / bajo / guitarra / piano ─► Basic Pitch ─┐
                               └─► batería ─► detector de golpes (DSP) ──────────┤
ORQUESTA (end-to-end)                                                            │
  audio ─► AMT multi-instrumento (Basic Pitch + asignación por registro) ────────┤
                                                                                 ▼
  limpieza ─► filtro de rango ─► beat tracking ─► cuantización (Viterbi) ─► tonalidad (Krumhansl-Schmuckler)
           ─► music21: claves, transposiciones, gran pentagrama ─► MusicXML · partes · MIDI · PDF (MuseScore)
```

| Etapa                  | Implementación                                                                                              | Código                          |
| ---------------------- | ----------------------------------------------------------------------------------------------------------- | ------------------------------- |
| Separación             | HTDemucs `htdemucs_6s`                                                                                      | `src/pipeline/separation.py`    |
| Transcripción por stem | Basic Pitch, acotado al rango del instrumento                                                               | `src/pipeline/transcription.py` |
| Batería                | Onsets + energía por bandas → bombo, caja, hi-hat, crash (baseline DSP)                                     | `src/pipeline/drums.py`         |
| Orquesta               | Basic Pitch sobre la mezcla + asignación por tesitura (baseline; MuScriptor/YourMT3 pendientes de licencia) | `src/pipeline/transcription.py` |
| Modo auto              | Heurística: energía percusiva + tasa de golpes graves (baseline de CLAP/PANNs)                              | `src/pipeline/routing.py`       |
| Limpieza               | Notas cortas o débiles, repeticiones, octavas fuera de rango, monofonía                                     | `src/pipeline/symbolic.py`      |
| Ritmo                  | Beat tracking (librosa) + cuantización por Viterbi con penalización a la complejidad                        | `src/pipeline/rhythm.py`        |
| Tonalidad              | Krumhansl-Schmuckler + deletreo según la tonalidad (Do♯ vs Re♭)                                             | `src/pipeline/key.py`           |
| Engraving              | music21: claves (Do en 4ª para trombón agudo), instrumentos transpositores, percusión                       | `src/pipeline/score.py`         |
| Exportación            | MusicXML, partes, MIDI cuantizado y crudo, PDF                                                              | `src/pipeline/export.py`        |

### Estructura

```text
audio2score/
├── container/          # imagen del worker GPU: Dockerfile, entrypoint, requirements, versión, build-push
├── serverless/         # stacks: storage, image, worker, api, web (Serverless Framework v4)
├── src/
│   ├── contract/       # catálogo de instrumentos y contrato de jobs (Python puro, compartido)
│   ├── pipeline/       # audio → stems → notas → partitura → archivos (+ CLI)
│   ├── serving/        # servidor SageMaker (/ping, /invocations) y handler del job
│   ├── evaluation/     # métricas (SDR, F1, multi-instrument F1), datasets, ablation
│   ├── functions/jobs/ # Lambdas: ListInstruments, CreateJob, GetJob, Dispatch, OnComplete
│   ├── services/       # un módulo por servicio AWS (s3, dynamodb, sagemaker_runtime)
│   ├── utilities/      # compartido por las Lambdas
│   └── scripts/        # API local, audio sintético, evaluación
├── tests/              # pytest, espeja src/
├── web/                # SPA Vue 3 + TypeScript (ver web/README.md)
├── notebooks/          # exploración (Fase 0)
├── docs/               # plan, API, arquitectura, modelos, resultados
├── .docker/  .envs/  .claude/  package.json  pyproject.toml  pytest.ini
└── data/  outputs/     # local, ignorados por git
```

### Estado por fases

| Fase | Descripción                  | Estado                                                                                                              |
| ---- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| 0    | Fundamentos y exploración    | ✅ notebooks `01`–`04`; falta correrlos con tus audios y completar `docs/modelos.md`                                |
| 1    | Pipeline local de rock (CLI) | ✅ `npm run local:run -- song.wav --mode rock`                                                                      |
| 2    | Ruta orquestal               | ✅ con el modelo base; ⏳ MuScriptor / YourMT3 (licencia y VRAM por verificar)                                      |
| 3    | Evaluación                   | ✅ métricas y ablation (`npm run local:evaluate`); ⏳ correr sobre Slakh2100 / URMP y publicar `docs/resultados.md` |
| 4    | Worker GPU + infraestructura | ✅ IaC lista; ⏳ primer despliegue                                                                                  |
| 5    | Frontend                     | ✅ `web/`; ⏳ despliegue en CloudFront                                                                              |
| 6    | Pulido y publicación         | ✅ throttling, cuota por IP, límite de duración, página "Cómo funciona"; ⏳ métricas reales, post del portafolio    |

---

## Configuración

### Contenedor de desarrollo

Todo corre en el devcontainer (Node 24, Python 3.11, AWS CLI, Serverless v4, ffmpeg, MuseScore 3, el mismo `container/requirements.txt` que el worker).

1. Instala la extensión `ms-vscode-remote.remote-containers` de VS Code.
2. Docker debe estar corriendo: el contenedor usa el daemon del host para construir la imagen del worker.
3. Abre esta carpeta en VS Code y acepta _Reopen in Container_. El primer build tarda (torch + TensorFlow; en Apple Silicon además compila `sphn` con Rust).

Sin VS Code:

```bash
docker compose -f .docker/docker-compose.yml up -d
docker exec -it Audio2Score bash
```

> **Python 3.11** a propósito: `basic-pitch==0.4.0` no instala en 3.12+. Las Lambdas usan 3.13 porque no importan nada del pipeline, solo `src/contract`.

### Variables de entorno

Crea los archivos de `.envs/` a partir de los `*.example` (detalle en el [Glosario](#glosario)). Para desarrollo local sin AWS bastan archivos vacíos.

### Desarrollo local (sin AWS)

```bash
npm run local:demo                                   # audio sintético con verdad conocida → data/audio/demo_*.wav
npm run local:real-audio                             # grabaciones reales abiertas (MUSDB18 7 s, TRIOS) → data/real/
npm run local:run -- data/audio/demo_rock.wav --mode rock
npm run local:run -- data/audio/orquesta.wav --mode orchestra --instruments violin viola cello trombone
npm run local:api                                    # API local en http://localhost:8000 (mismo contrato que AWS)
npm run web:dev                                      # SPA en http://localhost:5173 (VITE_API_URL=http://localhost:8000)
npm test                                             # tests unitarios (rápidos, sin modelos)
npm run test:slow                                    # Demucs + Basic Pitch reales sobre el audio sintético
npm run format && npm run lint
```

La CLI escribe en `outputs/<nombre>/`: `stems/`, `midi/` (cuantizado al tempo de la partitura) y `midi/raw/` (alineado con el audio), `score.musicxml`, `parts/`, `score.mid`, `score.pdf` y `manifest.json`.

En CPU, Demucs tarda unos minutos por cada 30 s de audio. Los pesos se descargan la primera vez (en el contenedor quedan en el volumen `audio2score-models`).

### Despliegue en AWS

El orden es el mismo para `dev`, `test` y `prod`. Reemplaza `<stage>` en cada comando. Las credenciales de `.envs/aws.env` deben ser de la cuenta de ese stage.

1. `npm run deploy-storage:<stage>`: bucket de archivos, tabla de jobs, topics SNS y presupuesto. **Confirma el correo de suscripción SNS** que llega a `NOTIFICATION_EMAIL`.
2. `npm run deploy-image:<stage>`: repositorio ECR.
3. `npm run image:push`: construye la imagen del worker (linux/amd64, CUDA, pesos incluidos) y la sube. En Apple Silicon corre emulada: el primer build tarda bastante.
4. `npm run deploy-worker:<stage>`: endpoint SageMaker asíncrono con autoescalado 0..N. Falla si el paso 3 no subió la imagen. Arranca con 1 instancia y baja a 0 a los ~5 min sin jobs.
5. `npm run deploy-api:<stage>`: HTTP API y Lambdas.
6. `npm run deploy-web:<stage>`: construye `web/` con la URL de la API (SSM) y lo publica en CloudFront.

La URL de la app queda en el parámetro SSM `/audio2score-web/WebUrl`, y la de la API en `/audio2score-api/ApiUrl`.

### Actualizaciones

| Cambio                                                                                           | Pasos                                                    |
| ------------------------------------------------------------------------------------------------ | -------------------------------------------------------- |
| Pipeline, worker o `container/` (`src/pipeline`, `src/serving`, `src/contract`, `src/utilities`) | Paso 3 (`image:push`) y paso 4 (`deploy-worker`)         |
| `src/contract` (catálogo, validación)                                                            | Además del anterior, paso 5: las Lambdas también lo usan |
| Lambdas (`src/functions`, `src/services`) o configuración de la API                              | Paso 5                                                   |
| Frontend (`web/`)                                                                                | Paso 6                                                   |
| Retención, tabla, topics, presupuesto                                                            | Paso 1                                                   |

### Operación

| Tarea                                   | Comando                                                    |
| --------------------------------------- | ---------------------------------------------------------- |
| Estado del worker (instancias actuales) | `npm run worker:status`                                    |
| Probar la API con curl                  | ver [`docs/api.md`](docs/api.md)                           |
| Logs del worker                         | CloudWatch → `/aws/sagemaker/Endpoints/audio2score-worker` |
| Logs de una Lambda                      | `cd serverless/api && sls logs -f <Función> --tail`        |

Ejemplo:

```bash
API=$(aws ssm get-parameter --name /audio2score-api/ApiUrl --query Parameter.Value --output text)
JOB=$(curl -s -X POST "$API/jobs" -H 'Content-Type: application/json' \
  -d '{"mode":"rock","fileName":"demo.wav","contentType":"audio/wav","sizeBytes":'$(stat -c%s data/audio/demo_rock.wav)',"durationSec":20}')
echo "$JOB" | jq -r '.upload.fields | to_entries[] | "-F \(.key)=\(.value)"' | xargs curl -s "$(echo "$JOB" | jq -r .upload.url)" -F file=@data/audio/demo_rock.wav
curl -s "$API/jobs/$(echo "$JOB" | jq -r .jobId)" | jq '{status, stage, stages}'
```

**Costos:** fuera de uso, unos pocos USD al mes. Una `ml.g4dn.xlarge` cuesta del orden de 0,7 USD/h y solo corre mientras hay jobs, más ~5 min de enfriamiento. Las alarmas `NotScalingToZero` (3 h seguidas con una instancia) y el presupuesto mensual avisan por correo.

### Evaluación

```bash
npm run local:evaluate -- --dataset slakh --root data/slakh2100/test --limit 20
npm run local:evaluate -- --dataset urmp --root data/urmp
npm run local:evaluate -- --dataset trios --root data/real/trios   # sin registro: npm run local:real-audio
```

Compara **separar → transcribir** contra **transcribir la mezcla**, con F1 de onset por instrumento y multi-instrument F1. Escribe `outputs/evaluation/<dataset>.csv` y una tabla en markdown para [`docs/resultados.md`](docs/resultados.md). Los datasets se descargan aparte (ver `src/evaluation/datasets.py`).

### Eliminación

Usa `sls remove` en orden inverso al despliegue (`web`, `api`, `worker`, `image`, `storage`). El stack `worker` es el único con costo por hora mientras hay instancias. El repositorio ECR se conserva al quitar `image`: bórralo a mano si ya no lo necesitas.

---

## Guías de contribución

- Antes de dar un cambio por terminado: `npm run format`, `npm run lint`, `npm test` y, en cada `serverless/<stack>/` que toques, `serverless print` y `serverless package`.
- Documenta cada cambio en [`changelog.md`](changelog.md).
- Docs para personas en español; código, comentarios y `.claude/rules/` en inglés.
- Un commit por cambio, con asunto en imperativo.
- Antes de integrar un modelo nuevo, verifica su licencia en [`docs/modelos.md`](docs/modelos.md).

---

## Glosario

| Variable                                                                                 | Archivo            | Uso                                                                                      |
| ---------------------------------------------------------------------------------------- | ------------------ | ---------------------------------------------------------------------------------------- |
| `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, `AWS_DEFAULT_OUTPUT` | `.envs/aws.env`    | Credenciales de la cuenta del stage (`us-east-1`)                                        |
| `SERVERLESS_ACCESS_KEY`                                                                  | `.envs/sls.env`    | Login de Serverless Framework v4                                                         |
| `ORG`                                                                                    | `.envs/sls.env`    | Organización: forma parte del nombre del bucket de despliegue                            |
| `DEVELOPER`                                                                              | `.envs/config.env` | Alias del desarrollador; solo aparece en el bucket de despliegue de `dev`                |
| `NOTIFICATION_EMAIL`                                                                     | `.envs/config.env` | Recibe alarmas y alertas de presupuesto                                                  |
| `SKIP_IMAGE_CHECK`                                                                       | `.envs/config.env` | `true` omite la verificación de que la imagen del worker esté en ECR                     |
| `A2S_DEVICE`                                                                             | entorno del worker | `cuda` / `cpu` para Demucs (por defecto: `cuda` si hay GPU)                              |
| `A2S_DEMUCS_MODEL`                                                                       | entorno            | Modelo de Demucs (por defecto `htdemucs_6s`)                                             |
| `A2S_MULTI_BACKEND`                                                                      | entorno            | Backend de la ruta orquestal (`basic-pitch-assign`; `muscriptor` y `yourmt3` reservados) |
| `A2S_MUSESCORE`                                                                          | entorno            | Ruta al binario de MuseScore si no está en el `PATH`                                     |
| `VITE_API_URL`                                                                           | `web/.env`         | URL de la API para el frontend (por defecto `http://localhost:8000`)                     |
