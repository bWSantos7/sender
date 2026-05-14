from app import app, db, Corretor
with app.app_context():
    nome_alvo = "Maria do Desterro Vasconcelos Santos"
    # Busca exata
    c1 = Corretor.query.filter_by(nome=nome_alvo).first()
    # Busca robusta
    c2 = Corretor.query.filter(db.func.lower(Corretor.nome) == nome_alvo.lower()).first()
    # Lista todos parecidos
    similares = Corretor.query.filter(Corretor.nome.ilike(f"%Maria%")).all()
    
    print(f"Busca exata: {'Encontrado' if c1 else 'NÃO encontrado'}")
    print(f"Busca robusta: {'Encontrado' if c2 else 'NÃO encontrado'}")
    print(f"Similares encontrados: {[s.nome for s in similares]}")
