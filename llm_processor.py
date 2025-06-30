import google.generativeai as genai
import json
import time
from urllib.parse import urljoin
import logging
import asyncio

# --- CARICAMENTO DELLA BASE DI CONOSCENZA DELLE CLASSI DI CONCORSO ---
try:
    with open('classi_concorso.json', 'r', encoding='utf-8') as f:
        CDC_DATA = json.load(f)
    # Convertiamo la lista di oggetti in una stringa JSON formattata per il prompt
    CDC_CONTEXT_JSON = json.dumps(CDC_DATA, indent=2, ensure_ascii=False)
except FileNotFoundError:
    print("ERRORE CRITICO: Il file 'classi_concorso.json' non è stato trovato. Assicurati che sia nella stessa cartella.")
    CDC_CONTEXT_JSON = "[]"
except json.JSONDecodeError:
    print("ERRORE CRITICO: Il file 'classi_concorso.json' contiene un errore di formattazione.")
    CDC_CONTEXT_JSON = "[]"

# --- PROMPT ---

LINK_EXTRACTION_PROMPT = """
Sei un assistente specializzato nell'analizzare i siti della pubblica amministrazione italiana, in particolare quelli degli Uffici Scolastici Provinciali.
Il tuo unico compito è analizzare il seguente HTML di una pagina di elenco e estrarre TUTTI i link `<a>` che puntano a pagine di dettaglio di singoli "interpelli", "avvisi per supplenze", "convocazioni" o "posti disponibili".

**REGOLA DI ESCLUSIONE IMPORTANTE**: Ignora e non includere nell'output i link il cui testo è ESATTAMENTE "Interpelli ricerca supplenti" o "Interpelli-ricerca-supplenti", perché sono link di categoria e non avvisi specifici.

Restituisci i risultati in un oggetto JSON con questo esatto formato:
{{"article_links": ["url_completo_1", "url_completo_2"]}}

Assicurati che tutti gli URL restituiti siano assoluti. L'URL di base per questa pagina è: {base_url}
Se non trovi nessun link ad articoli, restituisci una lista vuota: `[]`.
"""

UNIVERSAL_DATA_FINDER_PROMPT = """
Sei un assistente esperto nell'analisi di avvisi scolastici italiani.
Il tuo compito è analizzare il seguente HTML di una pagina di avviso e trovare le informazioni di un interpello.

**SEGUI QUESTA LOGICA ESATTA:**
1.  **CERCA PRIMA I LINK**: Analizza l'HTML e cerca link `<a>` che puntano a documenti o portali esterni.
2.  **CATEGORIZZA I LINK**:
    - Se un link finisce con `.pdf`, `.doc`, `.docx`, mettilo nella lista `file_links`.
    - Se un link punta a `drive.google.com`, mettilo nella lista `gdrive_links`.
    - Se un link punta a portali noti come `axioscloud.it`, `nuvola.madisoft.it`, `argo.net`, `spaggiari.eu`, mettilo nella lista `portal_links`.
3.  **SE TROVI QUALSIASI TIPO DI LINK**: Restituisci un oggetto JSON con le liste di link che hai trovato. `extracted_data` deve essere `null`.
4.  **SE E SOLO SE NON TROVI NESSUN LINK**: Allora analizza il testo dell'HTML per estrarre direttamente i dati dell'interpello e mettili in `extracted_data`.

**Formato JSON di risposta OBBLIGATORIO:**
`{{"file_links": [], "gdrive_links": [], "portal_links": [], "extracted_data": OGGETTO_DATI_O_NULL}}`

L'URL di base per questa pagina è: {base_url}. Assicurati che tutti gli URL siano assoluti.

Formato per `extracted_data` (se presente):
`{{"nome_scuola": "Nome...", "indirizzo": "Indirizzo...", "citta": "Città...", "data_fine_incarico": "DD/MM/YYYY", "classe_di_concorso": "Codice...", "numero_di_ore": 18, "tipo_cattedra": "Tipo..."}}`
"""

# --- PROMPT DI ESTRAZIONE DATI DINAMICO ---
DATA_EXTRACTION_PROMPT_TEMPLATE = f"""
Sei un esperto del sistema scolastico italiano. Il tuo compito è analizzare il documento o il testo HTML fornito e estrarre le seguenti informazioni in formato JSON.

### CONTESTO E CODICI DI RIFERIMENTO ###
Usa la seguente lista JSON come riferimento per dedurre la Classe di Concorso (CDC) corretta, anche se il codice non è scritto esplicitamente.
Cerca nel testo una delle descrizioni o degli "alias" e restituisci il "codice" corrispondente. Se trovi un codice esplicito (es. A041), usa quello.

**LISTA DI RIFERIMENTO CDC:**
{CDC_CONTEXT_JSON}

### FORMATO JSON RICHIESTO ###
{{
  "nome_scuola": "Nome completo dell'istituto scolastico",
  "indirizzo": "Indirizzo completo della scuola (via, numero civico)",
  "citta": "Città della scuola",
  "data_fine_incarico": "Data di fine dell'incarico (formato DD/MM/YYYY)",
  "classe_di_concorso": "Codice della classe di concorso dedotto o trovato",
  "numero_di_ore": "Numero intero di ore settimanali",
  "tipo_cattedra": "Descrizione del tipo di cattedra (es. Cattedra Interna, Spezzone, COE)"
}}

Analizza attentamente il documento per trovare tutti i dati. Se un'informazione non è presente, lascia il campo come null.
"""

# Assegniamo il template compilato a una variabile per usarlo nelle funzioni
DATA_EXTRACTION_PROMPT = DATA_EXTRACTION_PROMPT_TEMPLATE


async def extract_page_links_with_gemini(models, html_content, base_url, logger):
    logger.info(f"Invio HTML da {base_url} a Gemini (fast) per l'estrazione dei link agli articoli...")
    prompt = LINK_EXTRACTION_PROMPT.format(base_url=base_url)
    
    try:
        response = await models['fast'].generate_content_async([prompt, html_content])
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        
        parsed_data = json.loads(cleaned_response)
        
        article_links = []
        if isinstance(parsed_data, dict):
            article_links = parsed_data.get("article_links", [])
        elif isinstance(parsed_data, list):
            article_links = parsed_data

        if article_links:
            article_links = [urljoin(base_url, link) for link in article_links]
            
        logger.info(f"Trovati {len(article_links)} link di articoli.")
        return article_links
    except json.JSONDecodeError:
        logger.error(f"Errore di decodifica JSON: Gemini ha restituito una risposta non valida. Risposta: {response.text}")
        return []
    except Exception as e:
        logger.error(f"Errore durante l'estrazione dei link con Gemini: {e}")
        return []

async def analyze_article_page_and_get_data_or_links(models, html_content, base_url, logger):
    logger.info(f"Invio HTML da {base_url} a Gemini (fast) per l'analisi universale...")
    prompt = UNIVERSAL_DATA_FINDER_PROMPT.format(base_url=base_url)
    
    try:
        response = await models['fast'].generate_content_async([prompt, html_content])
        logger.info(f"\n--- RISPOSTA RICEVUTA (ANALISI UNIVERSALE) ---\n{response.text}")
        
        raw_text = response.text
        json_start = raw_text.find('{')
        json_end = raw_text.rfind('}')

        if json_start != -1 and json_end != -1:
            json_str = raw_text[json_start:json_end+1]
            data = json.loads(json_str)
            
            for key in ["file_links", "gdrive_links", "portal_links"]:
                if data.get(key):
                    data[key] = [urljoin(base_url, link) for link in data[key]]
            
            return data
        else:
            logger.warning(f"Nessun JSON valido trovato nella risposta di analisi universale. Risposta: {raw_text}")
            return None

    except Exception as e:
        logger.error(f"Errore durante l'analisi universale con Gemini: {e}")
        return None

async def extract_data_from_html(models, html_content, logger):
    logger.info("Invio HTML a Gemini (powerful) per l'estrazione dati diretta...")
    try:
        response = await models['powerful'].generate_content_async([DATA_EXTRACTION_PROMPT, html_content])
        raw_text = response.text
        json_start = raw_text.find('[') if raw_text.find('[') != -1 else raw_text.find('{')
        json_end = raw_text.rfind(']') if raw_text.rfind(']') != -1 else raw_text.rfind('}')

        if json_start != -1 and json_end != -1:
            json_str = raw_text[json_start:json_end+1]
            extracted_data = json.loads(json_str)
            logger.info("Dati estratti con successo da HTML.")
            return extracted_data
        else:
            logger.warning(f"Nessun blocco JSON trovato nella risposta di estrazione da HTML. Risposta: {raw_text}")
            return None
    except Exception as e:
        logger.error(f"Errore durante l'estrazione dati da HTML con Gemini: {e}")
        return None

async def process_pdf_with_gemini(models, pdf_path, logger):
    logger.info(f"Invio del file '{pdf_path}' a Gemini (powerful) per l'analisi dei dati...")
    try:
        uploaded_file = genai.upload_file(path=pdf_path, display_name=pdf_path)
        logger.info(f"File caricato con successo: {uploaded_file.display_name}")

        while uploaded_file.state.name == "PROCESSING":
            logger.info("In attesa che il file venga processato...")
            await asyncio.sleep(5)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
             raise ValueError(f"Elaborazione del file fallita: {uploaded_file.state}")

        response = await models['powerful'].generate_content_async([DATA_EXTRACTION_PROMPT, uploaded_file])
        
        raw_text = response.text
        json_start = raw_text.find('[') if raw_text.find('[') != -1 else raw_text.find('{')
        json_end = raw_text.rfind(']') if raw_text.rfind(']') != -1 else raw_text.rfind('}')

        if json_start != -1 and json_end != -1:
            json_str = raw_text[json_start:json_end+1]
            extracted_data = json.loads(json_str)
            logger.info("Dati estratti con successo.")
            return extracted_data
        else:
            logger.warning(f"Nessun blocco JSON trovato nella risposta di Gemini per {pdf_path}. Risposta completa: {raw_text}")
            return None

    except json.JSONDecodeError:
        logger.error(f"Errore di decodifica JSON dal PDF: {pdf_path}. Risposta di Gemini non era un JSON valido. Risposta completa: {response.text}")
        return None
    except Exception as e:
        logger.error(f"Errore durante l'elaborazione del PDF con Gemini: {e}")
        return None