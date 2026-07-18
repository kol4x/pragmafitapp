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
   veloce della serie e il profilo carico-velocità dell'esercizio scelto.
7. **Feedback su Velocity Loss**: confronta la velocità media della prima e
   dell'ultima ripetizione della serie e restituisce un consiglio pratico.

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
