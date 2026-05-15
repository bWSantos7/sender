import sys
import os
import json
sys.path.append(os.getcwd())
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from models import db, User, Corretor, Configuracao, LinkForm, EmailConfig, EmpreendimentoSupervisor, FilaUpload, EnvioLog, Anotacao
from flask import Flask

# Configurações
# Substitua pela sua DATABASE_URL do Railway se não estiver no ambiente
DATABASE_URL_POSTGRES = "postgresql://postgres:iFZuoMkmmjGlJYWTWjyYevwhpnsXzOUH@yamabiko.proxy.rlwy.net:31192/railway"

# Caso o Railway use o prefixo antigo postgres://
if DATABASE_URL_POSTGRES.startswith("postgres://"):
    DATABASE_URL_POSTGRES = DATABASE_URL_POSTGRES.replace("postgres://", "postgresql://", 1)

DATABASE_URL_SQLITE = "sqlite:///database.db"

def migrate():
    print("Iniciando ambiente Flask...")
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL_SQLITE
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    print(f"Conectando ao Postgres: {DATABASE_URL_POSTGRES.split('@')[-1]}...")
    try:
        engine_pg = create_engine(DATABASE_URL_POSTGRES, connect_args={'connect_timeout': 10})
        
        with engine_pg.connect() as conn:
            print("Conexão com Postgres estabelecida. Ajustando schema...")
            try:
                conn.execute(text("ALTER TABLE \"user\" ALTER COLUMN password_hash TYPE TEXT"))
                conn.commit()
                print("Coluna password_hash ajustada.")
            except Exception as e:
                print(f"Nota sobre schema: {e}")

        SessionPG = sessionmaker(bind=engine_pg)
        session_pg = SessionPG()
        
        with app.app_context():
            print("Lendo dados do SQLite...")
            modelos = [User, Corretor, Configuracao, LinkForm, EmailConfig, EmpreendimentoSupervisor, FilaUpload, EnvioLog, Anotacao]

            for model in modelos:
                print(f"Migrando {model.__name__}...", end=" ", flush=True)
                items = model.query.all()
                print(f"({len(items)} registros)", end=" ", flush=True)
                
                for item in items:
                    data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
                    new_item = model(**data)
                    session_pg.merge(new_item)
                
                session_pg.commit()
                print("OK")

        print("\n=== MIGRAÇÃO CONCLUÍDA COM SUCESSO ===")
    except Exception as e:
        print(f"\nERRO FATAL NA MIGRAÇÃO: {e}")

if __name__ == "__main__":
    migrate()

if __name__ == "__main__":
    migrate()
