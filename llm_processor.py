import google.generativeai as genai
import json
import time
from urllib.parse import urljoin
import logging

LINK_EXTRACTION_PROMPT = """
Sei un web scraper esperto. Analizza il seguente contenuto HTML.
Il tuo unico compito è identificare i link `<a>` che puntano ad articoli o post individuali che parlano di "interpelli", "avviso" o "supplenza".

**REGOLA DI ESCLUSIONE IMPORTANTE**: Ignora e non includere nell'output i link il cui testo del link è ESATTAMENTE "Interpelli ricerca supplenti" o "Interpelli-ricerca-supplenti".

Restituisci i risultati in un oggetto JSON con questo esatto formato:
{{"article_links": ["url_completo_1", "url_completo_2"]}}

Assicurati che tutti gli URL restituiti siano assoluti. L'URL di base per questa pagina è: {base_url}
Se non trovi nessun link ad articoli, restituisci una lista vuota: `[]`.
"""

PDF_FINDER_PROMPT = """
Sei un assistente specializzato nel trovare file. Analizza il seguente HTML della pagina di un articolo.
Il tuo unico compito è trovare l'URL ESATTO del link che avvia il download del documento PDF.
**IMPORTANTE**: Non inventare o costruire un URL. Estrai solo l'URL presente nell'attributo `href` di un tag `<a>`.
Il link potrebbe non finire con ".pdf", ma potrebbe essere un link dinamico (es. con parametri come `?aid=...`). Cerca link con testo come "allegato", "scarica", "download".

Restituisci i risultati in un oggetto JSON con questo esatto formato:
{{"pdf_links": ["url_esatto_estratto_da_href"]}}

Assicurati che tutti gli URL restituiti siano assoluti. L'URL di base per questa pagina è: {base_url}
Se non trovi nessun link a un PDF, restituisci una lista vuota: `[]`.
"""

PDF_EXTRACTION_PROMPT = """
Analizza il documento di interpello fornito e estrai le seguenti informazioni in formato JSON.
Se un'informazione non è presente, lascia il campo come null.

Formato JSON richiesto:
{
  "nome_scuola": "Nome completo dell'istituto scolastico",
  "indirizzo": "Indirizzo completo della scuola (via, numero civico)",
  "citta": "Città della scuola",
  "data_fine_incarico": "Data di fine dell'incarico (formato DD/MM/YYYY)",
  "classe_di_concorso": "Codice della classe di concorso (es. A028, A041)",
  "numero_di_ore": "Numero intero di ore settimanali",
  "tipo_cattedra": "Descrizione del tipo di cattedra (es. Cattedra Interna, Spezzone, COE)"
}

Analizza attentamente il documento per trovare tutti i dati. Presta particolare attenzione alle date e alle classi di concorso.
"""

def extract_page_links_with_gemini(model, html_content, base_url, logger):
    logger.info(f"Invio HTML da {base_url} a Gemini per l'estrazione dei link...")
    prompt = LINK_EXTRACTION_PROMPT.format(base_url=base_url)
    
    try:
        response = model.generate_content([prompt, html_content])
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(cleaned_response)
        
        article_links = data.get("article_links", [])
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

def find_pdf_link_with_gemini(model, html_content, base_url, logger):
    logger.info(f"Invio HTML da {base_url} a Gemini per la ricerca del PDF...")
    prompt = PDF_FINDER_PROMPT.format(base_url=base_url)

    try:
        response = model.generate_content([prompt, html_content])
        logger.info("\n--- RISPOSTA RICEVUTA DA GEMINI (PDF FINDER) ---\n" + response.text)
        cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
        data = json.loads(cleaned_response)

        pdf_links = data.get("pdf_links", [])
        if pdf_links:
            pdf_links = [urljoin(base_url, link) for link in pdf_links]
            logger.info(f"Trovati {len(pdf_links)} link a PDF.")
        
        return pdf_links
    except json.JSONDecodeError:
        logger.error(f"Errore di decodifica JSON: Gemini ha restituito una risposta non valida. Risposta: {response.text}")
        return []
    except Exception as e:
        logger.error(f"Errore durante la ricerca del PDF con Gemini: {e}")
        return []

def process_pdf_with_gemini(model, pdf_path, logger):
    logger.info(f"Invio del file '{pdf_path}' a Gemini per l'analisi dei dati...")
    try:
        uploaded_file = genai.upload_file(path=pdf_path, display_name=pdf_path)
        logger.info(f"File caricato con successo: {uploaded_file.display_name}")

        while uploaded_file.state.name == "PROCESSING":
            logger.info("In attesa che il file venga processato...")
            time.sleep(10)
            uploaded_file = genai.get_file(uploaded_file.name)

        if uploaded_file.state.name == "FAILED":
             raise ValueError(f"Elaborazione del file fallita: {uploaded_file.state}")

        response = model.generate_content([PDF_EXTRACTION_PROMPT, uploaded_file])
        
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