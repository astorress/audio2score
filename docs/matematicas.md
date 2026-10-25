# Fundamentos matemáticos

Formulación de cada etapa del pipeline, tal como está implementada en `src/pipeline/`. Cuando un modelo
es una caja negra preentrenada (Demucs, Basic Pitch) se describe su formulación publicada; las
constantes y reglas que aparecen aquí son las del código.

- [0. Notación](#0-notación)
- [1. Representación del audio](#1-representación-del-audio)
- [2. Separación de fuentes (HTDemucs)](#2-separación-de-fuentes-htdemucs)
- [3. Transcripción de notas (Basic Pitch)](#3-transcripción-de-notas-basic-pitch)
- [4. Batería: detección de golpes por bandas](#4-batería-detección-de-golpes-por-bandas)
- [5. Ruta orquestal: asignación de notas a instrumentos](#5-ruta-orquestal-asignación-de-notas-a-instrumentos)
- [6. Modo automático: clasificación de la ruta](#6-modo-automático-clasificación-de-la-ruta)
- [7. Limpieza simbólica](#7-limpieza-simbólica)
- [8. Ritmo: pulso, compás y cuantización](#8-ritmo-pulso-compás-y-cuantización)
- [9. Tonalidad y ortografía de alturas](#9-tonalidad-y-ortografía-de-alturas)
- [10. Notación: de notas a partitura](#10-notación-de-notas-a-partitura)
- [11. Métricas de evaluación](#11-métricas-de-evaluación)

---

## 0. Notación

| Símbolo                | Significado                                                                       |
| ---------------------- | --------------------------------------------------------------------------------- |
| $x[n]$                 | señal de audio en tiempo discreto, $n = 0,\dots,N-1$                              |
| $f_s$                  | frecuencia de muestreo (44 100 Hz para separación; 22 050 Hz para análisis)       |
| $X[m,k]$               | STFT en el cuadro $m$ y el bin $k$                                                |
| $p$                    | altura MIDI: $p = 69 + 12\log_2(f/440)$, de modo que $f = 440\cdot 2^{(p-69)/12}$ |
| $\text{pc}(p)$         | clase de altura, $p \bmod 12$                                                     |
| $n = (p, t_0, t_1, v)$ | nota: altura, inicio, fin y velocity (`Note` en `notes.py`)                       |
| $\beta(t)$             | posición en pulsos (negras) del instante $t$ en segundos                          |
| $[l_i, h_i]$           | rango (MIDI sonoro) del instrumento $i$, definido en `contract/instruments.py`    |

Hasta la cuantización, los tiempos de una nota están en **segundos**; después, en **negras** (quarter
notes), con $t_0, t_1 \in \mathbb{Q}$ (múltiplos de $1/2$, $1/3$, $1/4$, $1/6$ u $1/8$).

---

## 1. Representación del audio

`audio.py` decodifica con librosa (ffmpeg/libsndfile), remuestrea a $f_s = 44100$ Hz y conserva los
canales: un tensor $x \in \mathbb{R}^{C \times N}$ en `float32`. El audio se recorta a
$N \le f_s \cdot T_{\max}$ con $T_{\max} = 90$ s.

La **STFT** de una señal con ventana $w$ de $L$ muestras y salto $H$ es

$$
X[m,k] = \sum_{n=0}^{L-1} x[n + mH]\, w[n]\, e^{-j 2\pi k n / L}.
$$

El espectro de potencia es $|X[m,k]|^2$ y el bin $k$ corresponde a $f_k = k f_s / L$. Se usa en tres
sitios: el modelo de separación (internamente), la clasificación de ruta (`routing.py`: $L = 2048$,
$H = 512$) y la detección de batería (ventanas de $0{,}05$ s con Hann).

Para el análisis rítmico y de ruta el mix se pasa a mono y a $22\,050$ Hz (`ANALYSIS_RATE`):

$$
x_{\text{mono}}[n] = \frac{1}{C}\sum_{c=1}^{C} x_c[n].
$$

---

## 2. Separación de fuentes (HTDemucs)

**Problema.** Dada la mezcla $x = \sum_{s=1}^{S} y_s$ (con $S = 6$ en `htdemucs_6s`: voz, batería,
bajo, guitarra, piano, otros), estimar cada fuente $\hat{y}_s$.

### 2.1 Modelo

HTDemucs (_Hybrid Transformer Demucs_, Rouard et al. 2023) es una red de **dos ramas** que operan en
paralelo y se fusionan en el cuello de botella:

- **Rama temporal:** U-Net convolucional 1-D sobre la forma de onda $x \in \mathbb{R}^{C\times N}$
  (codificador con submuestreo y decodificador con conexiones de salto).
- **Rama espectral:** U-Net 2-D sobre la STFT compleja $X$, con parte real e imaginaria apiladas como
  canales (_complex-as-channels_, CaC), y convoluciones sobre (frecuencia, tiempo).
- **Transformer entre dominios:** en el cuello de botella, capas de autoatención dentro de cada rama y
  de **atención cruzada** entre ramas. Con $Q, K, V$ proyecciones de las representaciones:

$$
\operatorname{Attn}(Q,K,V) = \operatorname{softmax}\!\left(\frac{QK^\top}{\sqrt{d}}\right)V .
$$

La salida final es la suma de las dos ramas, cada una devuelta a forma de onda (la espectral mediante
la iSTFT):

$$
\hat{y}_s = \hat{y}^{\text{tiempo}}_s + \text{iSTFT}\big(\hat{Y}^{\text{espectro}}_s\big).
$$

Entrenamiento: pérdida $L_1$ en el dominio temporal, $\mathcal{L} = \tfrac{1}{S}\sum_s \lVert \hat{y}_s - y_s\rVert_1$,
sobre segmentos de unos 8 s. Se usan los pesos preentrenados; **este repo no entrena nada**.

> Los detalles internos (profundidad, canales, número de capas del Transformer) son los del paper y de
> la librería `demucs==4.1.0`; no se verificaron aquí. Lo que sí es del repo es lo que sigue.

### 2.2 Inferencia (`separation.py`)

1. **Normalización.** Con $r = \tfrac{1}{C}\sum_c x_c$ (referencia mono), $\mu = \operatorname{mean}(r)$ y
   $\sigma = \operatorname{std}(r) + 10^{-8}$:

$$
\tilde{x} = \frac{x - \mu}{\sigma}, \qquad \hat{y}_s = \sigma\, f_\theta(\tilde{x})_s + \mu .
$$

2. **Mono → estéreo.** Si la entrada es mono se replica al número de canales del modelo (2).
3. **Troceado con solape.** `apply_model(..., split=True, overlap=0.25)` divide la señal en segmentos
   de la longitud de entrenamiento con un 25 % de solape y los recompone por _overlap-add_ con una
   ventana de peso triangular $\omega(n)$:

$$
\hat{y}[n] = \frac{\sum_j \omega_j(n)\,\hat{y}_j[n]}{\sum_j \omega_j(n)} .
$$

4. **Truco de desplazamientos aleatorios** (`shifts=1`): se promedia la salida del modelo sobre
   desplazamientos temporales aleatorios $\tau$ de la entrada, lo que reduce el error por posición
   dentro del segmento: $\hat{y} = \tfrac{1}{K}\sum_{k} f_\theta(x(\cdot-\tau_k))(\cdot+\tau_k)$ con
   $K = 1 + \text{shifts}$ pasadas efectivas según la implementación de Demucs.

Cada fuente se escribe como WAV PCM de 16 bits a 44,1 kHz. El stem `other` **no se transcribe**
(`UNTRANSCRIBED_STEMS` en `contract/instruments.py`).

**Complejidad.** El costo es lineal en la duración; en CPU son unos minutos por cada 30 s de audio.
En GPU (T4) se espera ~1-2 min por clip de 90 s, una estimación del IaC aún **no medida** (ver
`docs/arquitectura.md`).

---

## 3. Transcripción de notas (Basic Pitch)

**Problema.** Dado un audio monofónico o polifónico de un solo instrumento, estimar un conjunto de
notas $\{(p_i, t_{0,i}, t_{1,i}, v_i)\}$. Basic Pitch (Bittner et al. 2022) es una red
convolucional pequeña, **independiente del instrumento**.

### 3.1 Modelo

- **Entrada:** CQT con _harmonic stacking_. Se calcula la Transformada Q-constante a 22 050 Hz con 3 bins
  por semitono,

$$
f_b = f_{\min}\, 2^{\,b/36}, \qquad X^{\text{CQT}}[m,b],
$$

y se apilan versiones desplazadas del CQT en los armónicos $h \in \{\tfrac12, 1, 2,\dots,7\}$ como
canales, de modo que los armónicos de una nota queden alineados en el eje de frecuencia.

- **Salidas** (tres _posteriorgramas_ por cuadro $m$ y altura $p$, con $\approx 86$ cuadros/s):
  - $O[m,p]\in[0,1]$: probabilidad de **inicio** de nota (onset),
  - $N[m,p]\in[0,1]$: probabilidad de que la nota esté **activa** (frame),
  - $C[m,b]$: **contorno** de $f_0$ a resolución de tercio de semitono (para pitch bends).

### 3.2 De posteriorgramas a notas

Con los umbrales de `transcription.py` — `ONSET_THRESHOLD` $\theta_o = 0{,}5$, `FRAME_THRESHOLD`
$\theta_f = 0{,}3$ y duración mínima 58 ms —:

1. Se buscan **máximos locales** de $O$ por altura con $O[m,p] > \theta_o$: cada uno abre una nota.
2. Desde el inicio se avanza mientras $N[m,p] > \theta_f$ (con una pequeña tolerancia de cuadros por
   debajo del umbral); donde cae, la nota termina.
3. Se descartan las notas más cortas que 58 ms.
4. La velocity se obtiene de la amplitud de $N$ en la nota, reescalada a $[1,127]$.

El repo **ignora los pitch bends**: `from_pretty_midi` solo conserva `(pitch, start, end, velocity)`.

### 3.3 Restricción por rango del instrumento

Basic Pitch cubre A0–C8 (MIDI 21–108): pedirle una frecuencia fuera de ese intervalo no devuelve
notas. Para un instrumento con rango $[l, h]$ se restringe la búsqueda a

$$
[\,\max(l - 12,\ 21),\ \min(h + 12,\ 108)\,]
$$

(una octava de holgura a cada lado, `transcribe_stem`), con frecuencias límite
$f_{\min} = 440\cdot 2^{(l'-0{,}5-69)/12}$ y $f_{\max} = 440\cdot 2^{(h'+0{,}5-69)/12}$. La holgura es
deliberada: los errores de octava son el fallo más habitual de la transcripción automática y se
corrigen después con el plegado de octavas (§7.2), en vez de perder la nota.

---

## 4. Batería: detección de golpes por bandas

Es una línea base DSP transparente (`drums.py`), pensada para compararla después con un transcriptor
aprendido.

### 4.1 Onsets

Sobre el stem de batería (mono, 44,1 kHz) se calcula la **envolvente de fuerza de onset** de librosa,
$\text{OSE}[m]$: la suma sobre frecuencias del flujo espectral positivo (media-onda rectificada) del
espectrograma mel en dB,

$$
\text{OSE}[m] = \sum_{k} \max\!\big(0,\ S_{\text{dB}}[k,m] - S_{\text{dB}}[k,m-1]\big),
$$

y se eligen los picos con `onset_detect(backtrack=True)`: cada pico se retrocede hasta el mínimo local
previo, que es donde el golpe realmente empieza.

### 4.2 Energía por banda tras cada golpe

Para cada onset $t_j$, con $W = 0{,}05$ s:

$$
P_j[k] = \Big|\sum_{n=0}^{W f_s - 1} x[t_j f_s + n]\, w_{\text{Hann}}[n]\, e^{-j2\pi kn/(W f_s)}\Big|^2,
\qquad
E_{b,j} = \sum_{f_k \in B_b} P_j[k]
$$

con las bandas $B_{\text{low}} = [20,150)$, $B_{\text{mid}} = [150,2500)$,
$B_{\text{noise}} = [2500,8000)$, $B_{\text{high}} = [8000,16000)$ Hz. También se mide el
**sostenimiento**, la razón entre el RMS de la cola (de 50 a 350 ms) y el de la cabeza (50 ms):

$$
\text{sust}_j = \frac{\operatorname{RMS}\big(x[t_j + W : t_j + 0{,}35]\big)}{\operatorname{RMS}\big(x[t_j : t_j + W]\big)}.
$$

### 4.3 Regla de decisión

Con la cuota de cada banda $s_b = E_b / \sum_{b'} E_{b'}$ y la razón respecto de la **mediana** de esa
banda en todos los golpes de la pieza, $r_b = E_b / \operatorname{med}_j(E_{b,j})$, un golpe puede
disparar varios instrumentos a la vez (bombo + hi-hat):

| Instrumento (GM)   | Condición                                                                          |
| ------------------ | ---------------------------------------------------------------------------------- |
| Bombo (36)         | $s_{\text{low}} > 0{,}35$ y $r_{\text{low}} > 0{,}6$                               |
| Caja (38)          | $s_{\text{mid}}+s_{\text{noise}} > 0{,}35$, $r_{\text{noise}} > 0{,}6$, $r_{\text{mid}} > 0{,}3$ |
| Hi-hat (42) / Crash (49) | $s_{\text{high}} > 0{,}08$ y $r_{\text{high}} > 0{,}6$; crash si $\text{sust} > 0{,}5$, si no hi-hat |

Si ninguna condición dispara, se asigna el instrumento de la banda dominante. La velocity es

$$
v_j = \operatorname{clip}\!\Big(40 + 87\,\frac{\text{OSE}[m_j]}{\max_m \text{OSE}[m]},\ 1,\ 127\Big).
$$

Cada golpe se escribe como una nota de 0,1 s en el canal de percusión. **No detecta ride** (limitación
conocida).

---

## 5. Ruta orquestal: asignación de notas a instrumentos

No hay stems orquestales en Demucs, así que la ruta orquestal transcribe la **mezcla completa** con
Basic Pitch (en el rango $[\min_i l_i,\ \max_i h_i]$ de los instrumentos pedidos) y reparte cada nota
entre los instrumentos solicitados por **registro y tesitura**. Es una línea base, no AMT
multi-instrumento real: se asigna por rango, no por timbre.

### 5.1 Agrupar en acordes

Se ordenan las notas por inicio y se agrupan las que empiezan a menos de $\Delta = 0{,}05$ s de la
primera del grupo. Cada acorde se resuelve de forma independiente.

### 5.2 Costo de una asignación

La **tesitura** del instrumento $i$ es $\tau_i = (l_i + h_i)/2$. El costo de que el instrumento $i$
toque la nota de altura $p$ es

$$
c(p, i) =
\begin{cases}
+\infty & p \notin [l_i, h_i] \\[2pt]
\dfrac{|p - \tau_i|}{h_i - l_i} + \mathbb{1}[\text{$i$ monofónico y ocupado}]\cdot 1{,}0 & \text{en otro caso}
\end{cases}
$$

(la distancia al centro del rango, medida en "anchos de rango"). "Ocupado" significa que el
instrumento ya tiene una nota sonando en ese instante.

### 5.3 Alineamiento monótono por programación dinámica

Sean las notas del acorde ordenadas por altura ascendente $p_1 \le \dots \le p_q$ y los instrumentos
ordenados por tesitura ascendente $i = 1,\dots,m$. Se busca una asignación $a_1,\dots,a_q$ con
$a_k \in \{1,\dots,m\} \cup \{\varnothing\}$ que cumpla:

- **no cruce de voces:** los índices de instrumento asignados son **no decrecientes** con la altura;
- un instrumento **monofónico** toma como máximo una nota del acorde;
- compartir un instrumento polifónico cuesta $\gamma = 0{,}3$ extra;
- una nota que ningún instrumento puede tocar queda sin asignar con costo $\sigma = 2{,}0$.

Estado: $D_k(j)$ = costo mínimo de las primeras $k$ notas con el último instrumento usado $j$
($j=0$: ninguno todavía).

$$
D_k(j) = \min\Big\{\, D_{k-1}(j) + \sigma,\ \ \min_{j' \le j}\ D_{k-1}(j') + c(p_k, j) + \gamma\,\mathbb{1}[j'=j]\,\Big\}
$$

con la restricción de que $j'=j$ solo es válido si $j$ es polifónico. La solución es
$\min_j D_q(j)$ y se recupera con los punteros de retroceso. Complejidad $O(q\,m^2)$ por acorde, con
$q$ y $m$ pequeños.

Tras asignar un acorde, se actualiza $\text{busy}_i \leftarrow \max(\text{busy}_i, t_1)$.

---

## 6. Modo automático: clasificación de la ruta

Para `mode = auto` (`routing.py`), se decide entre **rock** y **orquesta** con un clasificador
logístico de dos rasgos, calculados sobre el mix mono a 22 050 Hz.

**Rasgo 1: fracción percusiva.** Con la magnitud de la STFT $S = |X|$ ($L=2048$, $H=512$), la
separación armónico/percusiva (HPSS, Fitzgerald 2010) filtra con medianas: $S_H$ suaviza **a lo largo
del tiempo** (líneas horizontales = tonos sostenidos) y $S_P$ **a lo largo de la frecuencia** (líneas
verticales = transitorios). Luego se aplican máscaras suaves:

$$
\hat{H} = S \odot \frac{\tilde{S}_H^{\,2}}{\tilde{S}_H^{\,2} + \tilde{S}_P^{\,2}},\qquad
\hat{P} = S \odot \frac{\tilde{S}_P^{\,2}}{\tilde{S}_H^{\,2} + \tilde{S}_P^{\,2}},
\qquad
\rho = \frac{\lVert \hat{P}\rVert_F^2}{\lVert \hat{H}\rVert_F^2 + \lVert \hat{P}\rVert_F^2 + \varepsilon}.
$$

**Rasgo 2: tasa de bombos.** Se toma $\hat{P}$ por debajo de 150 Hz, se calcula la envolvente de
onset en dB y se cuenta el número de picos por segundo, $\kappa$.

**Decisión:**

$$
z = -3{,}0 + 10{,}0\,\rho + 0{,}8\,\kappa,\qquad
P(\text{rock}) = \sigma(z) = \frac{1}{1+e^{-z}},\qquad
\text{ruta} = \begin{cases}\text{rock} & P \ge 0{,}5\\ \text{orquesta} & \text{si no}\end{cases}
$$

Los pesos están fijados a mano sobre audio sintético y real de los notebooks; **no están calibrados**.
Limitación conocida: la tasa de graves cuenta también notas de piano o violonchelo y etiqueta como
rock tríos clásicos (ver "Open items" en `CLAUDE.md`). El plan prevé reemplazar `classify` por un
clasificador sobre embeddings (CLAP/PANNs) con la misma salida.

---

## 7. Limpieza simbólica

`symbolic.prepare` aplica, por instrumento y en este orden, tres filtros sobre las notas en segundos.

### 7.1 Notas espurias y fragmentos (`clean_notes`)

- Se eliminan las notas con duración $< 0{,}05$ s o velocity $< 20$.
- Dos notas de la **misma altura** se **fusionan** si el hueco entre ellas es $< 0{,}03$ s **y** al
  menos una dura $< 0{,}12$ s (una nota sostenida partida por el transcriptor):

$$
t_{0,\text{nuevo}} = t_{0,a},\quad t_{1,\text{nuevo}} = \max(t_{1,a}, t_{1,b}),\quad v = \max(v_a, v_b).
$$

Dos notas largas seguidas se respetan (un bajo que toca negras re-articula).

### 7.2 Plegado de octavas (`filter_range`)

Con rango $[l, h]$, una nota a lo sumo una octava fuera de rango se **desplaza una octava** hacia
dentro; más lejos se descarta:

$$
p' =
\begin{cases}
p + 12 & l - 12 \le p < l\\
p - 12 & h < p \le h + 12\\
p & l \le p \le h \\
\text{descartada} & \text{en otro caso.}
\end{cases}
$$

### 7.3 Reducción a una voz (`to_monophonic`)

Para instrumentos monofónicos, se recorre el orden $(t_0, -v, -p)$. Si la nota nueva solapa con la
actual:

- si empiezan juntas, se queda la primera del orden (la más fuerte y, a igualdad, la más aguda);
- si no, gana la de mayor $(v, p)$ lexicográfico: la anterior se **corta** en $t_0$ de la nueva; si
  pierde la nueva pero termina después, se conserva solo su **cola** tras el fin de la actual.

(La más fuerte, y a igualdad la más aguda, es la heurística habitual de melodía.)

---

## 8. Ritmo: pulso, compás y cuantización

Convierte tiempo continuo (segundos) en tiempo métrico (negras): `rhythm.py`.

### 8.1 Seguimiento del pulso

El rastreador de pulso de librosa (Ellis 2007) usa la envolvente de onset $O[m]$ y programación
dinámica. Busca los instantes $\{b_k\}$ que maximizan

$$
\sum_{k} O[b_k] \;-\; \alpha \sum_{k} \Big(\log \frac{b_k - b_{k-1}}{\tau}\Big)^{2},
$$

donde $\tau$ es el periodo de pulso estimado a partir de la autocorrelación de $O$ (con prior
log-gaussiano centrado en 120 BPM) y $\alpha$ pondera la regularidad. Si se detectan menos de 4
pulsos (silencio, tiempo libre) se usa una rejilla regular de 120 BPM.

### 8.2 Normalización del tempo

Los trackers se enganchan a la mitad o al doble del pulso real. Se pliega la rejilla al intervalo
$[60, 180]$ BPM, con $\text{BPM} = 60/\operatorname{med}(\Delta b)$:

- si $\text{BPM} < 60$: se **duplica** la densidad insertando puntos medios $(b_k + b_{k+1})/2$;
- si $\text{BPM} > 180$ (con al menos 8 pulsos): se **toma un pulso de cada dos**;
- hasta 4 iteraciones.

El tempo de la partitura es la mediana: $\text{tempo} = \operatorname{round}\big(60/\operatorname{med}(\Delta b)\big)$.

### 8.3 Compás y fase del primer tiempo

Con la fuerza de onset en cada pulso $s_k$, para cada métrica $M \in \{3,4\}$ y fase
$\phi \in \{0,\dots,M-1\}$ se mide el **contraste** de acentuación:

$$
\text{contraste}(M,\phi) = \overline{s_{\{k \equiv \phi \pmod M\}}} - \overline{s_{\{k \not\equiv \phi \pmod M\}}},\qquad
\phi^*_M = \arg\max_\phi \text{contraste}(M,\phi).
$$

Se elige **3/4 solo si** $\text{contraste}(3,\phi_3^*) > 1{,}15\cdot \text{contraste}(4,\phi_4^*)$ y es
positivo; en cualquier otro caso, 4/4 (es, con diferencia, el compás más habitual en ambos géneros).

### 8.4 Segundos → pulsos

Con pulsos detectados $b_0 < b_1 < \dots < b_{K-1}$, la posición métrica es la **interpolación
lineal a trozos**

$$
\beta(t) = k + \frac{t - b_k}{b_{k+1} - b_k}, \qquad t \in [b_k, b_{k+1}],
$$

extrapolada en los extremos con el primer y último intervalo. Así el rubato y la deriva de tempo
**curvan la rejilla** en lugar de acumular error. El compás 1 empieza en el último primer tiempo
anterior a la primera nota (`measure_origin`); lo anterior queda como anacrusa rellena con silencios.

### 8.5 Cuantización por Viterbi

**Idea.** Cada pulso elige **una subdivisión** $s \in \mathcal{S}$ (negra, corcheas, semicorcheas,
tresillos…) que equilibra tres términos: el error de ajuste de sus notas, la complejidad rítmica y la
estabilidad entre pulsos vecinos (una partitura se lee mejor si no cambia de subdivisión a cada rato).

Subdivisiones por negra y complejidad $C(s)$:

| $s$ | 1 | 2 | 4 | 8 | 3 | 6 |
| --- | -- | -- | -- | -- | -- | -- |
| $C(s)$ | 0 | 1 | 2 | 3 | 2,5 | 3,5 |

El conjunto $\mathcal{S}$ lo fija la opción `quantization` (`1/8` → $s\le 2$, `1/16` → $s \le 4$, `1/32`
→ $s \le 8$) y `allowTriplets` añade $s=3$ (y $s=6$ si $s_{\max}\ge 4$).

Sea $F_b = \{\beta_i - b\}$ el conjunto de fracciones de las notas cuyo inicio cae en el pulso $b$
(un inicio pertenece al pulso $\lfloor \beta + \epsilon \rfloor$ con $\epsilon = 1/(2 s_{\max})$, de modo
que un golpe apenas antes del pulso se asigna a ese pulso). El **ajuste** a la rejilla $s$ es
$\text{snap}_s(f) = \operatorname{round}(f\,s)/s$ y el costo de emisión

$$
e_b(s) = \sum_{f \in F_b} |f - \text{snap}_s(f)| \;+\; \lambda_C\, C(s),\qquad \lambda_C = 0{,}03 .
$$

El costo de transición entre pulsos consecutivos es $\lambda_S\,\mathbb{1}[s \ne s']$ con
$\lambda_S = 0{,}02$. Se busca la secuencia $s_0,\dots,s_{B-1}$ de costo mínimo,

$$
\min_{s_{0:B-1}}\ \sum_{b=0}^{B-1} e_b(s_b) + \lambda_S \sum_{b=1}^{B-1} \mathbb{1}[s_b \neq s_{b-1}],
$$

resuelta con el algoritmo de Viterbi:

$$
V_b(s) = e_b(s) + \min_{s'}\big(V_{b-1}(s') + \lambda_S\,\mathbb{1}[s \ne s']\big),
$$

con punteros de retroceso, en $O(B\,|\mathcal{S}|^2)$. Los pesos están en unidades de **pulsos** de error:
$\lambda_C$ y $\lambda_S$ son pequeños, por lo que una subdivisión más compleja se paga solo si reduce de
verdad el error de ajuste.

Tras decidir la subdivisión $s_b$ de cada pulso, el inicio $\beta$ de una nota se proyecta a
$b + \text{snap}_{s_b}(\beta - b)$, el fin igual, con duración mínima $1/s_b$.

Todas las pistas se cuantizan contra la **misma rejilla y el mismo origen de compás**, para que
las partes queden alineadas.

---

## 9. Tonalidad y ortografía de alturas

### 9.1 Algoritmo de Krumhansl-Schmuckler

El perfil de clases de altura de la pieza acumula la **duración** de cada clase:

$$
\mathbf{p}[c] = \sum_{n:\ \text{pc}(p_n) = c} (t_{1,n} - t_{0,n}), \qquad c = 0,\dots,11 .
$$

Se correlaciona (Pearson) con los 24 perfiles de tono de prueba de Krumhansl-Kessler,
$\mathbf{K}^{\text{mayor}}$ y $\mathbf{K}^{\text{menor}}$ rotados a cada tónica $\tau$:

$$
r(\tau, \text{modo}) = \operatorname{corr}\big(\mathbf{p},\ \operatorname{roll}(\mathbf{K}^{\text{modo}}, \tau)\big),
\qquad
(\hat\tau, \widehat{\text{modo}}) = \arg\max_{\tau,\ \text{modo}} r(\tau, \text{modo}).
$$

Perfiles usados (`key.py`):

$$
\begin{aligned}
\mathbf{K}^{\text{mayor}} &= [6{,}35, 2{,}23, 3{,}48, 2{,}33, 4{,}38, 4{,}09, 2{,}52, 5{,}19, 2{,}39, 3{,}66, 2{,}29, 2{,}88]\\
\mathbf{K}^{\text{menor}} &= [6{,}33, 2{,}68, 3{,}52, 5{,}38, 2{,}60, 3{,}53, 2{,}54, 4{,}75, 3{,}98, 2{,}69, 3{,}34, 3{,}17]
\end{aligned}
$$

Solo cuentan las notas **afinadas** (la batería no). Con menos de dos clases de altura presentes se
devuelve Do mayor con correlación 0.

### 9.2 Ortografía

La tonalidad ($\hat\tau$ y modo) fija el nombre de cada clase de altura para que las alteraciones se
lean con naturalidad (Do♯ frente a Re♭): `spelling_map` asigna a cada clase el nombre que tiene en la
escala de la tonalidad (en modo menor también la 6.ª y 7.ª subidas) y, para las notas cromáticas
restantes, la alteración con la dirección de la armadura (sostenidos si $\#>0$, bemoles si $\#<0$,
y la ortografía más habitual si no hay alteraciones). La octava se recalcula desde el número MIDI
para que casos como Si♯/Do♭ crucen bien el límite de octava.

---

## 10. Notación: de notas a partitura

`score.py` construye un `music21.Score` partiendo de notas cuantizadas en negras.

### 10.1 Instrumentos transpositores

Cada parte se escribe en **altura escrita**. Con el intervalo de transposición $I$ (de escrita a
sonora, p. ej. `"M-2"` para el clarinete en Si♭: suena una 2.ª mayor por debajo) y $\delta = $
semitonos de $I$:

$$
p_{\text{escrita}} = p_{\text{sonora}} - \delta,\qquad
\text{tonalidad escrita} = \text{tonalidad de concierto}\ \text{transpuesta por}\ I^{-1}.
$$

Para el clarinete en Si♭, $\delta = -2$, así que se escribe una 2.ª mayor **más agudo**. La parte lleva
`atSoundingPitch = False`, y los lectores de MusicXML la reproducen a altura de concierto.

### 10.2 Notas solapadas → acordes con ligaduras

Si hay solapes, el eje del tiempo se parte en todos los inicios y finales
$\mathcal{B} = \{t_0\} \cup \{t_1\}$ ordenados. En cada tramo $[\beta_j, \beta_{j+1})$ suenan las notas
activas: una sola es una nota; varias, un **acorde**. Una nota que continúa en el tramo siguiente se
une con **ligaduras** `start` / `continue` / `stop`. Es un `chordify` manual y determinista. Las
duraciones se representan como fracciones exactas, $\operatorname{limit\_denominator}(48)$, para que
semicorcheas, fusas y tresillos no acumulen error de coma flotante.

### 10.3 Reglas de lectura

| Regla                       | Valor                                                                                       |
| --------------------------- | ------------------------------------------------------------------------------------------- |
| Legato                      | un hueco $\le 0{,}25$ negras se absorbe en la nota anterior (los offsets del AMT son ruidosos) |
| Batería                     | cada golpe dura hasta el siguiente, como máximo 1 negra                                      |
| Clave de Do en 4.ª          | trombón, fagot y violonchelo, si $\ge 60\,\%$ de sus notas son $\ge$ MIDI 62 (Re4)          |
| Gran pentagrama             | piano y arpa: $p \ge 60$ (Do central) a la mano derecha, el resto a la izquierda            |
| Percusión                   | clave de percusión; cada altura GM se dibuja en una línea con su cabeza (× para platos)    |
| Longitud común              | todas las partes se rellenan con silencios hasta un número entero de compases              |

El tempo $\text{round}(\text{BPM})$ y el compás $M/4$ salen de la rejilla (§8). `makeNotation` de
music21 pone las barras de compás, parte las notas largas con ligaduras y agrupa las corcheas.

### 10.4 MIDI cuantizado

Para que el MIDI suene en sincronía con el cursor de la partitura, el MIDI de cada instrumento se
escribe a tempo constante, $t[\text{s}] = q \cdot 60/\text{tempo}$, donde $q$ está en negras. Además se
guarda el MIDI **crudo** (`midi/raw/`), en segundos alineados con el audio original.

---

## 11. Métricas de evaluación

`src/evaluation/metrics.py` y `ablation.py` miden cada etapa contra una verdad conocida.

**SDR de un stem** (dB):

$$
\text{SDR}(y, \hat{y}) = 10\log_{10}\frac{\lVert y\rVert^2 + \varepsilon}{\lVert y - \hat{y}\rVert^2 + \varepsilon}.
$$

**F1 de notas** (`mir_eval`): una nota estimada acierta si su altura coincide (a menos de 50 cents) y su
inicio está a $\pm 50$ ms del de una nota de referencia, con emparejamiento uno a uno (opcionalmente
también el fin, dentro del 20 % de la duración). Con $M$ aciertos, $R$ notas de referencia y $E$ estimadas:

$$
P = \frac{M}{E},\qquad \text{Rec} = \frac{M}{R},\qquad F_1 = \frac{2P\,\text{Rec}}{P + \text{Rec}} .
$$

**F1 multi-instrumento:** como en MT3, una nota cuenta solo si coinciden altura, inicio **e**
instrumento; $M$, $R$ y $E$ se suman (micropromedio) sobre todos los instrumentos.

**Exactitud de compases:** proporción de compases (de todas las partes, excluyendo el primero y el
último, por anacrusa y cierre) cuya duración coincide con la del compás:

$$
\text{exactitud} = \frac{\#\{m : |d_m - d_{\text{compás}}| < 10^{-6}\}}{\#\{m\}} .
$$

**Ablation (`ablation.py`).** Compara dos estrategias sobre las mismas pistas: _separar → transcribir_
(ruta rock: Demucs + Basic Pitch por stem) frente a _transcribir la mezcla_ (Basic Pitch + asignación
por registro), con F1 por instrumento y F1 multi-instrumento. Responde a la pregunta "¿separar antes
ayuda?".

---

## Referencias

- Rouard, Massa, Défossez. _Hybrid Transformers for Music Source Separation_. ICASSP 2023.
- Défossez. _Hybrid Spectrogram and Waveform Source Separation_. ISMIR MDX Workshop 2021.
- Bittner et al. _A Lightweight Instrument-Agnostic Model for Polyphonic Note Transcription and
  Multipitch Estimation_. ICASSP 2022.
- Krumhansl. _Cognitive Foundations of Musical Pitch_. Oxford University Press, 1990.
- Ellis. _Beat Tracking by Dynamic Programming_. Journal of New Music Research, 2007.
- Fitzgerald. _Harmonic/Percussive Separation Using Median Filtering_. DAFx 2010.
- Gardner et al. _MT3: Multi-Task Multitrack Music Transcription_. ICLR 2022 (definición de la F1
  multi-instrumento).
- Raffel et al. _mir_eval: A Transparent Implementation of Common MIR Metrics_. ISMIR 2014.
