import scraper
import llm_processor
import os
import asyncio

async def fetch_and_extract_links_worker(semaphore, session, models, url, provincia, logger):
    """Worker per la Fase 1: recupera HTML di una pagina elenco e restituisce (link, provincia)."""
    async with semaphore:
        try:
            html_content = await scraper.get_page_html(session, url)
            if not html_content:
                return []
            article_links = await llm_processor.extract_page_links_with_gemini(models, html_content, url, logger)
            # Associa immediatamente la provincia corretta a ogni link trovato
            return [(link, provincia) for link in article_links]
        except Exception as e:
            logger.error(f"Errore imprevisto nel worker di raccolta link per {url}: {e}")
            return []


async def process_single_article_worker(semaphore, session, models, article_url, provincia, logger):
    """Worker per la Fase 2: analizza un singolo articolo."""
    async with semaphore:
        try:
            logger.info(f"Task per {article_url} avviato.")
            all_extracted_data = []

            html_content_article = await scraper.get_page_html(session, article_url)
            if not html_content_article:
                logger.warning(f"Impossibile recuperare l'HTML dell'articolo: {article_url}")
                return all_extracted_data

            analysis_result = await llm_processor.analyze_article_page_and_get_data_or_links(models, html_content_article, article_url, logger)
            if not analysis_result:
                logger.error(f"Analisi della pagina fallita per {article_url}")
                return all_extracted_data

            file_links = analysis_result.get("file_links", [])
            gdrive_links = analysis_result.get("gdrive_links", [])
            portal_links = analysis_result.get("portal_links", [])
            extracted_data_from_html = analysis_result.get("extracted_data")

            if file_links:
                for doc_url in file_links:
                    file_path = await scraper.download_direct_file(session, doc_url)
                    if file_path:
                        extracted_data = await llm_processor.process_pdf_with_gemini(models, file_path, logger)
                        if extracted_data:
                            items = extracted_data if isinstance(extracted_data, list) else [extracted_data]
                            for item in items:
                                item['provincia'] = provincia
                                item['url_sorgente'] = doc_url
                                all_extracted_data.append(item)
                        os.remove(file_path)
            
            if gdrive_links:
                for doc_url in gdrive_links:
                    file_path = await scraper.download_google_drive_file(session, doc_url)
                    if file_path:
                        extracted_data = await llm_processor.process_pdf_with_gemini(models, file_path, logger)
                        if extracted_data:
                            items = extracted_data if isinstance(extracted_data, list) else [extracted_data]
                            for item in items:
                                item['provincia'] = provincia
                                item['url_sorgente'] = doc_url
                                all_extracted_data.append(item)
                        os.remove(file_path)

            if portal_links:
                for portal_url in portal_links:
                    portal_html = await scraper.get_page_html(session, portal_url)
                    if portal_html:
                        extracted_data = await llm_processor.extract_data_from_html(models, portal_html, logger)
                        if extracted_data:
                            items = extracted_data if isinstance(extracted_data, list) else [extracted_data]
                            for item in items:
                                item['provincia'] = provincia
                                item['url_sorgente'] = portal_url
                                all_extracted_data.append(item)
            
            if extracted_data_from_html:
                items = extracted_data_from_html if isinstance(extracted_data_from_html, list) else [extracted_data_from_html]
                for item in items:
                    item['provincia'] = provincia
                    item['url_sorgente'] = article_url
                    all_extracted_data.append(item)
            
            return all_extracted_data
        except Exception as e:
            logger.error(f"Errore imprevisto nel worker di analisi articolo per {article_url}: {e}")
            return []