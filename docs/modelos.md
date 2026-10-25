# Modelos

Qué modelos usa audio2score, qué hace cada uno, con qué configuración se invoca y qué falta verificar.
Las fórmulas están en [`matematicas.md`](matematicas.md). **Regla del repo:** antes de integrar un
modelo nuevo se verifica la licencia de su código **y de sus pesos**; lo que no se haya ejecutado o
comprobado aquí se marca "no verificado".

## Resumen

| Etapa                 | Modelo / método                                  | Parámetros del repo                                                    | ¿Aprendido? | Estado              |
| --------------------- | ------------------------------------------------ | ---------------------------------------------------------------------- | ----------- | ------------------- |
| Separación            | HTDemucs `htdemucs_6s` (`demucs==4.1.0`)         | `shifts=1`, `overlap=0.25`, `split=True`; `A2S_DEMUCS_MODEL`, `A2S_DEVICE` | sí          | en uso              |
| Transcripción melódica | Basic Pitch ICASSP 2022 (`basic-pitch==0.4.0`)  | onset 0,5 · frame 0,3 · mínimo 58 ms · rango del instrumento ± 1 octava | sí          | en uso              |
| Batería               | onsets + energía por bandas                      | ventana 50 ms, bandas 20–150 / 150–2500 / 2500–8000 / 8–16 kHz         | no (DSP)    | línea base          |
| Orquesta              | Basic Pitch + asignación por registro            | `A2S_MULTI_BACKEND=basic-pitch-assign`                                 | parcial     | línea base          |
| Modo automático       | HPSS + regresión logística a mano                | pesos −3,0 · 10,0 · 0,8                                                | no          | línea base          |
| Pulso                 | `librosa.beat.beat_track` (programación dinámica) | tempo plegado a 60–180 BPM                                             | no          | en uso              |
| Tonalidad             | Krumhansl-Schmuckler                             | perfiles de Krumhansl-Kessler                                          | no          | en uso              |
| Notación              | `music21`                                        | —                                                                      | no          | en uso              |
| Orquesta (real)       | MuScriptor / YourMT3 / MT3                       | —                                                                      | sí          | **pendiente** (licencia y VRAM por verificar) |

Solo dos redes neuronales preentrenadas están integradas (Demucs y Basic Pitch); todo lo demás es
procesamiento de señal, programación dinámica o estadística clásica. **El repo no entrena ni ajusta
ningún modelo.**

---

## HTDemucs `htdemucs_6s`

- **Qué hace:** separa la mezcla en 6 fuentes: voz, batería, bajo, guitarra, piano y otros.
- **Arquitectura:** Transformer híbrido con una rama temporal (U-Net 1-D sobre la forma de onda) y una
  espectral (U-Net 2-D sobre la STFT compleja), unidas por un Transformer con atención cruzada entre
  dominios en el cuello de botella.
- **Entrada/salida:** estéreo a 44,1 kHz → 6 stems estéreo a 44,1 kHz.
- **Uso en el repo:** `src/pipeline/separation.py`, con normalización por la media y desviación de la
  mezcla mono, segmentos solapados un 25 % y un desplazamiento aleatorio (`shifts=1`). El stem `other` no
  se transcribe.
- **Pesos:** se descargan al construir la imagen (`container/download-models.py`, `TORCH_HOME` en
  `/opt/models/torch`), no al arrancar.
- **Memoria:** debe caber junto a Basic Pitch en 16 GB de la T4. **No verificado en AWS.**
- **Limitaciones:** el stem de piano es el más débil de los seis; no existen stems orquestales, por eso esa
  ruta no usa separación.
- **Licencia:** código y pesos **no verificados aquí**; comprobar antes de publicar el servicio.

## Basic Pitch

- **Qué hace:** transcripción polifónica de notas independiente del instrumento, con detección de
  _pitch bends_ (que el repo no usa).
- **Arquitectura:** red convolucional ligera sobre una CQT con _harmonic stacking_; tres salidas por cuadro
  (onset, nota activa, contorno).
- **Entrada/salida:** audio mono a 22 050 Hz → notas en un `PrettyMIDI` (A0–C8, MIDI 21–108).
- **Uso en el repo:** `src/pipeline/transcription.py`. El modelo (TensorFlow, empaquetado dentro de
  `basic-pitch`) se carga una vez (`lru_cache`). El rango del instrumento se pasa como frecuencia mínima y
  máxima; pedir una frecuencia fuera de A0–C8 devuelve cero notas, por eso se limita a ese intervalo.
- **Dependencias:** arrastra TensorFlow 2.15 y numpy 1.26; exige **Python 3.11**.
- **Limitaciones observadas** (Fase 0, audio real): errores de octava (se corrigen con plegado al rango),
  notas fragmentadas (se fusionan) y una sola "voz" por stem aunque el instrumento sea polifónico.
- **Licencia:** **no verificada aquí.**

## Detector de batería (DSP)

Línea base transparente para compararla con un transcriptor aprendido (ADTOF, Omnizart) en la fase de
evaluación. Distingue bombo, caja, hi-hat y crash; no distingue ride ni toms. Ver §4 de
[`matematicas.md`](matematicas.md).

## Ruta orquestal (línea base)

Basic Pitch sobre la mezcla y un reparto por rango/tesitura. **No distingue instrumentos por timbre**: dos
violines o violín y flauta en el mismo registro no se separan. Con piano falla (F1 multi-instrumento 0,37 en
TRIOS). Los backends que lo resolverían —**MuScriptor**, **YourMT3**, **MT3**— están reservados en
`transcription.py` y lanzan `BackendUnavailable` hasta que se verifique:

1. licencia del código **y de los pesos** (uso en un servicio público);
2. VRAM necesaria junto con el resto del pipeline en una T4 de 16 GB;
3. API estable de inferencia.

## Clasificador de ruta

Logística de dos rasgos con pesos fijados a mano (no calibrados); etiqueta como rock los tríos clásicos.
El plan prevé reemplazarla por embeddings CLAP/PANNs con un umbral, manteniendo la misma salida
(`RouteDecision`).

---

## Cómo evaluar un modelo nuevo

1. Implementar el backend detrás de `transcription.transcribe_mix` (o `separation.separate`).
2. Correr `npm run local:evaluate -- --dataset slakh --root data/slakh2100/test --limit 20` (también `urmp` y
   `trios`) y comparar F1 por instrumento y F1 multi-instrumento contra la línea base.
3. Documentar los números en `docs/resultados.md` (todavía **no existe**: las métricas no se han corrido
   sobre Slakh2100/URMP).
4. Registrar licencia y VRAM aquí antes de activarlo en el worker.
