import sys
import time
import asyncio
from collections import defaultdict
from rich.console import Console
from rich.table import Table
from reportlab.platypus import SimpleDocTemplate, Table as PdfTable, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib import colors
import config

class SharedCounter:
    """Un contatore thread-safe per l'ambiente asincrono."""
    def __init__(self):
        self._value = 0
        self._lock = asyncio.Lock()

    async def increment(self):
        async with self._lock:
            self._value += 1

    async def decrement(self):
        async with self._lock:
            self._value -= 1

    async def get_value(self):
        async with self._lock:
            return self._value

def print_results(rows):
    if not rows:
        print("\nNessun risultato trovato per i criteri selezionati.")
        return

    console = Console()
    data_by_province = defaultdict(list)
    for row in rows:
        provincia = row[4]
        data_by_province[provincia].append(row)

    for provincia, province_rows in sorted(data_by_province.items()):
        table = Table(title=f"\n--- PROVINCIA: {provincia.upper()} ---", show_header=True, header_style="bold magenta", show_lines=True)
        table.add_column("ID", style="dim", width=5)
        table.add_column("Scuola", style="cyan", no_wrap=False, width=40)
        table.add_column("Città", style="green")
        table.add_column("Fine Incarico", style="yellow")
        table.add_column("CDC", style="bold red")
        table.add_column("Ore", style="blue")
        table.add_column("Cattedra", style="purple", no_wrap=False)

        for row in province_rows:
            (id_interpello, nome_scuola, _, citta, _, data_fine, cdc, ore, cattedra, _, _) = row
            table.add_row(
                str(id_interpello), str(nome_scuola or 'N/D'), str(citta or 'N/D'),
                str(data_fine or 'N/D'), str(cdc or 'N/D'), str(ore or 'N/D'), str(cattedra or 'N/D')
            )
        console.print(table)

def export_to_pdf(rows):
    if not rows:
        print("Nessun dato da esportare.")
        return

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    filename = f"report_interpelli_{timestamp}.pdf"
    
    doc = SimpleDocTemplate(filename, pagesize=landscape(letter))
    elements = []
    styles = getSampleStyleSheet()
    
    title = Paragraph("Report Interpelli", styles['h1'])
    elements.append(title)
    
    data_by_province = defaultdict(list)
    for row in rows:
        provincia = row[4]
        data_by_province[provincia].append(row)

    for provincia, province_rows in sorted(data_by_province.items()):
        elements.append(Spacer(1, 24))
        prov_title = Paragraph(f"Provincia: {provincia.upper()}", styles['h2'])
        elements.append(prov_title)
        elements.append(Spacer(1, 12))

        data = [["ID", "Scuola", "Città", "Fine Incarico", "CDC", "Ore", "Cattedra"]]
        
        for row in province_rows:
            (id_interpello, nome_scuola, _, citta, _, data_fine, cdc, ore, cattedra, _, _) = row
            data.append([
                str(id_interpello), str(nome_scuola or 'N/D'), str(citta or 'N/D'),
                str(data_fine or 'N/D'), str(cdc or 'N/D'), str(ore or 'N/D'), str(cattedra or 'N/D')
            ])

        pdf_table = PdfTable(data)
        style = TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.grey), ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'), ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
            ('BOTTOMPADDING', (0,0), (-1,0), 12), ('BACKGROUND', (0,1), (-1,-1), colors.beige),
            ('GRID', (0,0), (-1,-1), 1, colors.black)
        ])
        pdf_table.setStyle(style)
        elements.append(pdf_table)
    
    doc.build(elements)
    print(f"\nTabella esportata con successo nel file: {filename}")

async def display_progress(active_tasks_counter, semaphore_limit, phase_name, all_tasks_future):
    spinner_chars = ['|', '/', '-', '\\']
    i = 0
    start_time = time.time()
    
    await asyncio.sleep(0.2) 

    while not all_tasks_future.done() or await active_tasks_counter.get_value() > 0:
        active_count = await active_tasks_counter.get_value()
        
        if all_tasks_future.done() and active_count == 0:
            break
            
        fill_percent = active_count / semaphore_limit if semaphore_limit > 0 else 0
        bar_len = 30
        filled_len = int(bar_len * fill_percent)
        
        yellow = "\033[93m"
        bold = "\033[1m"
        reset = "\033[0m"
        
        bar = f"{yellow}{'=' * filled_len}{' ' * (bar_len - filled_len)}{reset}"
        spinner = spinner_chars[i % len(spinner_chars)]
        i += 1
        
        elapsed_time = time.time() - start_time
        
        status_text = (
            f"\r{spinner} {phase_name}... {bar} "
            f"{bold}Lavoratori Attivi: {active_count} / {semaphore_limit}{reset} "
            f"| Tempo: {elapsed_time:.0f}s"
        )
        
        sys.stdout.write(status_text)
        sys.stdout.flush()
        
        await asyncio.sleep(0.2)
            
    sys.stdout.write("\r" + " " * 120 + "\r")
    sys.stdout.flush()
    print()

def get_provinces_to_scan():
    provinces = list(config.SITES_CONFIG.keys())
    selected_provinces = []
    while True:
        print("\n--- SELEZIONE PROVINCE ---")
        for i, province in enumerate(provinces, 1):
            marker = "[x]" if province in selected_provinces else "[ ]"
            print(f"{i:2}: {marker} {province}")
        
        print("-" * 26)
        print("12: Seleziona tutte le province")
        print("-" * 26)

        print("\nProvince selezionate: " + (", ".join(selected_provinces) if selected_provinces else "Nessuna"))
        print("--------------------------")
        try:
            choice_str = input("Inserisci il numero della provincia da aggiungere/rimuovere (0 per avviare la ricerca): ")
            choice = int(choice_str)

            if choice == 0:
                return selected_provinces if selected_provinces else None
            
            if choice == 12:
                selected_provinces = list(provinces)
                print("Tutte le province sono state selezionate.")
                continue

            if 1 <= choice <= len(provinces):
                selected_province_name = provinces[choice - 1]
                if selected_province_name in selected_provinces:
                    selected_provinces.remove(selected_province_name)
                else:
                    selected_provinces.append(selected_province_name)
            else:
                print("Scelta non valida.")
        except ValueError:
            print("Input non valido.")

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
            print("Input non valido.")