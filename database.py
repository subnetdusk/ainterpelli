import sqlite3
from sqlite3 import Error

DB_FILE = "interpelli.sqlite"

def create_connection():
    conn = None
    try:
        conn = sqlite3.connect(DB_FILE)
        return conn
    except Error as e:
        print(f"Errore durante la connessione al database: {e}")
    return conn

def create_table(conn):
    create_table_sql = """
    CREATE TABLE IF NOT EXISTS interpelli (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome_scuola TEXT NOT NULL,
        indirizzo TEXT,
        citta TEXT,
        provincia TEXT NOT NULL,
        data_fine_incarico TEXT,
        classe_di_concorso TEXT,
        numero_di_ore INTEGER,
        tipo_cattedra TEXT,
        url_sorgente TEXT NOT NULL,
        data_inserimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE (nome_scuola, classe_di_concorso, data_fine_incarico)
    );
    """
    try:
        c = conn.cursor()
        c.execute(create_table_sql)
        print("Tabella 'interpelli' creata o già esistente.")
    except Error as e:
        print(f"Errore durante la creazione della tabella: {e}")

def insert_interpello(conn, interpello_data):
    sql = ''' INSERT INTO interpelli(nome_scuola, indirizzo, citta, provincia, data_fine_incarico, classe_di_concorso, numero_di_ore, tipo_cattedra, url_sorgente)
              VALUES(?,?,?,?,?,?,?,?,?) '''
    
    try:
        cur = conn.cursor()
        cur.execute(sql, (
            interpello_data.get('nome_scuola'),
            interpello_data.get('indirizzo'),
            interpello_data.get('citta'),
            interpello_data.get('provincia'),
            interpello_data.get('data_fine_incarico'),
            interpello_data.get('classe_di_concorso'),
            interpello_data.get('numero_di_ore'),
            interpello_data.get('tipo_cattedra'),
            interpello_data.get('url_sorgente')
        ))
        conn.commit()
        print(f"Inserito nuovo interpello per: {interpello_data.get('nome_scuola')}")
        return cur.lastrowid
    except sqlite3.IntegrityError:
        print(f"Record duplicato ignorato per: {interpello_data.get('nome_scuola')}")
        return None
    except Error as e:
        print(f"Errore durante l'inserimento nel database: {e}")
        return None

def setup_database():
    conn = create_connection()
    if conn is not None:
        create_table(conn)
        conn.close()
    else:
        print("Errore! Impossibile creare la connessione al database.")

def get_all_interpelli(conn):
    """Recupera tutti i record, ordinati di default per classe di concorso."""
    cur = conn.cursor()
    # ORDINAMENTO DI DEFAULT AGGIORNATO
    cur.execute("SELECT * FROM interpelli ORDER BY classe_di_concorso, provincia, data_inserimento DESC")
    rows = cur.fetchall()
    return rows

def get_unique_classi_di_concorso(conn):
    """Recupera tutti i valori unici e non nulli di 'classe_di_concorso'."""
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT classe_di_concorso FROM interpelli WHERE classe_di_concorso IS NOT NULL ORDER BY classe_di_concorso")
    rows = [row[0] for row in cur.fetchall()]
    return rows

def get_interpelli_by_filter(conn, filters):
    """Recupera i record in base a un dizionario di filtri (CDC o ore minime)."""
    base_query = "SELECT * FROM interpelli WHERE 1=1"
    params = []

    if 'classe_di_concorso' in filters:
        base_query += " AND classe_di_concorso = ?"
        params.append(filters['classe_di_concorso'])
    
    if 'min_ore' in filters:
        base_query += " AND numero_di_ore >= ?"
        params.append(filters['min_ore'])
    
    base_query += " ORDER BY classe_di_concorso, provincia, data_inserimento DESC"
    
    cur = conn.cursor()
    cur.execute(base_query, params)
    rows = cur.fetchall()
    return rows