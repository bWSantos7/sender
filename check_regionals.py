from app import app
from models import db, EnvioLog

with app.app_context():
    regionais = db.session.query(EnvioLog.regional).distinct().all()
    print("Regionais encontradas nos Logs:")
    for r in regionais:
        print(f"- '{r[0]}'")
    
    logs_count = EnvioLog.query.count()
    print(f"\nTotal de logs no banco: {logs_count}")
