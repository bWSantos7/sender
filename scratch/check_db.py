from app import app, db, Configuracao
with app.app_context():
    configs = Configuracao.query.all()
    for c in configs:
        print(f"--- {c.tipo} ---")
        print(f"Data Limite: {c.data_limite_envio}")
        print(f"Email Prazo HTML: {c.email_prazo}")
        print("-" * 20)
