from app import app, db, EnvioLog, Corretor
with app.app_context():
    # Busca o corretor pelo nome (buscando de forma robusta)
    nome_corretor = "2 Irmãos Imoveis"
    corretor = Corretor.query.filter(db.func.lower(Corretor.nome) == nome_corretor.lower()).first()
    
    if corretor:
        # Busca o log específico
        # Como o usuário mostrou uma imagem, vamos filtrar pelo nome do corretor e o tipo
        log = EnvioLog.query.filter_by(corretor_id=corretor.id, tipo="Premiação - Metas").first()
        if log:
            db.session.delete(log)
            db.session.commit()
            print(f"Log de '{nome_corretor}' removido com sucesso.")
        else:
            print(f"Log de '{nome_corretor}' não encontrado.")
    else:
        # Tenta buscar pelo ID 1 (que é usado como fallback no app.py para 'corretor não encontrado')
        log = EnvioLog.query.filter_by(corretor_id=1, tipo="Premiação - Metas").first()
        if log:
            db.session.delete(log)
            db.session.commit()
            print(f"Log de corretor não identificado removido com sucesso.")
        else:
            print("Corretor e log não encontrados.")
