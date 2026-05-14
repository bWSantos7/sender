from app import app, db, Configuracao
with app.app_context():
    c = Configuracao.query.filter_by(tipo='Premiação - Metas').first()
    if c:
        print(f"Email Rodapé HTML: {c.email_rodape}")
