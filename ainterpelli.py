import config
import database
import scraper
import llm_processor
import os
import time
import logging
import multiprocessing
from itertools import chain
from rich.console import Console
from rich.table import Table

def setup_main_logging():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(processName)s - %(levelname)s - %(message)s',
        filename='ainterpelli.log',
        filemode='w'
    )

def print_results(rows):
    if not rows:
        print("\nNessun risultato trovato per i criteri selezionati.")
        return

    console = Console()
    current_province = None
    table = None

    for row in rows:
        (id_interpello, nome_scuola, _, citta, provincia, data_fine, cdc, ore, cattedra, _, _) = row
        
        if provincia != current_province:
            if table:
                console.print(table)
            
            table = Table(title=f"\n--- PROVINCIA: {provincia.upper()} ---", show_header=True, header_style="bold magenta", show_lines=True)
            table.add_column("ID", style="dim", width=5)
            table.add_column("Scuola", style="cyan", no_wrap=False, width=40)
            table.add_column("Città", style="green")
            table.add_column("Fine Incarico", style="yellow")
            table.add_column("CDC", style="bold red")
            table.add_column("Ore", style="blue")
            table.add_column("Cattedra", style="purple", no_wrap=False)
            
            current_province = provincia
        
        table.add_row(
            str(id_interpello),
            str(nome_scuola or 'N/D'),
            str(citta or 'N/D'),
            str(data_fine or 'N/D'),
            str(cdc or 'N/D'),
            str(ore or 'N/D'),
            str(cattedra or 'N/D')
        )

    if table:
        console.print(table)

def export_to_pdf(rows):
    if not rows:
        print("Nessun dato da esportare.")
        return

    from reportlab.platypus import SimpleDocTemplate, Table as PdfTable, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import landscape, letter
    from reportlab.lib import colors

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"report_interpelli_{timestamp}.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("Report Interpelli", styles['h1'])
    elements.append(title)
    elements.append(Spacer(1, 12))

    data = [["ID", "Scuola", "Città", "Fine Incarico", "CDC", "Ore", "Cattedra"]]
    
    for row in rows:
        (id_interpello, nome_scuola, _, citta, _, data_fine, cdc, ore, cattedra, _, _) = row
        data.append([
            str(id_interpello),
            str(nome_scuola or 'N/D'),
            str(citta or 'N/D'),
            str(data_fine or 'N/D'),
            str(cdc or 'N/D'),
            str(ore or 'N/D'),
            str(cattedra or 'N/D')
        ])

    pdf_table = PdfTable(data)
    
    style = TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.grey),
        ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0,0), (-1,0), 12),
        ('BACKGROUND', (0,1), (-1,-1), colors.beige),
        ('GRID', (0,0), (-1,-1), 1, colors.black)
    ])
    pdf_table.setStyle(style)
    
    elements.append(pdf_table)
    doc.build(elements)
    
    print(f"\nTabella esportata con successo nel file: {filename}")

def run_database_mode():
    print("\n--- Modalità di Interrogazione Database ---")
    db_conn = database.create_connection()
    if not db_conn:
        print("Impossibile connettersi al database.")
        return
    
    print("\nRecupero tutti gli interpelli salvati (ordinati per Classe di Concorso)...")
    last_displayed_rows = database.get_all_interpelli(db_conn)
    print_results(last_displayed_rows)

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
                    print_results(last_displayed_rows)
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
                    print_results(last_displayed_rows)
                else:
                    print("Inserisci un numero positivo.")
            except ValueError:
                print("Input non valido. Inserisci un numero.")

        elif choice == '3':
            print("\nRecupero tutti gli interpelli salvati...")
            last_displayed_rows = database.get_all_interpelli(db_conn)
            print_results(last_displayed_rows)

        elif choice == '4':
            export_to_pdf(last_displayed_rows)

        elif choice == '0':
            break
        else:
            print("Scelta non valida.")
            
    db_conn.close()

def run_scraping_mode():
    logger = logging.getLogger()
    
    provinces_to_scan = get_provinces_to_scan()
    if not provinces_to_scan:
        return

    max_pages = get_max_pages_to_scan()
    print(f"\nAvvio della ricerca per le province selezionate (max {max_pages} pagine)...")

    filtered_sites_config = {
        province: config.SITES_CONFIG[province] 
        for province in provinces_to_scan
    }

    model_for_main_process = config.setup_gemini()
    if not model_for_main_process:
        logger.error("Controllo preliminare fallito. Assicurarsi che la chiave API sia valida.")
        return

    db_conn = database.create_connection()
    if not db_conn:
        logger.error("Esecuzione interrotta. Impossibile connettersi al database.")
        return

    for provincia, site_info in filtered_sites_config.items():
        print(f"\n--- PROVINCIA DI {provincia.upper()} ---")
        logger.info(f"\nPROVINCIA DI {provincia.upper()}")
        base_url = site_info['url']
        
        for page_num in range(1, max_pages + 1):
            current_url = f"{base_url.rstrip('/')}/page/{page_num}/" if page_num > 1 else base_url
            print(f"\nAnalisi Pagina Elenco {page_num}: {current_url}")
            logger.info(f"\nAnalisi Pagina Elenco {page_num}: {current_url}")
            
            html_content = scraper.get_page_html(current_url)
            if not html_content:
                print(f"Pagina {page_num} non trovata. Fine della scansione per {provincia}.")
                logger.info(f"Pagina {page_num} non trovata. Fine della scansione per {provincia}.")
                break

            article_links = llm_processor.extract_page_links_with_gemini(model_for_main_process, html_content, current_url, logger)
            if not article_links:
                print(f"Nessun articolo trovato in pagina {page_num}. Fine della scansione per {provincia}.")
                logger.info(f"Nessun articolo trovato in pagina {page_num}. Fine della scansione per {provincia}.")
                break

            tasks = [(url, provincia) for url in article_links]
            
            num_processes = min(multiprocessing.cpu_count(), len(tasks))
            print(f"Avvio di un pool di {num_processes} processi per analizzare {len(tasks)} articoli...")
            logger.info(f"Avvio di un pool di {num_processes} processi per analizzare {len(tasks)} articoli...")
            
            pool = multiprocessing.Pool(processes=num_processes)
            try:
                results_from_workers = pool.map(process_single_article, tasks)
                pool.close()
                pool.join()
            except KeyboardInterrupt:
                print("\nInterruzione richiesta dall'utente. Chiusura forzata dei processi...")
                logger.warning("Interruzione richiesta dall'utente. Chiusura forzata dei processi...")
                pool.terminate()
                pool.join()
                break
            
            all_results = list(chain.from_iterable(results_from_workers))
            print(f"Raccolti {len(all_results)} risultati totali dai processi lavoratori.")
            logger.info(f"Raccolti {len(all_results)} risultati totali dai processi lavoratori.")

            for data in all_results:
                database.insert_interpello(db_conn, data)
            
            time.sleep(5)

    db_conn.close()
    print("\nProcesso di scraping e analisi completato!")
    logger.info("\nProcesso di scraping e analisi completato!")

def get_provinces_to_scan():
    provinces = list(config.SITES_CONFIG.keys())
    selected_provinces = []
    
    while True:
        print("\n--- SELEZIONE PROVINCE ---")
        for i, province in enumerate(provinces, 1):
            marker = "[x]" if province in selected_provinces else "[ ]"
            print(f"{i:2}: {marker} {province}")
        
        print("\nProvince selezionate: " + (", ".join(selected_provinces) if selected_provinces else "Nessuna"))
        print("--------------------------")

        try:
            choice_str = input("Inserisci il numero della provincia da aggiungere/rimuovere (0 per avviare la ricerca): ")
            choice = int(choice_str)

            if choice == 0:
                if not selected_provinces:
                    print("Nessuna provincia selezionata. Uscita.")
                    return None
                return selected_provinces
            
            if 1 <= choice <= len(provinces):
                selected_province_name = provinces[choice - 1]
                if selected_province_name in selected_provinces:
                    selected_provinces.remove(selected_province_name)
                else:
                    selected_provinces.append(selected_province_name)
            else:
                print("Scelta non valida. Per favore, inserisci un numero dalla lista.")

        except ValueError:
            print("Input non valido. Per favore, inserisci un numero.")

def get_max_pages_to_scan():
    while True:
        try:
            choice_str = input("\nInserisci il numero massimo di pagine da scansionare per ogni provincia (es. 5): ")
            max_pages = int(choice_str)
            if max_pages > 0:
                return max_pages
            else:
                print("Per favore, inserisci un numero maggiore di zero.")
        except ValueError:
            print("Input non valido. Per favore, inserisci un numero intero.")

def process_single_article(args):
    article_url, provincia = args
    logger = logging.getLogger()
    
    model = config.setup_gemini()
    if not model:
        logger.error(f"Processo per {article_url} non può inizializzare Gemini. Uscita.")
        return []

    all_extracted_data = []
    logger.info(f"Processo per {article_url} avviato.")
    
    html_content_article = scraper.get_page_html(article_url)
    if not html_content_article:
        logger.warning(f"Impossibile recuperare l'HTML dell'articolo: {article_url}")
        return all_extracted_data

    pdf_urls = llm_processor.find_pdf_link_with_gemini(model, html_content_article, article_url, logger)
    
    for pdf_url in pdf_urls:
        pdf_path = scraper.download_file(pdf_url)
        
        if pdf_path:
            extracted_data = llm_processor.process_pdf_with_gemini(model, pdf_path, logger)
            
            if extracted_data:
                if isinstance(extracted_data, list):
                    for item in extracted_data:
                        item['provincia'] = provincia
                        item['url_sorgente'] = pdf_url
                        all_extracted_data.append(item)
                else:
                    extracted_data['provincia'] = provincia
                    extracted_data['url_sorgente'] = pdf_url
                    all_extracted_data.append(extracted_data)
            
            os.remove(pdf_path)
        
        time.sleep(1)
        
    return all_extracted_data

def main():
    setup_main_logging()
    
    database.setup_database()

    while True:
        print("\n--- AInterpelli: Menu Principale ---")
        print(" 1: Interroga il Database Esistente")
        print(" 2: Avvia Scansione e Scraping Nuovi Interpelli")
        print(" 0: Esci")
        choice = input("Scegli un'opzione: ")
        
        if choice == '1':
            run_database_mode()
        elif choice == '2':
            run_scraping_mode()
        elif choice == '0':
            print("Uscita.")
            break
        else:
            print("Scelta non valida.")

if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()