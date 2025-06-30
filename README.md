# AInterpelli - Scraper Cognitivo

`AInterpelli` è uno scraper intelligente basato su LLM (Google Gemini) progettato per raccogliere, analizzare e archiviare gli interpelli per le supplenze scolastiche dai siti degli Uffici Scolastici Territoriali (UST) della Lombardia.

Lo script è in grado di navigare le pagine dei siti, interpretare il contenuto HTML per trovare i link corretti, analizzare i documenti PDF per estrarre le informazioni chiave e salvarle in un database locale SQLite.

## Funzionalità Principali

-   **Scraping Cognitivo**: Utilizza un modello linguistico di grandi dimensioni per analizzare l'HTML delle pagine e trovare i link agli articoli e ai PDF, rendendo lo script resiliente ai cambiamenti di layout.
-   **Analisi PDF**: Invia i documenti PDF all'LLM per estrarre dati strutturati (scuola, classe di concorso, ore, ecc.).
-   **Multiprocessing**: Accelera notevolmente il processo di scraping analizzando più articoli in parallelo, sfruttando tutti i core della CPU.
-   **Database Locale**: Salva tutti i dati raccolti in un database SQLite (`interpelli.sqlite`) per una facile consultazione e analisi future.
-   **Interfaccia Interattiva**: Permette all'utente di scegliere se avviare una nuova scansione o interrogare il database esistente.
-   **Filtri e Esportazione**: Offre un menu per filtrare i risultati salvati (per classe di concorso, ore) e per esportare le viste correnti in un file PDF.

## Setup del Progetto

1.  **Clona il Repository** (o scarica i file in una cartella).

2.  **Crea il file di ambiente**:
    Nella cartella principale del progetto, crea un file chiamato `.env` e inserisci la tua chiave API di Gemini in questo formato:
    ```
    GEMINI_API_KEY="LA_TUA_CHIAVE_API_SEGRETA"
    ```

3.  **Crea e Attiva l'Ambiente Virtuale**:
    Apri un terminale nella cartella del progetto ed esegui:
    ```bash
    # Crea l'ambiente (solo la prima volta)
    python -m venv venv

    # Attiva l'ambiente (ogni volta che inizi a lavorare)
    # Su Windows PowerShell:
    .\venv\Scripts\Activate.ps1
    # Su macOS/Linux:
    source venv/bin/activate
    ```
    *Se PowerShell dà un errore di sicurezza, esegui prima: `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process`*

4.  **Installa le Dipendenze**:
    Con l'ambiente virtuale attivo, esegui:
    ```bash
    pip install -r requirements.txt
    ```

## Come Eseguire lo Script

Una volta completato il setup, lancia lo script principale dal terminale (con l'ambiente virtuale attivo):

```bash
python ainterpelli.py