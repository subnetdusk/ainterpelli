import requests
import os
import time
import re

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_page_html(url):
    print(f"Recupero HTML da: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        # Se il codice di stato è 404 (Not Found), restituisce None
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il recupero dell'HTML da {url}: {e}")
        return None

def download_file(url, folder="downloads"):
    if not os.path.exists(folder):
        os.makedirs(folder)
    
    try:
        safe_filename_base = re.sub(r'[^a-zA-Z0-9.]', '_', url.replace("https://", "").replace("http://", ""))
        safe_filename = (safe_filename_base[:150] + '.pdf') if not safe_filename_base.endswith('.pdf') else safe_filename_base[:155]
        
        final_filepath = os.path.join(folder, safe_filename)

        print(f"Tentativo di download da: {url}")
        response = requests.get(url, headers=HEADERS, stream=True, timeout=30)
        response.raise_for_status()
        
        with open(final_filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        print(f"File scaricato con successo in: {final_filepath}")
        return final_filepath
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il download di {url}: {e}")
        return None