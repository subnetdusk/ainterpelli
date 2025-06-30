import config
import scraper
import llm_processor
import time
import logging
import os
import json
import asyncio
import aiohttp

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='simple_diagnostics.log',
        filemode='w'
    )

def select_province_for_test():
    provinces = list(config.SITES_CONFIG.keys())
    while True:
        print("\n--- SELEZIONA PROVINCIA PER LA DIAGNOSTICA ---")
        for i, province in enumerate(provinces, 1):
            print(f"{i:2}: {province}")
        print("---------------------------------------------")
        try:
            choice_str = input("Inserisci il numero della provincia da testare (0 per uscire): ")
            choice = int(choice_str)
            if choice == 0:
                return None
            if 1 <= choice <= len(provinces):
                return provinces[choice - 1]
            else:
                print("Scelta non valida.")
        except (ValueError, IndexError):
            print("Input non valido.")

async def run_simple_diagnostics():
    setup_logging()
    logging.info("Avvio Diagnostica Semplice (Logica Universale)")
    print("Avvio diagnostica... L'output verrà salvato nel file 'simple_diagnostics.log'")
    
    provincia_test = select_province_for_test()
    if not provincia_test:
        print("Nessuna provincia selezionata. Uscita.")
        return

    base_url = config.SITES_CONFIG[provincia_test]["url"]
    
    models = config.setup_gemini()
    if not models:
        logging.error("Impossibile configurare Gemini. Test interrotto.")
        return

    logging.info("="*40)
    logging.info(f"\n--- TEST: Provincia di {provincia_test.upper()} ---")
    
    async with aiohttp.ClientSession() as session:
        try:
            logging.info("\n[FASE 1] Trovare i link agli articoli...")
            html_content_list = await scraper.get_page_html(session, base_url)
            if not html_content_list: 
                logging.error(">>> RISULTATO FASE 1: FALLITO - Impossibile recuperare l'HTML della pagina elenco.")
                return
            
            article_links = await llm_processor.extract_page_links_with_gemini(models, html_content_list, base_url, logging)
            if not article_links:
                logging.warning(">>> RISULTATO FASE 1: FALLITO - L'LLM non ha trovato link ad articoli.")
                return

            first_article_url = article_links[0]
            logging.info(f"Articolo di test selezionato: {first_article_url}")

            logging.info("\n[FASE 2] Analisi universale della pagina articolo...")
            html_content_article = await scraper.get_page_html(session, first_article_url)
            if not html_content_article: 
                logging.error(f">>> RISULTATO FASE 2: FALLITO - Impossibile recuperare l'HTML dell'articolo: {first_article_url}")
                return

            analysis_result = await llm_processor.analyze_article_page_and_get_data_or_links(models, html_content_article, first_article_url, logging)
            if not analysis_result:
                logging.error(">>> RISULTATO FASE 2: FALLITO - L'analisi della pagina non ha restituito un risultato valido.")
                return
            
            logging.info(f">>> RISULTATO FASE 2: SUCCESSO - L'analisi ha prodotto un risultato.")

            logging.info("\n[FASE 3] Azione basata sull'analisi...")
            file_links = analysis_result.get("file_links", [])
            gdrive_links = analysis_result.get("gdrive_links", [])
            portal_links = analysis_result.get("portal_links", [])
            extracted_data_from_html = analysis_result.get("extracted_data")

            if file_links:
                doc_url = file_links[0]
                logging.info(f"Azione: Scaricare il primo file diretto trovato: {doc_url}")
                file_path = await scraper.download_direct_file(session, doc_url)
                if file_path:
                    extracted_data = await llm_processor.process_pdf_with_gemini(models, file_path, logging)
                    os.remove(file_path)
                    if extracted_data:
                        logging.info(f">>> RISULTATO FASE 3: SUCCESSO - Dati estratti dal file: {json.dumps(extracted_data, indent=2, ensure_ascii=False)}")
            
            elif gdrive_links:
                doc_url = gdrive_links[0]
                logging.info(f"Azione: Scaricare il primo file Google Drive trovato: {doc_url}")
                file_path = await scraper.download_google_drive_file(session, doc_url)
                if file_path:
                    extracted_data = await llm_processor.process_pdf_with_gemini(models, file_path, logging)
                    os.remove(file_path)
                    if extracted_data:
                        logging.info(f">>> RISULTATO FASE 3: SUCCESSO - Dati estratti da Google Drive: {json.dumps(extracted_data, indent=2, ensure_ascii=False)}")

            elif portal_links:
                portal_url = portal_links[0]
                logging.info(f"Azione: Analizzare HTML del portale: {portal_url}")
                portal_html = await scraper.get_page_html(session, portal_url)
                if portal_html:
                    extracted_data = await llm_processor.extract_data_from_html(models, portal_html, logging)
                    if extracted_data:
                        logging.info(f">>> RISULTATO FASE 3: SUCCESSO - Dati estratti dal portale: {json.dumps(extracted_data, indent=2, ensure_ascii=False)}")

            elif extracted_data_from_html:
                logging.info(f">>> RISULTATO FASE 3: SUCCESSO - Dati estratti dall'HTML: {json.dumps(extracted_data_from_html, indent=2, ensure_ascii=False)}")

            else:
                logging.warning(">>> RISULTATO FASE 3: FALLITO - L'LLM non ha trovato né link a documenti né dati estraibili.")

        except Exception as e:
            logging.error(f">>> ERRORE IMPREVISTO: {e}", exc_info=True)

    logging.info("\n" + "="*40)
    print("Diagnostica completata. Controllare il file 'simple_diagnostics.log'.")

if __name__ == '__main__':
    try:
        asyncio.run(run_simple_diagnostics())
    except KeyboardInterrupt:
        print("\nDiagnostica interrotta dall'utente.")