import sqlite3
import os

db_path = 'instance/database.db'
if not os.path.exists(db_path):
    db_path = 'database.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE anotacao ADD COLUMN layout TEXT DEFAULT '{}'")
        print("Coluna 'layout' adicionada com sucesso!")
    except sqlite3.OperationalError as e:
        print(f"Aviso: {e}")
    conn.commit()
    conn.close()
else:
    print("Banco de dados não encontrado localmente.")
