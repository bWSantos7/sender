from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta

db = SQLAlchemy()

def brasilia_now():
    return datetime.utcnow() - timedelta(hours=3)

class Corretor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, default="")
    supervisor = db.Column(db.String(120), nullable=False, default="")
    supervisor2 = db.Column(db.String(120), nullable=True)
    
    # Relacionamento com logs
    logs = db.relationship('EnvioLog', backref='corretor', lazy=True)

class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False) # Adiantamento, Repasse, Prêmio
    link_form = db.Column(db.String(300), nullable=True)
    link_form_retroativo = db.Column(db.String(300), nullable=True)
    data_limite_envio = db.Column(db.String(100), nullable=True)
    data_pagamento = db.Column(db.String(100), nullable=True)
    mes_referencia = db.Column(db.String(50), nullable=True)

class EmailConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    smtp_server = db.Column(db.String(120), default="smtp-mail.outlook.com")
    smtp_port = db.Column(db.Integer, default=587)
    smtp_user = db.Column(db.String(120), default="naoresponda.sousaraujo@outlook.com")
    smtp_pass = db.Column(db.String(120), nullable=True)
    from_name = db.Column(db.String(120), default="Construtora Sousa Araújo")

class Supervisor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False, unique=True)
    email = db.Column(db.String(150), nullable=False)

class EmpreendimentoSupervisor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empreendimento = db.Column(db.String(200), nullable=False)
    supervisor = db.Column(db.String(120), nullable=False, default="")
    supervisor2 = db.Column(db.String(120), nullable=True)

class FilaUpload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    corretor_nome = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    caminho_pdf = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default='Pendente') # Pendente, Processando, Concluido, Erro
    empreendimentos = db.Column(db.Text, nullable=True)
    destinatario_email = db.Column(db.Text, nullable=True)
    cc_emails = db.Column(db.Text, nullable=True)

class EnvioLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    corretor_id = db.Column(db.Integer, db.ForeignKey('corretor.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    data_envio = db.Column(db.DateTime, default=brasilia_now)
    status = db.Column(db.String(20), nullable=False)
    mensagem_erro = db.Column(db.Text, nullable=True)
    caminho_anexo = db.Column(db.String(300), nullable=True)
