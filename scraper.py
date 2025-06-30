import aiohttp
import os
import time
import re
from bs4 import BeautifulSoup

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

async def get_page_html(session, url):
    print(f"Recupero HTML da: {url}")
    try:
        async with session.get(url, headers=HEADERS, timeout=20) as response:
            if response.status == 404:
                return None
            response.raise_for_status()
            return await response.text()
    except Exception as e:
        print(f"Errore durante il recupero dell'HTML da {url}: {e}")
        return None

def _create_safe_filepath(url, folder):
    if not os.path.exists(folder):
        os.makedirs(folder)
    safe_filename_base = re.sub(r'[^a-zA-Z0-9.]', '_', url.replace("https://", "").replace("http://", ""))
    safe_filename = (safe_filename_base[:150] + '.pdf')
    return os.path.join(folder, safe_filename)

async def download_direct_file(session, url, folder="downloads"):
    final_filepath = _create_safe_filepath(url, folder)
    try:
        print(f"Tentativo di download diretto da: {url}")
        async with session.get(url, headers=HEADERS, timeout=60) as response:
            response.raise_for_status()
            with open(final_filepath, 'wb') as f:
                while True:
                    chunk = await response.content.read(8192)
                    if not chunk:
                        break
                    f.write(chunk)
        print(f"File scaricato con successo in: {final_filepath}")
        return final_filepath
    except Exception as e:
        print(f"Errore durante il download diretto di {url}: {e}")
        return None

async def download_google_drive_file(session, url, folder="downloads"):
    final_filepath = _create_safe_filepath(url, folder)
    
    try:
        match = re.search(r'/file/d/([^/]+)', url)
        if not match:
            print(f"URL Google Drive non valido, ID non trovato: {url}")
            return None
        
        file_id = match.group(1)
        download_url = f'https://drive.google.com/uc?export=download&id={file_id}'
        print(f"Rilevato link Google Drive. URL di download impostato a: {download_url}")

        async with session.get(download_url, timeout=60) as response:
            response.raise_for_status()
            
            content_type = response.headers.get('Content-Type', '')
            if "text/html" in content_type:
                print("Rilevata pagina di conferma di Google Drive. Cerco il link di download finale...")
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                confirm_link_tag = soup.find('a', {'id': 'uc-download-link'})
                if confirm_link_tag and confirm_link_tag.get('href'):
                    confirm_url = confirm_link_tag.get('href')
                    print(f"Trovato link di conferma. Eseguo il download finale da: {confirm_url}")
                    async with session.get(confirm_url, timeout=60) as final_response:
                        final_response.raise_for_status()
                        content = await final_response.read()
                else:
                    print("ERRORE: Impossibile trovare il link di download di conferma.")
                    return None
            else:
                content = await response.read()

        with open(final_filepath, 'wb') as f:
            f.write(content)
        
        print(f"File Google Drive scaricato con successo in: {final_filepath}")
        return final_filepath
        
    except Exception as e:
        print(f"Errore durante il download da Google Drive {url}: {e}")
        return None