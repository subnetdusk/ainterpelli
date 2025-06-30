import config
import scraper
import llm_processor
import time
import logging

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='diagnostics.log',
        filemode='w'
    )

def run_diagnostics():
    setup_logging()
    logging.info("Avvio Diagnostica Scraper AInterpelli (Logica LLM)")
    logging.info("="*40)

    # Setup Gemini, necessario per l'analisi HTML
    model = config.setup_gemini()
    if not model:
        logging.error("Impossibile configurare Gemini. Test interrotto.")
        return

    all_sites_ok = True

    for provincia, site_info in config.SITES_CONFIG.items():
        logging.info(f"\n--- TEST: Provincia di {provincia.upper()} ---")
        base_url = site_info['url']
        logging.info(f"URL Base: {base_url}")

        try:
            # --- Test Fase 1: Estrarre i link con l'LLM ---
            logging.info("\n[FASE 1] Recupero HTML e analisi con LLM...")
            
            html_content = scraper.get_page_html(base_url)
            if not html_content:
                logging.error(">>> RISULTATO FASE 1: FALLITO - Impossibile recuperare l'HTML.")
                all_sites_ok = False
                continue

            page_data = llm_processor.extract_page_links_with_gemini(model, html_content, base_url)
            article_links = page_data.get("article_links", [])

            if not article_links:
                logging.warning(">>> RISULTATO FASE 1: FALLITO - L'LLM non ha trovato link ad articoli.")
                all_sites_ok = False
                continue

            logging.info(f">>> RISULTATO FASE 1: SUCCESSO - L'LLM ha trovato {len(article_links)} link.")
            
            # --- Test Fase 2: Analizzare il primo articolo per trovare link a PDF ---
            first_article_url = article_links[0]
            logging.info(f"\n[FASE 2] Analisi del primo articolo per link a PDF...")
            logging.info(f"URL Articolo di test: {first_article_url}")
            
            pdf_links = scraper.find_pdf_in_page(first_article_url)

            if not pdf_links:
                logging.warning(">>> RISULTATO FASE 2: FALLITO - Nessun link a PDF trovato nella pagina dell'articolo.")
                all_sites_ok = False
                continue

            logging.info(f">>> RISULTATO FASE 2: SUCCESSO - Trovati {len(pdf_links)} link a PDF.")
            logging.info(f"Esempio link PDF: {pdf_links[0]}")
            
            logging.info(f"\n--- TEST per {provincia.upper()} COMPLETATO CON SUCCESSO ---")
        
        except Exception as e:
            logging.error(f">>> ERRORE IMPREVISTO per {provincia}: {e}", exc_info=True)
            all_sites_ok = False

        time.sleep(5) # Pausa per rispettare i limiti dell'API

    logging.info("\n" + "="*40)
    if all_sites_ok:
        logging.info("Diagnostica completata. Tutti i siti sembrano rispondere correttamente.")
    else:
        logging.warning("Diagnostica completata. Sono stati riscontrati problemi. Controllare diagnostics.log.")

if __name__ == '__main__':
    print("Avvio diagnostica con logica LLM... L'output verrà salvato nel file 'diagnostics.log'")
    run_diagnostics()
    print("Diagnostica completata. Controllare il file 'diagnostics.log' per i risultati.")