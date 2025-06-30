import config
import scraper
import llm_processor
import time
import logging
import os
import json # <-- ECCO LA CORREZIONE

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='simple_diagnostics.log',
        filemode='w'
    )

def run_simple_diagnostics():
    setup_logging()
    logging.info("Avvio Diagnostica Semplice (un solo sito)")
    logging.info("="*40)

    provincia_test = "Bergamo"
    base_url = config.SITES_CONFIG[provincia_test]["url"]
    
    model = config.setup_gemini()
    if not model:
        logging.error("Impossibile configurare Gemini. Test interrotto.")
        print("Impossibile configurare Gemini. Controlla la console.")
        return

    logging.info(f"\n--- TEST: Provincia di {provincia_test.upper()} ---")
    logging.info(f"URL Base: {base_url}")

    try:
        # --- FASE 1: Trovare i link agli articoli con l'LLM ---
        logging.info("\n[FASE 1] Recupero HTML pagina elenco e analisi con LLM...")
        html_content_list = scraper.get_page_html(base_url)
        if not html_content_list:
            logging.error(">>> RISULTATO FASE 1: FALLITO - Impossibile recuperare l'HTML della pagina elenco.")
            return

        page_data = llm_processor.extract_page_links_with_gemini(model, html_content_list, base_url, logging)
        article_links = page_data.get("article_links", [])

        if not article_links:
            logging.warning(">>> RISULTATO FASE 1: FALLITO - L'LLM non ha trovato link ad articoli.")
            return

        logging.info(f">>> RISULTATO FASE 1: SUCCESSO - L'LLM ha trovato {len(article_links)} link.")
        
        # --- FASE 2: Trovare il link al PDF nella pagina del primo articolo con l'LLM ---
        first_article_url = article_links[0]
        logging.info(f"\n[FASE 2] Recupero HTML articolo e ricerca PDF con LLM...")
        logging.info(f"URL Articolo di test: {first_article_url}")
        
        html_content_article = scraper.get_page_html(first_article_url)
        if not html_content_article:
            logging.error(f">>> RISULTATO FASE 2: FALLITO - Impossibile recuperare l'HTML dell'articolo: {first_article_url}")
            return

        pdf_links = llm_processor.find_pdf_link_with_gemini(model, html_content_article, first_article_url, logging)

        if not pdf_links:
            logging.warning(">>> RISULTATO FASE 2: FALLITO - L'LLM non ha trovato link a PDF nella pagina dell'articolo.")
            return

        logging.info(f">>> RISULTATO FASE 2: SUCCESSO - L'LLM ha trovato {len(pdf_links)} link a PDF.")
        
        # --- FASE 3: Scaricare il PDF ed estrarre i dati con l'LLM ---
        first_pdf_url = pdf_links[0]
        logging.info(f"\n[FASE 3] Download PDF e estrazione dati con LLM...")
        logging.info(f"URL PDF di test: {first_pdf_url}")

        pdf_path = scraper.download_file(first_pdf_url)
        if not pdf_path:
            logging.error(">>> RISULTATO FASE 3: FALLITO - Impossibile scaricare il file PDF.")
            return

        extracted_data = llm_processor.process_pdf_with_gemini(model, pdf_path, logging)

        # Pulizia del file scaricato
        os.remove(pdf_path)
        logging.info(f"File temporaneo rimosso: {pdf_path}")

        if not extracted_data:
            logging.warning(">>> RISULTATO FASE 3: FALLITO - L'LLM non ha estratto dati dal PDF.")
            return
        
        logging.info(">>> RISULTATO FASE 3: SUCCESSO - L'LLM ha estratto i seguenti dati:")
        logging.info(json.dumps(extracted_data, indent=2, ensure_ascii=False))

        logging.info(f"\n--- TEST per {provincia_test.upper()} COMPLETATO CON SUCCESSO ---")
    
    except Exception as e:
        logging.error(f">>> ERRORE IMPREVISTO per {provincia_test}: {e}", exc_info=True)

    logging.info("\n" + "="*40)
    logging.info("Diagnostica semplice completata. Controllare simple_diagnostics.log.")


if __name__ == '__main__':
    print("Avvio diagnostica semplice... L'output verrà salvato nel file 'simple_diagnostics.log'")
    run_simple_diagnostics()
    print("Diagnostica completata. Controllare il file 'simple_diagnostics.log' per i risultati.")