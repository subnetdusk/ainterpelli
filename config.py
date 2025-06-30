import os
import google.generativeai as genai
from dotenv import load_dotenv

MODEL_NAME = 'gemini-2.5-pro'

SITES_CONFIG = {
    "Bergamo": {
        "url": "https://bergamo.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Como": {
        "url": "https://como.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Cremona": {
        "url": "https://cremona.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Lecco": {
        "url": "https://lecco.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Lodi": {
        "url": "https://lodi.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Mantova": {
        "url": "https://mantova.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Milano": {
        "url": "https://milano.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Monza e Brianza": {
        "url": "https://monza.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Pavia": {
        "url": "https://pavia.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Sondrio": {
        "url": "https://sondrio.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    },
    "Varese": {
        "url": "https://varese.istruzionelombardia.gov.it/argomento/interpelli-ricerca-supplenti/"
    }
}


def setup_gemini():
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        print("Errore: La chiave API di Gemini non è stata trovata.")
        print('Assicurati di aver creato un file .env e inserito GEMINI_API_KEY="TUA_CHIAVE_API"')
        return None

    print(f"Configurazione di Gemini con il modello: {MODEL_NAME}...")

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(MODEL_NAME)
        print("Configurazione di Gemini completata con successo.")
        return model
    except Exception as e:
        print(f"Errore durante la configurazione di Gemini: {e}")
        print("Verifica che la tua chiave API sia corretta e che tu abbia accesso al modello scelto.")
        return None