# PRAGMA FIT

Web app prototipo con due modalità:

1. **Solo Bar Path (Analisi visiva)** — traccia e disegna la traiettoria
   reale del bilanciere, esattamente come nella versione precedente.
2. **VBT Avanzato (Algoritmo di Allenamento)** — in più calcola velocità,
   potenza, ripetizioni, stima l'1RM del giorno e dà un feedback sulla
   fatica (velocity loss), basandosi sullo stesso tracciamento.

- **Frontend + Backend**: Streamlit
- **Elaborazione video**: OpenCV
- **Tracciamento**: object tracking CSRT, inizializzato dal punto che
  l'utente clicca sul bilanciere nel primo fotogramma
- **Encoding output**: imageio + ffmpeg (H.264, compatibile con i browser)

---

## 🎨 Brand: PRAGMA FIT

L'app ha ora un'identità visiva propria, costruita attorno al logo che mi
hai fornito (`assets/pragma_logo.png`):

- **Palette**: nero puro (`#000000`, identico allo sfondo del logo) e
  bianco puro, con un unico accento — **rosso segnale `#FF4433`** — usato
  per la CTA principale e, non a caso, anche come colore di default della
  linea di tracciamento: il brand e la funzione dell'app condividono lo
  stesso colore.
- **Tipografia**: *Space Grotesk* per le etichette di sezione (maiuscolo,
  tracciato largo, in coerenza con le maiuscole geometriche del logo),
  *Inter* per il testo di interfaccia, *IBM Plex Mono* per **tutti i numeri**
  dell'app (kg, cm, px, m/s, W, %) — così ogni misura si legge come su uno
  strumento di precisione, in linea con lo spirito "pragmatico" del nome e
  con la natura data-driven del VBT.
- **Logo**: il wordmark caricato (`assets/pragma_logo.png`, ritagliato in
  `assets/pragma_wordmark.png` per un posizionamento più pulito in testata)
  è usato sia nell'header dell'app sia come favicon del browser. Il tag
  "FIT" è composto in testo (non nell'immagine originale) per formare il
  lockup completo "PRAGMA FIT".
- Tema Streamlit nativo (`.streamlit/config.toml`) impostato su dark mode
  con la stessa palette, così anche i widget non toccati dal CSS custom
  (slider, radio, ecc.) restano coerenti con il brand.

---

## 🆕 Cosa c'è di nuovo (motore VBT)

### Come funziona il calcolo
1. **Calibrazione pixel → metri**: l'altezza (in pixel) dell'area che
   selezioni sul bilanciere viene messa in rapporto con il diametro reale
   del disco (in cm) che inserisci — questo dà il fattore "metri per pixel".
2. **Velocità verticale**: ad ogni fotogramma si calcola lo spostamento
   verticale del punto tracciato, lo si converte in metri col fattore di
   calibrazione e lo si divide per il tempo trascorso tra i fotogrammi.
   *Nota tecnica*: per rendere il calcolo utilizzabile (differenziare pixel
   grezzi fotogramma-per-fotogramma è molto rumoroso), la posizione verticale
   viene leggermente smussata prima di calcolare la velocità. Questo
   riguarda **solo i numeri della dashboard**: la linea disegnata sul video
   resta quella grezza del tracker, come nella versione precedente.
3. **Fase concentrica (salita)**: i fotogrammi vengono classificati come
   salita/discesa/fermo in base alla velocità, con un piccolo "debounce"
   (persistenza minima ~100ms) per non farsi ingannare dal rumore video.
4. **Ripetizioni**: ogni tratto continuo di salita che sposta il bilanciere
   di almeno 5 cm viene contato come una ripetizione.
5. **Potenza**: Potenza = Forza × Velocità, con Forza = massa × (9.81 +
   accelerazione istantanea del bilanciere).
6. **1RM stimato di oggi**: usa la velocità media della ripetizione più
   veloce della serie e il profilo carico-velocità dell'esercizio scelto —
   affiancata da una seconda stima classica (formula di Epley, da peso e
   numero di ripetizioni) come riferimento incrociato. Vedi la sezione
   dedicata più sotto.
7. **Feedback su Velocity Loss**: confronta la velocità media della prima e
   dell'ultima ripetizione della serie e restituisce un consiglio pratico.

### 🐞 Bug corretto: 1RM assurdo su serie lunghe (es. "100kg×8 → 500kg")
Nella versione precedente, una serie di più ripetizioni (es. 8 reps) poteva
produrre una stima 1RM completamente irrealistica (es. 500kg da un carico di
100kg). Causa: il modello carico-velocità è calibrato per **serie brevi (1-3
ripetizioni) a velocità massima intenzionale con un carico impegnativo** —
esattamente come funzionano i dispositivi VBT commerciali. Su una serie più
lunga o sub-massimale, anche il colpo "più veloce" della serie può avere una
velocità che il modello interpreta come "carico leggerissimo", gonfiando la
stima. Un margine di sicurezza troppo permissivo (20% come soglia minima)
lasciava passare questi casi estremi.

**Correzioni applicate:**
- Il margine minimo di sicurezza è salito dal 20% al 30% del %1RM.
- Quando la serie ha più di 3 ripetizioni (o quando il modello finisce comunque
  fuori dal proprio range valido), l'app **non sostituisce silenziosamente**
  il numero: mostra entrambe le stime — quella da velocità e quella classica
  da ripetizioni (Epley) — con un avviso esplicito su quale delle due fidarsi
  in quel caso, e un suggerimento su come ottenere una lettura VBT precisa
  (serie da 1-3 ripetizioni a massima velocità).
- Rafforzata anche la robustezza del calcolo: uno smoothing leggero in più
  sulla serie di velocità (oltre a quello sulla posizione) e un filtro sul
  numero minimo di fotogrammi per considerare valida una ripetizione, per
  evitare che 2-3 fotogrammi rumorosi vengano letti come un colpo con
  velocità istantanea assurda.

Testato end-to-end (upload → tracciamento → dashboard) con una serie
sintetica da 8 ripetizioni: la stima da ripetizioni resta nell'ordine di
grandezza atteso (~127kg per 100kg×8), mentre quella da velocità viene
correttamente segnalata come non affidabile per una serie di quella
lunghezza, indipendentemente da eventuali rumore/imprecisioni di
tracciamento a monte.

### 🐞 Bug corretto: un solo colpo "anomalo" poteva dettare l'1RM da solo
Anche dopo il fix precedente, restava un problema più sottile: la velocità
di ogni ripetizione **è già calcolata solo sulla fase concentrica** (i
fotogrammi classificati "in salita" — la fase eccentrica, la discesa
controllata, non entra mai nel calcolo). Il bug reale era un altro: la fase
eccentrica è lenta e controllata, quindi ha un rapporto segnale/rumore
peggiore della concentrica esplosiva — basta un piccolo errore di
tracciamento durante la discesa perché la velocità istantanea superi per
qualche fotogramma la soglia di "movimento", venendo scambiata per un breve
tratto in salita. Se questo tratto anomalo risultava — per puro rumore — più
"veloce" di tutte le ripetizioni vere, veniva scelto come "ripetizione più
veloce" per il calcolo dell'1RM, falsando tutto.

**Correzioni applicate:**
- Soglia di rumore (`V_THRESHOLD`) alzata e resa più severa: un tratto deve
  avere un picco di velocità chiaramente sopra la soglia (non solo "appena
  sopra" per un fotogramma) per essere considerato un vero movimento.
- Durata minima di una ripetizione ora proporzionata agli fps del video
  (prima era un numero fisso di fotogrammi, impreciso su video girati a
  frame rate diversi).
- **Filtro anti-outlier**: tra tutte le ripetizioni rilevate, quelle con una
  velocità media superiore a 2,2 volte la mediana della serie vengono
  escluse dal calcolo dell'1RM e della perdita di velocità (ma restano
  conteggiate nel numero di ripetizioni). Una serie vera di ripetizioni
  pesanti ha velocità simili tra loro: un singolo colpo molto più
  "esplosivo" di tutti gli altri è quasi sempre un artefatto di
  tracciamento, non un vero exploit dell'atleta. Se l'app esclude una
  ripetizione per questo motivo, te lo segnala esplicitamente sotto la
  dashboard.
- Anche "Velocità di picco" e "Potenza di picco" nella dashboard ora
  derivano solo dalle ripetizioni valide/non-outlier, per coerenza in tutta
  la scheda.

Verificato con un test dedicato: inserendo artificialmente un colpo spurio a
2,1 m/s in mezzo a tre ripetizioni reali coerenti (~0,65-0,77 m/s), il
filtro lo esclude correttamente e la stima 1RM passa da 333kg (calcolo
"ingenuo", senza filtro) a 183kg (usando la vera ripetizione più veloce).

### 🐞 Bug corretto: velocità "schiacciata" → 1RM = peso sollevato
Un altro caso reale: panca piana, 65kg, 3 ripetizioni, velocità media
rilevata sulla rep più veloce di soli 0,16 m/s (velocità di picco 0,34 m/s).
L'app restituiva un 1RM stimato di **65kg esatti** — cioè "il tuo massimale è
esattamente il peso che hai appena sollevato per 3 ripetizioni", il che è
fisicamente impossibile: se fai 3 rep non sei al 100% del massimale sulla
prima.

**Due cause distinte, corrette entrambe:**

1. **La media veniva "tirata giù" da fotogrammi quasi fermi a inizio/fine
   ripetizione.** Il meccanismo che evita di spezzare una rep per un
   fotogramma rumoroso (debounce) ha un effetto collaterale: include nel
   segmento anche qualche fotogramma di stacco iniziale e di lockout finale,
   quasi fermi. Includerli nella *media* la fa crollare, anche se a metà
   salita la spinta è stata forte (lo confermava la velocità di picco, molto
   più alta). Ora questi fotogrammi vengono rifilati **solo dal calcolo della
   media** (non dal resto della logica) prima di calcolare la velocità media
   di ogni ripetizione.
2. **Non esisteva un controllo "soffitto".** Il fix precedente controllava
   solo se il %1RM calcolato fosse troppo *basso* (velocità troppo alta per
   il modello). Ma non controllava mai se fosse implausibilmente *alto*
   (velocità troppo bassa per il numero di ripetizioni realmente svolte) — e
   quel caso specifico ci cadeva dentro in pieno (%1RM grezzo: 109%, cioè
   "oltre il massimale", pur avendo fatto 3 rep). Ora l'app calcola anche il
   %1RM atteso in base al numero di ripetizioni svolte (stessa logica della
   formula di Epley) e, se il valore misurato lo supera troppo, segnala la
   stima da velocità come non affidabile e rimanda a quella da ripetizioni.

Non ho invece integrato la formula "a velocità di picco" proposta in un
suggerimento ricevuto (`%1RM = 117.8 - 45.9·v_picco`): non sono riuscito a
verificarla come uno standard scientifico effettivamente validato, e non
volevo inserire nel codice un numero dall'aria autorevole ma non verificato.
La velocità di picco resta comunque visibile nella dashboard come dato di
per sé utile.

**Anche qui, un limite reale che nessun fix software può eliminare del
tutto**: se il telefono non è ben perpendicolare al piano di movimento del
bilanciere, la distorsione prospettica riduce i pixel percorsi dal
bilanciere rispetto al reale, abbassando la velocità calcolata. L'app ora lo
ricorda esplicitamente nello step dei parametri VBT, ma la soluzione vera
resta una buona inquadratura in fase di ripresa.

### ⚠️ Un'avvertenza importante sui profili carico-velocità
Solo il profilo della **Panca Piana** (`%1RM = 121.1 - 74.7·v`) corrisponde a
un modello diffuso in letteratura VBT. Per **Squat** e **Stacco da terra** non
esiste un equivalente altrettanto standardizzato, quindi il codice usa
coefficienti **indicativi/approssimativi** (segnalati come tali nei commenti
di `app.py`, nella funzione `EXERCISE_PROFILES`). Per un uso serio ti consiglio
di calibrarli con i tuoi dati reali (massimali noti + velocità misurate) o con
fonti scientifiche specifiche per la tua popolazione/esercizio.

In generale: **tutte le metriche VBT di questa app sono stime da video 2D non
calibrato** (una fotocamera, senza encoder lineare) — utili come riferimento
di tendenza e per un feedback di massima, non come dato clinico validato.

---

## 📁 Contenuto del pacchetto

```
bar-path-tracker/
├── app.py                   # applicazione Streamlit completa (Bar Path + VBT)
├── requirements.txt         # dipendenze (compatibili con Python 3.14)
├── assets/
│   ├── pragma_logo.png      # logo originale (usato come favicon)
│   └── pragma_wordmark.png  # logo ritagliato (usato in testata)
├── .streamlit/
│   └── config.toml          # tema grafico dell'app (dark, palette PRAGMA)
└── README.md                # queste istruzioni
```

*Nota*: i nomi dei caratteri (Space Grotesk, Inter, IBM Plex Mono) vengono
caricati da Google Fonts via CSS al volo, nel browser di chi usa l'app: serve
quindi una connessione internet lato utente per vederli correttamente. Se non
disponibile, il browser mostra automaticamente un font di sistema simile,
senza errori.

---

## 💻 Come testarlo in locale su Windows (Python 3.14)

1. **Estrai** lo zip in una cartella, es. `C:\Progetti\bar-path-tracker`.
2. Apri PowerShell in quella cartella.
3. Crea e attiva un ambiente virtuale:
   ```powershell
   python -m venv venv
   venv\Scripts\activate
   ```
4. Installa le dipendenze:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
5. Avvia l'app:
   ```powershell
   streamlit run app.py
   ```
6. Nel browser (si apre da solo su `http://localhost:8501`):
   - Scegli la modalità in alto ("Solo Bar Path" o "VBT Avanzato").
   - Scegli la modalità in alto. Se scegli VBT, subito sotto l'app ti chiede
     esercizio, peso sul bilanciere e diametro del disco (nel flusso
     principale della pagina, non nella sidebar: così non li perdi di vista
     sul telefono, dove la sidebar parte chiusa).
   - Carica il video, clicca sul bilanciere nel primo fotogramma (in modalità
     VBT, fai combaciare l'area selezionata con l'altezza del disco), poi
     premi **"Elabora Video"**.

### Consigli per risultati VBT affidabili
- Registra **di lato**, con la fotocamera perpendicolare al piano di
  movimento del bilanciere (evita angolazioni oblique: falserebbero la
  calibrazione pixel→metri).
- Tieni la **fotocamera ferma** (treppiede) e alla stessa distanza per tutta
  la serie.
- Seleziona un punto/area ad **alto contrasto** sul bordo del disco.
- Video **orizzontali**, buona luce, tutta la serie nell'inquadratura.

---

## ☁️ Pubblicazione online gratuita

Vale la stessa procedura già vista in precedenza (Streamlit Community Cloud o
Hugging Face Spaces): carica i file su un repository GitHub e collega il
repository dalla piattaforma scelta. Il `requirements.txt` non è cambiato
nelle dipendenze principali, quindi la procedura di deploy resta identica.

**Novità**: assicurati di caricare su GitHub anche la cartella `assets/` con
i due file `pragma_logo.png` e `pragma_wordmark.png` — se manca, l'app
mostra comunque il testo "PRAGMA FIT" al posto del logo (fallback previsto
nel codice), ma perde l'immagine del marchio.

---

## ⚠️ Limiti noti

- Il tracciamento segue il punto scelto sul primo fotogramma: se il
  bilanciere esce dall'inquadratura o viene oscurato a lungo, il tracciamento
  può perdere il riferimento (l'app segnala quanti fotogrammi sono stati
  persi).
- Le metriche VBT presuppongono un movimento **verticale** e una fotocamera
  perpendicolare al piano di movimento: inquadrature oblique o bilancieri che
  si muovono molto anche in orizzontale (es. deviazioni laterali marcate)
  riducono l'accuratezza della velocità/potenza stimata.
- I profili carico-velocità per Squat e Stacco sono indicativi (vedi sopra).
- Video verticali con metadati di rotazione a volte non vengono gestiti
  correttamente da OpenCV.

---

## 🔧 Idee per evoluzioni future

- Calibrazione automatica del profilo carico-velocità con dati storici
  dell'utente (invece di coefficienti fissi).
- Grafico velocità/potenza nel tempo, non solo i valori aggregati.
- Selezione di un rettangolo (non solo un punto) per inizializzare il tracker
  con più precisione, e per una calibrazione pixel→metri più robusta.
