# Documentación de audio2score

| Documento                                 | Para qué sirve                                                                                          |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------- |
| [`matematicas.md`](matematicas.md)        | Formulación matemática de cada etapa: STFT, separación, Basic Pitch, batería, asignación DP, HPSS, Viterbi, Krumhansl-Schmuckler, notación y métricas |
| [`pipeline.md`](pipeline.md)              | Flujo de procesamiento del audio: rutas rock y orquesta, engraving, exportación, manifiesto, errores    |
| [`modelos.md`](modelos.md)                | Modelos usados, su configuración, limitaciones y lo pendiente de verificar (licencias, VRAM)             |
| [`api.md`](api.md)                        | Contrato HTTP: endpoints, estados del job, errores, límites y ejemplo con curl                          |
| [`arquitectura.md`](arquitectura.md)      | AWS: stacks, secuencia entre servicios, DynamoDB/S3, worker GPU y autoescalado, frontend, alarmas       |
| [`architecture.drawio`](architecture.drawio) | Diagrama editable de la arquitectura                                                                 |

Orden de lectura sugerido: `pipeline.md` → `modelos.md` → `matematicas.md` (el _qué_ y el _por qué_ del
audio) y `arquitectura.md` → `api.md` (cómo se sirve).

Los diagramas son Mermaid y las fórmulas LaTeX (`$…$`): se ven en GitHub y en VS Code con la vista previa
de Markdown.

## Pendiente

Los README y `CLAUDE.md` mencionan dos documentos que aún no existen: `PLAN.md` (formulación, fases y
riesgos) y `resultados.md` (métricas de evaluación y hallazgos de la Fase 0). Ninguno se inventó aquí: el
segundo depende de correr la evaluación sobre Slakh2100 y URMP.
