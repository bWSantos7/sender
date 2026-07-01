from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from flask_login import UserMixin
import secrets

db = SQLAlchemy()

def brasilia_now():
    return datetime.utcnow() - timedelta(hours=3)

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    role = db.Column(db.String(20), default='user') # 'admin' ou 'user'
    regional = db.Column(db.String(50), nullable=True) # ALTO TIETE, VALE DO PARAIBA, etc.

class Corretor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False, unique=True)
    email = db.Column(db.String(120), nullable=False, default="")
    supervisor = db.Column(db.String(120), nullable=False, default="")
    supervisor2 = db.Column(db.String(120), nullable=True)
    regional = db.Column(db.String(50), nullable=True)
    logs = db.relationship('EnvioLog', backref='corretor', lazy=True)

class Configuracao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    link_form = db.Column(db.String(300), nullable=True)
    link_form_retroativo = db.Column(db.String(300), nullable=True)
    data_limite_envio = db.Column(db.String(100), nullable=True)
    data_pagamento = db.Column(db.String(100), nullable=True)
    mes_referencia = db.Column(db.String(50), nullable=True)
    custom_message = db.Column(db.Text, nullable=True)
    email_titulo = db.Column(db.String(300), nullable=True)
    email_subtitulo = db.Column(db.String(300), nullable=True)
    email_alerta_amarelo = db.Column(db.Text, nullable=True)
    email_alerta_vermelho = db.Column(db.Text, nullable=True)
    email_rodape = db.Column(db.Text, nullable=True)
    email_cnpjs = db.Column(db.Text, nullable=True)
    email_prazo = db.Column(db.Text, nullable=True)
    email_retroativo_titulo = db.Column(db.Text, nullable=True)
    email_retroativo_texto = db.Column(db.Text, nullable=True)

class AnotacaoAba(db.Model):
    """Abas (planilhas) exibidas na tela de Anotações, configuráveis pelo admin."""
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    link = db.Column(db.Text, nullable=False)
    ordem = db.Column(db.Integer, default=0)

class LinkForm(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(200), nullable=False)
    link = db.Column(db.String(500), nullable=False)
    prazo_abertura = db.Column(db.String(100), nullable=True)
    prazo_encerramento = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), default='Ativo') # Ativo, Inativo, Encerrado
    regional = db.Column(db.String(50), nullable=False)

class EmailConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    smtp_server = db.Column(db.String(120), default="smtp.gmail.com")
    smtp_port = db.Column(db.Integer, default=587)
    smtp_user = db.Column(db.String(120))
    smtp_pass = db.Column(db.String(120), nullable=True)
    from_name = db.Column(db.String(120), default="Construtora Sousa Araújo")

class EmpreendimentoSupervisor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    empreendimento = db.Column(db.String(200), nullable=False)
    supervisor = db.Column(db.String(120), nullable=False, default="")
    supervisor2 = db.Column(db.String(120), nullable=True)
    regional = db.Column(db.String(50), nullable=True)

class FilaUpload(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    corretor_nome = db.Column(db.String(200), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    caminho_pdf = db.Column(db.String(300), nullable=False)
    status = db.Column(db.String(20), default='Pendente')
    empreendimentos = db.Column(db.Text, nullable=True)
    destinatario_email = db.Column(db.Text, nullable=True)
    cc_emails = db.Column(db.Text, nullable=True)
    regional = db.Column(db.String(50), nullable=True)

class EnvioLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    corretor_id = db.Column(db.Integer, db.ForeignKey('corretor.id'), nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    data_envio = db.Column(db.DateTime, default=brasilia_now)
    status = db.Column(db.String(20), nullable=False)
    mensagem_erro = db.Column(db.Text, nullable=True)
    caminho_anexo = db.Column(db.String(300), nullable=True)
    destinatario_email = db.Column(db.Text, nullable=True)
    cc_emails = db.Column(db.Text, nullable=True)
    token = db.Column(db.String(64), unique=True, default=lambda: secrets.token_urlsafe(32))
    regional = db.Column(db.String(50), nullable=True)

class Anotacao(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    data_criacao = db.Column(db.DateTime, default=brasilia_now)
    titulo = db.Column(db.String(200), nullable=False, default="Nova Planilha")
    colunas = db.Column(db.Text, nullable=False, default="[]") # JSON string
    dados = db.Column(db.Text, nullable=False, default="[]")   # JSON string
    layout = db.Column(db.Text, nullable=True, default="{}")   # JSON string para larguras/alturas
    regional = db.Column(db.String(50), nullable=True)
