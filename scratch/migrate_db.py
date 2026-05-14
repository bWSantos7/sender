from app import app, db
from sqlalchemy import text

with app.app_context():
    # 1. Tenta adicionar a coluna token na tabela envio_log
    try:
        db.session.execute(text("ALTER TABLE envio_log ADD COLUMN token VARCHAR(64)"))
        db.session.commit()
        print("Coluna 'token' adicionada com sucesso à tabela 'envio_log'.")
    except Exception as e:
        db.session.rollback()
        if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
            print("A coluna 'token' já existe.")
        else:
            print(f"Erro ao adicionar coluna: {e}")

    # 2. Garante que as novas tabelas (User, Anotacao) sejam criadas
    db.create_all()
    print("Verificação de tabelas concluída.")
