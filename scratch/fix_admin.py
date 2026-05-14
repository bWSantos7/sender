import sys
import os
sys.path.append(os.getcwd())
from app import app, db
from models import User

with app.app_context():
    u = User.query.filter_by(username='admin').first()
    if u:
        u.role = 'admin'
        u.is_admin = True
        db.session.commit()
        print(f"Usuário {u.username} atualizado para ADMIN.")
    else:
        print("Usuário 'admin' não encontrado.")
