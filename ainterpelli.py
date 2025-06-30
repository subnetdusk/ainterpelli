import config
import database
import scraper
import llm_processor
import ui
import worker
import logging
import asyncio
import aiohttp
from itertools import chain

def setup_main_logging():
    """Configura il logger per il processo principale."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        filename='ainterpelli.log',
        filemode='w'
    )

async def run_scraping_mode():
    """Orchestra l'intero processo di scraping asincrono."""
    logger = logging.getLogger()
    
    provinces_to_scan = ui.get_provinces_to_scan()
    if not provinces_to_scan: return

    max_pages = ui.get_max_pages_to_scan()
    print(f"\nAvvio della ricerca per le province selezionate (max {max_pages} pagine)...")

    models = config.setup_gemini()
    if not models: return

    db_conn = database.create_connection()
    if not db_conn: return

    # --- FASE 1: Raccolta Parallela di tutti i link degli articoli ---
    all_pages_to_scan = []
    for page_num in range(1, max_pages + 1):
        for provincia in provinces_to_scan:
            base_url = config.SITES_CONFIG[provincia]['url']
            current_url = f"{base_url.rstrip('/')}/page/{page_num}/" if page_num > 1 else base_url
            all_pages_to_scan.append((current_url, provincia))
    
    LINK_COLLECTION_CONCURRENCY = 10
    link_semaphore = asyncio.Semaphore(LINK_COLLECTION_CONCURRENCY)
    
    print(f"\n--- FASE 1: Raccolta link da {len(all_pages_to_scan)} pagine (max {LINK_COLLECTION_CONCURRENCY} parallele) ---")
    
    async with aiohttp.ClientSession() as session:
        link_collection_tasks = [worker.fetch_and_extract_links_worker(link_semaphore, session, models, url, prov, logger) for url, prov in all_pages_to_scan]
        results_of_link_collection = await asyncio.gather(*link_collection_tasks)

    processed_urls = set()
    all_article_tasks = []
    for task_result in results_of_link_collection:
        for url, prov in task_result:
            if url not in processed_urls:
                processed_urls.add(url)
                all_article_tasks.append((url, prov))
    
    if not all_article_tasks:
        print("\nNessun nuovo articolo da analizzare trovato.")
        return
        
    # --- FASE 2: Esecuzione parallela controllata da semaforo ---
    ARTICLE_ANALYSIS_CONCURRENCY = 50
    analysis_semaphore = asyncio.Semaphore(ARTICLE_ANALYSIS_CONCURRENCY)
    
    print(f"\n--- FASE 2: Inizio Analisi di {len(all_article_tasks)} Articoli (max {ARTICLE_ANALYSIS_CONCURRENCY} in parallelo) ---")
    
    async with aiohttp.ClientSession() as session:
        worker_tasks = [worker.process_single_article_worker(analysis_semaphore, session, models, url, prov, logger) for url, prov in all_article_tasks]
        results_from_workers = await asyncio.gather(*worker_tasks)
    
    all_results = list(chain.from_iterable(results_from_workers))
    print(f"\nRaccolti {len(all_results)} risultati totali.")
    logger.info(f"Raccolti {len(all_results)} risultati totali.")

    for data in all_results:
        database.insert_interpello(db_conn, data)

    db_conn.close()
    print("\nProcesso di scraping e analisi completato!")
    logger.info("\nProcesso di scraping e analisi completato!")

def run_database_mode():
    print("\n--- Modalità di Interrogazione Database ---")
    db_conn = database.create_connection()
    if not db_conn:
        print("Impossibile connettersi al database.")
        return
    
    print("\nRecupero tutti gli interpelli salvati (ordinati per Provincia)...")
    last_displayed_rows = database.get_all_interpelli(db_conn)
    ui.print_results(last_displayed_rows)

    while True:
        print("\n--- Menu Filtri ---")
        print(" 1: Filtra per Classe di Concorso (singola)")
        print(" 2: Filtra per Ore (minimo)")
        print(" 3: Mostra tutti gli interpelli")
        print(" 4: Esporta questa vista in PDF")
        print(" 0: Torna al menu principale")
        
        choice = input("Scegli un'opzione: ")
        
        if choice == '1':
            classi = database.get_unique_classi_di_concorso(db_conn)
            if not classi:
                print("Nessuna classe di concorso trovata nel database per filtrare.")
                continue
            
            print("\n--- Seleziona Classe di Concorso ---")
            for i, cdc in enumerate(classi, 1):
                print(f"{i:2}: {cdc}")
            print("---------------------------------")
            
            try:
                cdc_choice_str = input("Inserisci il numero della classe da filtrare: ")
                cdc_choice = int(cdc_choice_str)
                if 1 <= cdc_choice <= len(classi):
                    selected_cdc = classi[cdc_choice - 1]
                    filters = {'classe_di_concorso': selected_cdc}
                    last_displayed_rows = database.get_interpelli_by_filter(db_conn, filters)
                    print(f"\n--- Risultati Filtrati per CDC: {selected_cdc} ---")
                    ui.print_results(last_displayed_rows)
                else:
                    print("Scelta non valida.")
            except (ValueError, IndexError):
                print("Input non valido.")

        elif choice == '2':
            try:
                ore_str = input("\nInserisci il numero minimo di ore (es. 16): ")
                min_ore = int(ore_str)
                if min_ore > 0:
                    filters = {'min_ore': min_ore}
                    last_displayed_rows = database.get_interpelli_by_filter(db_conn, filters)
                    print(f"\n--- Risultati Filtrati per Ore >= {min_ore} ---")
                    ui.print_results(last_displayed_rows)
                else:
                    print("Inserisci un numero positivo.")
            except ValueError:
                print("Input non valido. Inserisci un numero.")

        elif choice == '3':
            print("\nRecupero tutti gli interpelli salvati...")
            last_displayed_rows = database.get_all_interpelli(db_conn)
            ui.print_results(last_displayed_rows)

        elif choice == '4':
            ui.export_to_pdf(last_displayed_rows)

        elif choice == '0':
            break
        else:
            print("Scelta non valida.")
            
    db_conn.close()

def main():
    setup_main_logging()
    database.setup_database()

    while True:
        print("\n--- AInterpelli: Menu Principale ---")
        print(" 1: Interroga il Database Esistente")
        print(" 2: Avvia Scansione e Scraping Nuovi Interpelli")
        print(" 9: Cancella Intero Database")
        print(" 0: Esci")
        choice = input("Scegli un'opzione: ")
        
        if choice == '1':
            run_database_mode()
        elif choice == '2':
            try:
                asyncio.run(run_scraping_mode())
            except KeyboardInterrupt:
                print("\nEsecuzione interrotta dall'utente.")
        elif choice == '9':
            print("\nATTENZIONE: Stai per cancellare l'intero database degli interpelli.")
            confirm = input("Sei assolutamente sicuro? Digita 'SI' in maiuscolo per confermare: ")
            if confirm == "SI":
                print("Cancellazione del database in corso...")
                if database.delete_database_file():
                    print("Database cancellato con successo.")
                    database.setup_database()
                else:
                    print("Errore durante la cancellazione del file.")
            else:
                print("Cancellazione annullata.")
        elif choice == '0':
            print("Uscita.")
            break
        else:
            print("Scelta non valida.")

if __name__ == '__main__':
    main()