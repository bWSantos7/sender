import sqlite3
import os

db_path = 'instance/database.db'
if not os.path.exists(db_path):
    db_path = 'database.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Adicionar colunas se não existirem
    tab_cols = {
        'user': ['role', 'regional'],
        'corretor': ['regional'],
        'empreendimento_supervisor': ['regional'],
        'fila_upload': ['regional'],
        'envio_log': ['regional'],
        'anotacao': ['regional']
    }
    
    for table, cols in tab_cols.items():
        for col in cols:
            try:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")
                print(f"Coluna '{col}' adicionada à tabela '{table}'.")
            except sqlite3.OperationalError:
                print(f"Aviso: Coluna '{col}' já existe na tabela '{table}'.")

    # Criar tabela LinkForm
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS link_form (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome VARCHAR(200) NOT NULL,
                link VARCHAR(500) NOT NULL,
                prazo_abertura VARCHAR(100),
                prazo_encerramento VARCHAR(100),
                status VARCHAR(20) DEFAULT 'Ativo',
                regional VARCHAR(50) NOT NULL
            )
        """)
        print("Tabela 'link_form' criada com sucesso.")
    except Exception as e:
        print(f"Erro ao criar tabela link_form: {e}")

    # Atualizar admins existentes
    cursor.execute("UPDATE user SET role = 'admin' WHERE is_admin = 1")
    
    conn.commit()
    conn.close()
else:
    print("Banco de dados não encontrado.")
