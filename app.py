"""
Bar Path Tracker + VBT (Velocity-Based Training) - Web App prototipo

Due modalita':
1. "Solo Bar Path (Analisi visiva)": traccia e disegna la traiettoria reale
   del bilanciere (object tracking CSRT), esattamente come nella versione
   precedente. Nessun calcolo fisico.
2. "VBT Avanzato (Algoritmo di Allenamento)": usa lo stesso tracciamento, ma
   in piu' calibra i pixel in metri (dal diametro del disco selezionato),
   calcola velocita' verticale, potenza istantanea, rileva le ripetizioni,
   stima l'1RM del giorno e da' un feedback sulla fatica (velocity loss).

Note tecniche importanti:
- La LINEA disegnata sul video resta sempre quella grezza del tracker
  (nessuno smoothing), cosi' il percorso visivo rappresenta esattamente il
  movimento rilevato, come richiesto in precedenza.
- Per i CALCOLI di velocita'/potenza (non per il disegno) applichiamo invece
  un leggero smoothing sulla posizione verticale: differenziare pixel grezzi
  fotogramma-per-fotogramma e' troppo rumoroso per stimare velocita' e
  accelerazione in modo utilizzabile. Questo smoothing riguarda SOLO i numeri
  della dashboard, non la linea disegnata sul video.
- Le formule di stima %1RM per Squat e Stacco da terra sono valori INDICATIVI
  (non una fonte scientifica specifica validata): solo la formula per la
  Panca Piana (121.1 - 74.7*v) e' un modello diffuso in letteratura VBT.
  Vedi commenti su EXERCISE_PROFILES piu' sotto.

Stack: Streamlit + OpenCV (object tracking) + streamlit-image-coordinates
Compatibile con Python 3.14.
"""

import os
import time
import base64
import hashlib
import tempfile

import cv2
import streamlit as st
from streamlit_image_coordinates import streamlit_image_coordinates
import imageio

# ----------------------------------------------------------------------------
# ASSET DEL BRAND
# ----------------------------------------------------------------------------
ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
LOGO_PATH = os.path.join(ASSETS_DIR, "pragma_wordmark.png")


def _load_logo_b64():
    try:
        with open(LOGO_PATH, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except OSError:
        return None


_LOGO_B64 = _load_logo_b64()

# ----------------------------------------------------------------------------
# CONFIGURAZIONE PAGINA
# ----------------------------------------------------------------------------
try:
    from PIL import Image
    _page_icon = Image.open(LOGO_PATH.replace("pragma_wordmark", "pragma_logo"))
except Exception:
    _page_icon = "⚡"

st.set_page_config(
    page_title="PRAGMA FIT",
    page_icon=_page_icon,
    layout="centered",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# SISTEMA DI DESIGN — PRAGMA FIT
#
# Palette (ricavata dal logo, nero e bianco puri, con un unico accento):
#   --pragma-black   #000000  sfondo pagina (identico al fondo del logo)
#   --pragma-ink     #0D0D0F  superfici leggermente sollevate (bordi, celle)
#   --pragma-line    rgba(255,255,255,.09)  linee sottili di separazione
#   --pragma-white   #FFFFFF  testo primario, wordmark
#   --pragma-mist    #8A8A90  testo secondario, didascalie
#   --pragma-signal  #FF4433  UNICO accento — è anche il colore di default
#                     della linea di tracciamento: il brand e la funzione
#                     dell'app condividono lo stesso colore.
#
# Tipografia:
#   Space Grotesk  — eyebrow/step label, maiuscolo, tracciato largo (echeggia
#                    le maiuscole geometriche del logo)
#   Inter          — testo di interfaccia, didascalie, corpo
#   IBM Plex Mono  — TUTTI i numeri dell'app (kg, cm, px, m/s, W, %). È la
#                    firma visiva del prodotto: ogni misura si legge come su
#                    uno strumento di precisione, coerente con l'idea di
#                    "PRAGMA" e con la natura data-driven del VBT.
# ----------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;700&family=Inter:wght@400;500;600&family=IBM+Plex+Mono:wght@500;600&display=swap');

    :root {
        --pragma-black: #000000;
        --pragma-ink: #0D0D0F;
        --pragma-line: rgba(255,255,255,0.09);
        --pragma-white: #FFFFFF;
        --pragma-mist: #8A8A90;
        --pragma-signal: #FF4433;
    }

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    .stApp {
        background: var(--pragma-black);
    }

    .block-container {
        padding-top: 1.6rem;
        padding-bottom: 4rem;
        max-width: 720px;
    }

    /* ---------- Lockup di apertura ---------- */
    .pragma-hero {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 0.35rem;
        margin-bottom: 0.6rem;
        text-align: center;
    }
    .pragma-hero img {
        height: 40px;
        width: auto;
        display: block;
    }
    .pragma-hero .pragma-fit-tag {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.45em;
        color: var(--pragma-signal);
        text-transform: uppercase;
        margin-left: 0.45em; /* compensa il letter-spacing per centratura ottica */
    }
    .pragma-subtitle {
        font-family: 'Inter', sans-serif;
        font-weight: 400;
        font-size: 0.95rem;
        color: var(--pragma-mist);
        text-align: center;
        max-width: 34rem;
        margin: 0.4rem auto 2rem auto;
        line-height: 1.5;
    }

    /* ---------- Eyebrow di sezione (step) ---------- */
    .pragma-step {
        display: flex;
        align-items: baseline;
        gap: 0.6rem;
        margin: 2.4rem 0 0.9rem 0;
        padding-bottom: 0.7rem;
        border-bottom: 1px solid var(--pragma-line);
    }
    .pragma-step .idx {
        font-family: 'IBM Plex Mono', monospace;
        font-weight: 600;
        font-size: 0.85rem;
        color: var(--pragma-signal);
    }
    .pragma-step .label {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        font-size: 0.85rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--pragma-white);
    }
    .pragma-step .sub {
        font-family: 'Inter', sans-serif;
        font-size: 0.82rem;
        color: var(--pragma-mist);
        margin-left: auto;
        text-align: right;
    }

    /* ---------- Micro eyebrow (dentro la dashboard) ---------- */
    .pragma-micro {
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        font-size: 0.72rem;
        letter-spacing: 0.14em;
        text-transform: uppercase;
        color: var(--pragma-mist);
        margin: 1.8rem 0 0.8rem 0;
    }
    .pragma-micro span { color: var(--pragma-signal); }

    /* ---------- Badge di stato ---------- */
    .status-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.3rem 0.75rem;
        border-radius: 999px;
        font-family: 'Space Grotesk', sans-serif;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        background: rgba(255,68,51,0.10);
        color: var(--pragma-signal);
        border: 1px solid rgba(255,68,51,0.25);
    }

    /* ---------- File uploader ---------- */
    [data-testid="stFileUploaderDropzone"] {
        border: 1px dashed var(--pragma-line);
        border-radius: 4px;
        background: var(--pragma-ink);
    }
    [data-testid="stFileUploaderDropzone"]:hover {
        border-color: var(--pragma-signal);
    }

    /* ---------- Bottoni ---------- */
    .stButton > button {
        border-radius: 4px;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        font-size: 0.82rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        padding: 0.8rem 1.2rem;
        transition: opacity 0.15s ease-in-out, transform 0.15s ease-in-out;
        border: 1px solid var(--pragma-line);
    }
    .stButton > button[kind="primary"] {
        background: var(--pragma-signal);
        border: 1px solid var(--pragma-signal);
        color: var(--pragma-black);
    }
    .stButton > button:hover {
        opacity: 0.88;
        transform: translateY(-1px);
    }
    .stDownloadButton > button {
        border-radius: 4px;
        font-family: 'Space Grotesk', sans-serif;
        font-weight: 700;
        font-size: 0.82rem;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }

    /* ---------- Metriche (pannello strumenti) ---------- */
    [data-testid="stMetric"] {
        background: var(--pragma-ink);
        border: 1px solid var(--pragma-line);
        border-radius: 4px;
        padding: 1rem 1.1rem;
    }
    [data-testid="stMetricLabel"] {
        font-family: 'Space Grotesk', sans-serif !important;
        font-size: 0.68rem !important;
        letter-spacing: 0.1em;
        text-transform: uppercase;
        color: var(--pragma-mist) !important;
    }
    [data-testid="stMetricValue"] {
        font-family: 'IBM Plex Mono', monospace !important;
        font-weight: 600 !important;
        color: var(--pragma-white) !important;
    }

    /* ---------- Caption e testo secondario ---------- */
    [data-testid="stCaptionContainer"], .stCaption {
        color: var(--pragma-mist) !important;
    }

    /* ---------- Numeri in stile strumento (usati via markdown) ---------- */
    .pragma-mono {
        font-family: 'IBM Plex Mono', monospace;
    }

    /* ---------- Footer ---------- */
    .pragma-footer {
        margin-top: 3rem;
        padding-top: 1.2rem;
        border-top: 1px solid var(--pragma-line);
        font-family: 'Inter', sans-serif;
        font-size: 0.78rem;
        color: var(--pragma-mist);
        text-align: center;
        line-height: 1.6;
    }

    @media (max-width: 600px) {
        .block-container {
            padding-left: 1rem;
            padding-right: 1rem;
        }
        .pragma-step .sub {
            display: none;
        }
    }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


_STEP_COUNTER = {"n": 0}


def step_header(label: str, sub: str = "", index: str = None):
    """Eyebrow tipografico per una sezione del flusso (sostituisce st.subheader).

    Senza 'index' esplicito, il numero di step si auto-incrementa: questo
    tiene la numerazione sempre corretta anche quando uno step (es. i
    parametri VBT) compare solo in una delle due modalità.
    """
    if index is None:
        idx_str = f"{_STEP_COUNTER['n']:02d}"
        _STEP_COUNTER["n"] += 1
    else:
        idx_str = index
    sub_html = f'<span class="sub">{sub}</span>' if sub else ""
    st.markdown(
        f'<div class="pragma-step">'
        f'<span class="idx">{idx_str}</span>'
        f'<span class="label">{label}</span>'
        f'{sub_html}'
        f'</div>',
        unsafe_allow_html=True,
    )


def micro_header(label: str):
    """Micro-eyebrow per sotto-sezioni (es. dentro la dashboard VBT)."""
    st.markdown(f'<div class="pragma-micro">{label}</div>', unsafe_allow_html=True)


# ---------- Hero: logo PRAGMA (immagine reale) + lockup "FIT" ----------
if _LOGO_B64:
    st.markdown(
        f'<div class="pragma-hero">'
        f'<img src="data:image/png;base64,{_LOGO_B64}" alt="PRAGMA" />'
        f'<span class="pragma-fit-tag">FIT</span>'
        f'</div>',
        unsafe_allow_html=True,
    )
else:
    st.markdown('<div class="pragma-hero"><span class="pragma-fit-tag">PRAGMA FIT</span></div>', unsafe_allow_html=True)

st.markdown(
    '<p class="pragma-subtitle">Traccia il bilanciere e calcola velocità, potenza e stima '
    'dell\'1RM del giorno con l\'algoritmo VBT.</p>',
    unsafe_allow_html=True,
)

# ----------------------------------------------------------------------------
# COSTANTI VBT
# ----------------------------------------------------------------------------
GRAVITY = 9.81  # m/s^2

# Soglie per la classificazione di fase (su/giu'/fermo) usate per il conteggio
# ripetizioni e per isolare i campioni "concentrici" (fase di salita).
V_THRESHOLD = 0.03          # m/s: sotto questa soglia il movimento e' considerato rumore
MIN_REP_DISPLACEMENT_M = 0.05  # una "salita" deve spostare almeno 5 cm per contare come rep
MIN_REP_SAMPLES = 4         # una "salita" deve durare almeno N campioni per contare come rep
                             # (evita che 2-3 fotogrammi rumorosi vengano letti come una rep
                             # con velocita' istantanea assurda)
SMOOTH_WINDOW = 7           # finestra di media mobile sulla posizione, solo per i calcoli fisici
VELOCITY_SMOOTH_WINDOW = 3  # ulteriore, leggero smoothing sulla serie di velocita' stessa

# Profili carico-velocita' per la stima dell'1RM: %1RM = a - b * v_media_rep_piu_veloce
# ATTENZIONE: solo il profilo "Panca Piana" corrisponde a un modello diffuso in
# letteratura VBT. I profili di Squat e Stacco da terra qui sotto sono valori
# INDICATIVI/APPROSSIMATI (non una citazione scientifica specifica): usali solo
# come riferimento di massima, non come dato clinico validato.
EXERCISE_PROFILES = {
    "Panca Piana": {"a": 121.1, "b": 74.7},
    "Squat": {"a": 116.0, "b": 63.5},          # indicativo
    "Stacco da terra": {"a": 110.0, "b": 72.0},  # indicativo
}

# --- Affidabilita' della stima 1RM da velocita' -----------------------------
# Il modello carico-velocita' (%1RM = a - b*v) e' calibrato per SERIE BREVI
# (1-3 ripetizioni) eseguite alla massima velocita' intenzionale con un carico
# davvero impegnativo. Fuori da queste condizioni la stima puo' diventare
# assurda: un colpo "veloce" dentro una serie lunga o sub-massimale (es. 100kg
# per 8 ripetizioni) puo' avere una velocita' che il modello legge come "carico
# leggerissimo", producendo un 1RM gonfiato (es. 500kg da un colpo a 100kg).
#
# Soluzione applicata (due livelli di protezione):
# 1. Il pavimento del clamp su %1RM e' alzato al 30% (prima era 20%): sotto
#    questa soglia il modello e' considerato fuori dal proprio range valido.
# 2. Quando la serie ha piu' di REPS_MAX_FOR_RELIABLE_VBT ripetizioni, oppure
#    quando il %1RM non-clampato cade sotto la soglia, la stima da velocita'
#    viene affiancata (non sostituita silenziosamente) da una stima classica
#    basata sul numero di ripetizioni (formula di Epley), con un avviso
#    esplicito su quale numero fidarsi di piu' e perche'.
PCT_1RM_FLOOR = 30.0
REPS_MAX_FOR_RELIABLE_VBT = 3


with st.expander("Come funziona", expanded=False):
    st.markdown(
        """
        1. Scegli la modalità qui sotto.
        2. **Se sei in modalità VBT**, indica esercizio, peso sul bilanciere
           e diametro del disco: servono per calcolare velocità, potenza e
           1RM stimato.
        3. **Carica** un video (bilanciere già visibile nel primo fotogramma).
        4. **Clicca** su un punto ad alto contrasto del bilanciere (bordo di
           un disco, adesivo, anello) e regola l'area da seguire — in
           modalità VBT quest'area viene usata anche per calibrare la
           conversione pixel → metri, quindi conviene farla combaciare con
           l'altezza del disco.
        5. Premi **Analizza set**. Il tracciamento (CSRT) segue il punto in
           ogni fotogramma; in modalità VBT ottieni anche velocità, potenza,
           ripetizioni, 1RM stimato e un feedback sulla fatica.

        💡 **Per una stima 1RM precisa**: la stima basata sulla velocità è
        pensata per serie brevi (1-3 ripetizioni) eseguite alla massima
        velocità possibile con un carico impegnativo — è così che funzionano
        tutti i dispositivi VBT commerciali. Su serie più lunghe o
        sub-massimali, l'app affianca automaticamente una stima classica
        basata sul numero di ripetizioni, più affidabile in quel caso.

        *Le stime VBT si basano su un tracciamento video 2D con una
        telecamera non calibrata: sono utili per il trend e per un feedback
        di massima, non sostituiscono un encoder lineare o un dispositivo VBT
        certificato.*
        """
    )

# ----------------------------------------------------------------------------
# 0) SELEZIONE MODALITÀ
# ----------------------------------------------------------------------------
step_header("Modalità")
mode = st.radio(
    "Modalità",
    ["Solo Bar Path (Analisi visiva)", "VBT Avanzato (Algoritmo di Allenamento)"],
    horizontal=True,
    label_visibility="collapsed",
)
vbt_mode = mode.startswith("VBT")

# ----------------------------------------------------------------------------
# 1) PARAMETRI DELLA SERIE (solo modalità VBT)
#
# Questi tre valori sono chiesti qui, nel flusso principale della pagina, e
# non in sidebar: sul telefono la sidebar parte chiusa e passa facilmente
# inosservata, mentre peso, esercizio e diametro sono indispensabili per
# calcolare velocità/potenza/1RM, quindi l'app li chiede esplicitamente
# prima di procedere.
# ----------------------------------------------------------------------------
exercise = None
peso_kg = None
diametro_cm = None

if vbt_mode:
    step_header("Parametri della serie")
    st.caption("Servono per calibrare pixel → metri e calcolare velocità, potenza e 1RM stimato.")

    exercise = st.radio(
        "Esercizio",
        list(EXERCISE_PROFILES.keys()),
        horizontal=True,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        peso_kg = st.number_input(
            "Peso sul bilanciere (kg)", min_value=1.0, value=20.0, step=1.0,
            help="Il carico totale sul bilanciere per questa serie (bilanciere + dischi).",
        )
    with col_b:
        diametro_cm = st.number_input(
            "Diametro del disco (cm)", min_value=5.0, value=45.0, step=0.5,
            help="45 cm è lo standard olimpico. Usato per convertire i pixel in metri.",
        )

# ----------------------------------------------------------------------------
# SIDEBAR - solo aspetto grafico (non blocca il flusso su mobile)
# ----------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div class="pragma-step" style="margin-top:0;">'
        '<span class="idx">//</span><span class="label">Aspetto</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    line_color_hex = st.color_picker("Colore linea", "#FF4433")
    line_thickness = st.slider("Spessore linea", min_value=2, max_value=12, value=4)

    st.markdown(
        '<div class="pragma-footer" style="text-align:left; margin-top:2rem;">PRAGMA FIT · Streamlit · OpenCV</div>',
        unsafe_allow_html=True,
    )

LINE_COLOR_BGR = None


def hex_to_bgr(hex_color: str):
    hex_color = hex_color.lstrip("#")
    r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return (b, g, r)


LINE_COLOR_BGR = hex_to_bgr(line_color_hex)


# ----------------------------------------------------------------------------
# UTILS DI TRACCIAMENTO (invariati rispetto alla versione Bar Path)
# ----------------------------------------------------------------------------
def create_tracker():
    """Crea un tracker CSRT, gestendo le diverse posizioni dell'API in OpenCV."""
    creators = []
    if hasattr(cv2, "TrackerCSRT_create"):
        creators.append(cv2.TrackerCSRT_create)
    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerCSRT_create"):
        creators.append(cv2.legacy.TrackerCSRT_create)
    last_err = None
    for creator in creators:
        try:
            return creator()
        except Exception as e:  # pragma: no cover
            last_err = e
    raise RuntimeError(
        "Impossibile creare il tracker CSRT. Verifica di avere installato "
        f"'opencv-contrib-python-headless' (errore: {last_err})."
    )


def clamp_bbox(x, y, w, h, frame_w, frame_h):
    x = max(0, min(x, frame_w - 1))
    y = max(0, min(y, frame_h - 1))
    w = max(4, min(w, frame_w - x))
    h = max(4, min(h, frame_h - y))
    return int(x), int(y), int(w), int(h)


def file_signature(uploaded_file) -> str:
    return hashlib.md5(
        f"{uploaded_file.name}-{uploaded_file.size}".encode("utf-8")
    ).hexdigest()


@st.cache_data(show_spinner=False)
def extract_first_frame(video_bytes: bytes, _sig: str):
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tmp.write(video_bytes)
    tmp.flush()
    tmp.close()
    cap = cv2.VideoCapture(tmp.name)
    ok, frame = cap.read()
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 0
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    os.remove(tmp.name)
    if not ok:
        return None, fps, total_frames, width, height
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return rgb_frame, fps, total_frames, width, height


# ----------------------------------------------------------------------------
# MOTORE DI CALCOLO VBT (velocità, potenza, ripetizioni, 1RM, feedback)
# ----------------------------------------------------------------------------
def smooth_series(values, window):
    """Media mobile centrata semplice, usata solo per i calcoli fisici."""
    n = len(values)
    if n == 0:
        return []
    half = window // 2
    smoothed = []
    for i in range(n):
        lo = max(0, i - half)
        hi = min(n, i + half + 1)
        chunk = values[lo:hi]
        smoothed.append(sum(chunk) / len(chunk))
    return smoothed


def compute_vbt_metrics(raw_series, fps, mpp, weight_kg):
    """
    Calcola velocita', potenza, fasi (su/giu') e ripetizioni a partire dalla
    serie di centri tracciati.

    raw_series: lista di tuple (frame_idx, x_px, y_px) SOLO per i fotogrammi
                in cui il tracciamento e' riuscito (i fotogrammi persi vengono
                semplicemente saltati nel calcolo del delta tempo/spazio).
    fps: fotogrammi al secondo del video.
    mpp: metri per pixel (fattore di calibrazione).
    weight_kg: peso sul bilanciere (kg), usato per calcolare Forza e Potenza.

    Ritorna un dizionario con le metriche aggregate e la lista delle
    ripetizioni rilevate (ognuna con velocita' media/di picco).
    """
    if len(raw_series) < 3:
        return None

    frame_idxs = [p[0] for p in raw_series]
    y_positions = [p[2] for p in raw_series]

    # Smoothing SOLO per i calcoli fisici (non per la linea disegnata sul video)
    y_smooth = smooth_series(y_positions, SMOOTH_WINDOW)

    # --- Velocita' istantanea (asse verticale) ---
    # Convenzione: positiva = verso l'alto (fase concentrica per gli esercizi
    # supportati), perche' in pixel-immagine y decresce salendo.
    velocities = [0.0]  # nessuna velocita' definita per il primissimo campione
    for i in range(1, len(y_smooth)):
        dt = (frame_idxs[i] - frame_idxs[i - 1]) / fps
        if dt <= 0:
            velocities.append(velocities[-1])
            continue
        dy_px = y_smooth[i - 1] - y_smooth[i]  # positivo se sale
        dy_m = dy_px * mpp
        v = dy_m / dt
        velocities.append(v)

    # Smoothing leggero anche sulla velocita' stessa: lo smoothing sulla sola
    # posizione non basta a eliminare gli "spike" della derivata quando il
    # tracciamento oscilla di 1-2 pixel tra due fotogrammi consecutivi. Senza
    # questo passaggio, un singolo colpo rumoroso puo' risultare con una
    # velocita' istantanea assurda e falsare la stima dell'1RM (era la causa
    # principale del bug "500kg da un colpo a 100kg").
    velocities = smooth_series(velocities, VELOCITY_SMOOTH_WINDOW)

    # --- Accelerazione e potenza istantanea ---
    # Forza = m * (g + a); Potenza = Forza * velocita'
    accelerations = [0.0]
    for i in range(1, len(velocities)):
        dt = (frame_idxs[i] - frame_idxs[i - 1]) / fps
        if dt <= 0:
            accelerations.append(0.0)
            continue
        a = (velocities[i] - velocities[i - 1]) / dt
        accelerations.append(a)

    # --- Classificazione fase (su / giu' / fermo) con debounce anti-rumore ---
    debounce_frames = max(2, round(fps * 0.10))  # ~100ms di persistenza minima

    direction_raw = []
    for v in velocities:
        if v > V_THRESHOLD:
            direction_raw.append("up")
        elif v < -V_THRESHOLD:
            direction_raw.append("down")
        else:
            direction_raw.append("still")

    confirmed_phase = []
    if direction_raw:
        run_dir = direction_raw[0]
        run_len = 0
        current_phase = run_dir
        for d in direction_raw:
            if d == run_dir:
                run_len += 1
            else:
                run_dir = d
                run_len = 1
            if run_len >= debounce_frames:
                current_phase = run_dir
            confirmed_phase.append(current_phase)

    # --- Segmentazione delle ripetizioni (ogni tratto continuo "up") ---
    reps = []
    i = 0
    n = len(confirmed_phase)
    while i < n:
        if confirmed_phase[i] == "up":
            start = i
            while i < n and confirmed_phase[i] == "up":
                i += 1
            end = i - 1
            seg_velocities = velocities[start:end + 1]
            seg_displacement_m = sum(
                (y_smooth[k] - y_smooth[k + 1]) * mpp
                for k in range(start, end)
                if k + 1 <= end
            )
            # Filtra micro-oscillazioni classificate come "salita" per errore:
            # sia per spostamento minimo, sia per durata minima (un segmento
            # troppo corto, anche se supera i 5cm, e' spesso solo rumore di
            # tracciamento con velocita' istantanea non realistica).
            if (
                abs(seg_displacement_m) >= MIN_REP_DISPLACEMENT_M
                and len(seg_velocities) >= MIN_REP_SAMPLES
            ):
                reps.append({
                    "start_idx": start,
                    "end_idx": end,
                    "mean_v": sum(seg_velocities) / len(seg_velocities),
                    "peak_v": max(seg_velocities),
                })
        else:
            i += 1

    # --- Metriche aggregate ---
    concentric_indices = [idx for idx, ph in enumerate(confirmed_phase) if ph == "up"]
    concentric_velocities = [velocities[idx] for idx in concentric_indices]
    concentric_power = [
        weight_kg * (GRAVITY + accelerations[idx]) * velocities[idx]
        for idx in concentric_indices
    ] if concentric_indices else []

    mean_concentric_velocity = (
        sum(concentric_velocities) / len(concentric_velocities) if concentric_velocities else 0.0
    )
    peak_velocity = max(concentric_velocities) if concentric_velocities else 0.0
    peak_power = max(concentric_power) if concentric_power else 0.0

    return {
        "reps": reps,
        "mean_concentric_velocity": mean_concentric_velocity,
        "peak_velocity": peak_velocity,
        "peak_power": peak_power,
        "reps_count": len(reps),
    }


def estimate_1rm_velocity(exercise_name, fastest_rep_velocity, weight_kg):
    """
    Stima l'1RM dal profilo carico-velocita' dell'esercizio, usando la
    velocita' media della SINGOLA ripetizione piu' veloce della serie (mai
    una media su tutte le ripetizioni: mediare i colpi di una serie lunga
    con quelli di una serie esplosiva breve produrrebbe una velocita' non
    rappresentativa di nessuno dei due scenari).

    Ritorna (1RM stimato, %1RM usato, affidabile:bool). 'affidabile' e' False
    quando il %1RM non-clampato cade sotto PCT_1RM_FLOOR: significa che la
    velocita' misurata e' fuori dal range su cui il modello lineare ha senso
    (tipicamente perche' il colpo piu' veloce viene da una serie lunga o
    sub-massimale, non da un vero tentativo a carico impegnativo).
    """
    profile = EXERCISE_PROFILES[exercise_name]
    pct_1rm_raw = profile["a"] - profile["b"] * fastest_rep_velocity
    affidabile = pct_1rm_raw >= PCT_1RM_FLOOR
    pct_1rm_clamped = max(PCT_1RM_FLOOR, min(100.0, pct_1rm_raw))
    estimated_1rm = weight_kg / (pct_1rm_clamped / 100.0)
    return estimated_1rm, pct_1rm_clamped, affidabile


def estimate_1rm_from_reps(weight_kg, reps_count):
    """
    Stima di riserva basata sul numero di ripetizioni (formula di Epley),
    utile come riferimento incrociato quando la serie non e' adatta alla
    stima da velocita' (troppo lunga per essere stata un tentativo massimale
    a velocita' intenzionale). Presuppone la serie svolta vicino al cedimento:
    e' anch'essa una stima, non un dato certo.
    """
    reps_count = max(1, reps_count)
    return weight_kg * (1 + reps_count / 30.0)


def velocity_loss_feedback(vl_pct):
    """Restituisce (tipo_box, messaggio) in base alla perdita di velocita'."""
    if vl_pct < 10:
        return "success", (
            "Fatica minima. Ottimo per stimolare la forza esplosiva o se hai "
            "altre serie da fare. Puoi aumentare leggermente il carico."
        )
    elif vl_pct <= 20:
        return "info", (
            "Zona ideale per l'ipertrofia e la forza neurale. Ottimo stimolo "
            "allenante, mantieni questo peso."
        )
    elif vl_pct <= 30:
        return "warning", (
            "Fatica moderata-alta. Sei in una zona di transizione: valuta se "
            "ridurre leggermente il carico nelle prossime serie."
        )
    else:
        return "warning", (
            "Fatica eccessiva rilevata! Stai sporcando il movimento o sei "
            "vicino al cedimento totale. Riduci il carico del 5-10% nella "
            "prossima serie o fermati qui."
        )


# ----------------------------------------------------------------------------
# 1) UPLOAD VIDEO
# ----------------------------------------------------------------------------
step_header("Carica il video")
uploaded_file = st.file_uploader(
    "Trascina qui il tuo video o caricalo dal rullino",
    type=["mp4", "mov", "avi", "mkv", "m4v"],
    accept_multiple_files=False,
    label_visibility="collapsed",
)

if uploaded_file is None:
    st.info("Carica un video per iniziare.")
    st.stop()

st.markdown('<span class="status-badge">● Video caricato</span>', unsafe_allow_html=True)

sig = file_signature(uploaded_file)

if st.session_state.get("video_sig") != sig:
    st.session_state["video_sig"] = sig
    st.session_state["selected_point"] = None

video_bytes = uploaded_file.getvalue()
first_frame, fps, total_frames, width, height = extract_first_frame(video_bytes, sig)

if fps <= 1 or fps > 240:
    fps = 30

if first_frame is None:
    st.error("❌ Impossibile leggere il primo fotogramma del video. Prova con un altro file (mp4 consigliato).")
    st.stop()

# ----------------------------------------------------------------------------
# 2) SELEZIONE DEL PUNTO DI PARTENZA SUL PRIMO FOTOGRAMMA
# ----------------------------------------------------------------------------
step_header("Clicca sul bilanciere")
if vbt_mode:
    st.caption(
        "In modalità VBT, l'area selezionata viene usata anche per "
        "calibrare la conversione pixel → metri: falla combaciare con "
        "l'altezza (il diametro) del disco."
    )

default_box = max(20, min(width, height) // 12)
box_size = st.slider(
    "Dimensione dell'area da seguire (px)",
    min_value=15,
    max_value=max(40, min(width, height) // 2),
    value=default_box,
    step=1,
    help="Deve coprire un dettaglio ad alto contrasto del bilanciere (bordo, "
         "adesivo, anello). Troppo piccola = facile perdere il tracciamento; "
         "troppo grande = puo' agganciare lo sfondo.",
)

display_width = min(700, width)
scale = width / display_width
display_height = int(height / scale)

preview = first_frame.copy()
selected_point = st.session_state.get("selected_point")
if selected_point is not None:
    px, py = selected_point
    half = box_size // 2
    x, y, w, h = clamp_bbox(px - half, py - half, box_size, box_size, width, height)
    # Colore accento PRAGMA (#FF4433) in BGR (OpenCV usa l'ordine B,G,R)
    accent_bgr = (51, 68, 255)
    cv2.rectangle(preview, (x, y), (x + w, y + h), accent_bgr, max(2, width // 400))
    cv2.circle(preview, (px, py), max(4, width // 250), accent_bgr, -1)

preview_small = cv2.resize(preview, (display_width, display_height), interpolation=cv2.INTER_AREA)

click_value = streamlit_image_coordinates(preview_small, key=f"point_selector_{sig}")

if click_value is not None:
    disp_w = click_value.get("width") or display_width
    disp_h = click_value.get("height") or display_height
    real_x = int(click_value["x"] * (width / disp_w))
    real_y = int(click_value["y"] * (height / disp_h))
    real_x = max(0, min(real_x, width - 1))
    real_y = max(0, min(real_y, height - 1))
    if st.session_state.get("selected_point") != (real_x, real_y):
        st.session_state["selected_point"] = (real_x, real_y)
        st.rerun()

if selected_point is None:
    st.warning("Clicca su un punto del bilanciere nell'immagine qui sopra prima di procedere.")
else:
    st.caption(f"Punto selezionato — x: {selected_point[0]}px · y: {selected_point[1]}px")

# ----------------------------------------------------------------------------
# 3) ELABORAZIONE
# ----------------------------------------------------------------------------
step_header("Analizza set")
process_clicked = st.button(
    "Analizza set",
    use_container_width=True,
    type="primary",
    disabled=selected_point is None,
)

if process_clicked and selected_point is not None:
    input_suffix = os.path.splitext(uploaded_file.name)[1] or ".mp4"
    input_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=input_suffix)
    input_tmp.write(video_bytes)
    input_tmp.flush()
    input_path = input_tmp.name
    input_tmp.close()

    output_path = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4").name

    status_text = st.empty()
    progress_bar = st.progress(0, text="Inizializzazione...")

    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        st.error("❌ Impossibile leggere il video. Prova con un altro file o formato (mp4 consigliato).")
        st.stop()

    ret, frame = cap.read()
    if not ret:
        st.error("❌ Impossibile leggere il primo fotogramma per inizializzare il tracciamento.")
        cap.release()
        st.stop()

    px, py = selected_point
    half = box_size // 2
    init_bbox = clamp_bbox(px - half, py - half, box_size, box_size, width, height)

    # Fattore di calibrazione pixel -> metri (solo modalita' VBT):
    # usiamo l'altezza della bounding box iniziale come riferimento del
    # diametro del disco. metri_per_pixel = (diametro_cm/100) / altezza_px
    mpp = None
    if vbt_mode:
        bbox_height_px = init_bbox[3]
        mpp = (diametro_cm / 100.0) / bbox_height_px

    try:
        tracker = create_tracker()
        tracker.init(frame, init_bbox)
    except Exception as e:
        st.error(f"❌ Errore nell'inizializzazione del tracciamento: {e}")
        cap.release()
        st.stop()

    writer = imageio.get_writer(
        output_path,
        fps=fps,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
    )

    trajectory_points = []
    raw_series = []  # (frame_idx, x_px, y_px) per i soli frame trovati (usato solo in VBT)
    lost_frames = 0
    frame_idx = 0
    start_time = time.time()
    last_center = (int(px), int(py))

    while True:
        if frame_idx > 0:
            ret, frame = cap.read()
            if not ret:
                break
        frame_idx += 1

        if frame_idx == 1:
            x, y, w, h = init_bbox
            success = True
        else:
            success, bbox = tracker.update(frame)
            if success:
                x, y, w, h = bbox

        if success:
            center = (int(x + w / 2), int(y + h / 2))
            last_center = center
            trajectory_points.append(center)
            if vbt_mode:
                raw_series.append((frame_idx, center[0], center[1]))
        else:
            lost_frames += 1
            # Nessun punto fittizio: il percorso disegnato resta quello reale
            # fin dove il tracciamento e' riuscito.

        if len(trajectory_points) > 1:
            for i in range(1, len(trajectory_points)):
                cv2.line(
                    frame,
                    trajectory_points[i - 1],
                    trajectory_points[i],
                    LINE_COLOR_BGR,
                    line_thickness,
                    lineType=cv2.LINE_AA,
                )

        marker_color = LINE_COLOR_BGR if success else (128, 128, 128)
        cv2.circle(frame, last_center, line_thickness + 2, marker_color, -1, lineType=cv2.LINE_AA)
        cv2.circle(frame, last_center, line_thickness + 4, (255, 255, 255), 2, lineType=cv2.LINE_AA)

        frame_rgb_out = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        writer.append_data(frame_rgb_out)

        progress = min(frame_idx / max(total_frames, 1), 1.0)
        elapsed = time.time() - start_time
        progress_bar.progress(
            progress,
            text=f"Elaborazione fotogramma {frame_idx}/{total_frames or '?'} "
                 f"({progress*100:.0f}%) · {elapsed:.0f}s",
        )

    cap.release()
    writer.close()

    progress_bar.progress(1.0, text="✅ Elaborazione completata!")

    if lost_frames == 0:
        status_text.success(
            f"Video elaborato in {time.time() - start_time:.1f}s — "
            f"{frame_idx} fotogrammi, tracciamento riuscito su tutto il video."
        )
    else:
        loss_pct = 100 * lost_frames / max(frame_idx, 1)
        status_text.warning(
            f"Video elaborato in {time.time() - start_time:.1f}s. "
            f"Tracciamento perso per {lost_frames} fotogrammi su {frame_idx} "
            f"({loss_pct:.0f}%) — probabilmente il punto scelto è uscito dall'inquadratura "
            f"o è stato oscurato. Prova a scegliere un punto più ad alto contrasto o "
            f"un'area leggermente più grande."
        )

    step_header("Risultato", index="→")
    st.video(output_path)

    with open(output_path, "rb") as f:
        video_out_bytes = f.read()

    st.download_button(
        label="Scarica il video elaborato",
        data=video_out_bytes,
        file_name="pragma_fit_output.mp4",
        mime="video/mp4",
        use_container_width=True,
    )

    # ------------------------------------------------------------------
    # DASHBOARD VBT (solo in modalita' "VBT Avanzato")
    # ------------------------------------------------------------------
    if vbt_mode:
        metrics = compute_vbt_metrics(raw_series, fps, mpp, peso_kg)

        step_header("Dashboard VBT", index="→")

        if metrics is None or metrics["reps_count"] == 0:
            st.warning(
                "Non è stato rilevato un movimento verticale sufficiente per "
                "calcolare le metriche VBT. Verifica che il punto tracciato "
                "segua effettivamente il bilanciere durante la salita."
            )
        else:
            col1, col2 = st.columns(2)
            col1.metric("Velocità media in salita", f"{metrics['mean_concentric_velocity']:.2f} m/s")
            col2.metric("Velocità di picco", f"{metrics['peak_velocity']:.2f} m/s")

            col3, col4 = st.columns(2)
            col3.metric("Potenza di picco", f"{metrics['peak_power']:.0f} W")
            col4.metric("Ripetizioni rilevate", f"{metrics['reps_count']}")

            # --- Stima 1RM di oggi (doppio metodo, vedi costanti VBT sopra) ---
            fastest_rep = max(metrics["reps"], key=lambda r: r["mean_v"])
            vbt_1rm, pct_used, vbt_affidabile = estimate_1rm_velocity(
                exercise, fastest_rep["mean_v"], peso_kg
            )
            reps_1rm = estimate_1rm_from_reps(peso_kg, metrics["reps_count"])

            # La stima da velocita' e' affidabile solo se il modello non e'
            # stato "clampato" FUORI dal suo range valido E la serie e'
            # abbastanza breve da poter essere un vero tentativo massimale.
            serie_adatta_a_vbt = metrics["reps_count"] <= REPS_MAX_FOR_RELIABLE_VBT
            stima_affidabile = vbt_affidabile and serie_adatta_a_vbt

            micro_header(f"1RM stimato oggi <span>· {exercise}</span>")

            col_v, col_r = st.columns(2)
            col_v.metric(
                "Da velocità (VBT)",
                f"{vbt_1rm:.1f} kg",
                help=f"Dalla ripetizione più veloce della serie ({fastest_rep['mean_v']:.2f} m/s), "
                     f"corrispondente a circa il {pct_used:.0f}% dell'1RM secondo il profilo "
                     f"carico-velocità di {exercise}.",
            )
            col_r.metric(
                "Da ripetizioni (rif.)",
                f"{reps_1rm:.1f} kg",
                help="Stima classica (formula di Epley) da peso e numero di ripetizioni, "
                     "assumendo la serie svolta vicino al cedimento. Utile come riferimento "
                     "incrociato, specialmente su serie lunghe.",
            )

            if stima_affidabile:
                st.caption(
                    "Serie breve a velocità elevata: la stima **da velocità** è quella "
                    "più affidabile in questo caso."
                )
            else:
                motivo = (
                    f"la serie ha {metrics['reps_count']} ripetizioni (il modello VBT è "
                    f"pensato per serie di massimo {REPS_MAX_FOR_RELIABLE_VBT})"
                    if not serie_adatta_a_vbt
                    else "la ripetizione più veloce ha una velocità fuori dal range tipico del modello"
                )
                st.warning(
                    f"⚠️ La stima **da velocità** qui sopra non è affidabile: {motivo}. "
                    f"In questo caso conviene fare riferimento alla stima **da ripetizioni** "
                    f"({reps_1rm:.1f} kg). Per una stima da velocità precisa, esegui una serie "
                    f"breve (1-3 ripetizioni) alla massima velocità possibile con un carico "
                    f"impegnativo."
                )
            st.caption(
                "Entrambe le stime sono indicative: non sostituiscono un test 1RM reale "
                "né un dato clinico validato individualmente."
            )

            # --- Feedback su Velocity Loss ---
            micro_header("Consigli automatici")
            if metrics["reps_count"] < 2:
                st.info(
                    "Rilevata una sola ripetizione: la perdita di velocità si "
                    "calcola confrontando la prima e l'ultima ripetizione di "
                    "una serie con più ripetizioni."
                )
            else:
                v_first = metrics["reps"][0]["mean_v"]
                v_last = metrics["reps"][-1]["mean_v"]
                if v_first > 0:
                    vl_pct = max(0.0, (v_first - v_last) / v_first * 100)
                    box_type, message = velocity_loss_feedback(vl_pct)
                    full_message = f"**Perdita di velocità: {vl_pct:.0f}%.** {message}"
                    if box_type == "success":
                        st.success(full_message)
                    elif box_type == "warning":
                        st.warning(full_message)
                    else:
                        st.info(full_message)
                else:
                    st.info("Non è stato possibile calcolare la perdita di velocità per questa serie.")

    try:
        os.remove(input_path)
    except OSError:
        pass

st.markdown(
    '<div class="pragma-footer">PRAGMA FIT · Prototipo — la traiettoria è calcolata tramite '
    'object tracking (CSRT) sul punto scelto dall\'utente.<br>Le metriche VBT sono stime basate '
    'su video 2D non calibrato: usale come riferimento di tendenza, non come dato clinico.</div>',
    unsafe_allow_html=True,
)
