import threading
import time
import random
from datetime import datetime, timedelta
import os
import io
import zipfile
import json
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Acesso negado: Esta função é exclusiva para administradores.', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function
from models import db, Corretor, Configuracao, EmailConfig, EnvioLog, FilaUpload, EmpreendimentoSupervisor, User, Anotacao, LinkForm
from services.excel_parser import processar_planilha_base
from services.pdf_generator import gerar_pdfs
from services.email_sender import enviar_email_smtp, gerar_html_email
from dotenv import load_dotenv

load_dotenv()

def get_brasilia_time():
    return datetime.utcnow() - timedelta(hours=3)

app = Flask(__name__)

# Controle global de disparos
stop_envio = threading.Event()
thread_ativa = False

app.secret_key = os.getenv('SECRET_KEY', 'sousa_araujo_secreto_saas')
# Suporte a PostgreSQL no Railway ou SQLite local
database_url = os.getenv('DATABASE_URL', 'sqlite:///database.db')
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Inicialização do Banco de Dados (Executa no deploy)
with app.app_context():
    db.create_all()
    if User.query.count() == 0:
        admin_pw = os.getenv('ADMIN_PASSWORD', 'admin123')
        admin = User(
            username='admin',
            password_hash=generate_password_hash(admin_pw),
            role='admin',
            is_admin=True
        )
        db.session.add(admin)
        db.session.commit()

# Mapeamento de Regionais
MAPA_REGIONAIS = {
    "AMETISTA": "GRANDE CAMPINAS",
    "CEREJEIRAS": "VALE DO PARAIBA",
    "CEREJEIRAS II": "VALE DO PARAIBA",
    "DUMONT": "VALE DO PARAIBA",
    "FLORENÇA": "VALE DO PARAIBA",
    "GRAN PORTINARI": "VALE DO PARAIBA",
    "MONET": "GRANDE SÃO PAULO",
    "MONET II": "GRANDE SÃO PAULO",
    "PORTAL DO LAGO": "GRANDE CAMPINAS",
    "RESIDENCIAL MONET": "GRANDE SÃO PAULO",
    "RESIDENCIAL MONET II": "GRANDE SÃO PAULO",
    "RESIDENCIAL TURMALINA": "GRANDE CAMPINAS",
    "SAFIRA I": "GRANDE CAMPINAS",
    "SAFIRA II": "GRANDE CAMPINAS",
    "SOU MAIS DIADEMA": "GRANDE SÃO PAULO",
    "SOU MAIS GUAIANASES": "GRANDE SÃO PAULO",
    "SOU MAIS SUZANO": "ALTO TIETE",
    "SOU MAIS URBAN": "GRANDE SÃO PAULO",
    "SOU PLENO COTIA": "GRANDE SÃO PAULO",
    "SOU PLENO HOME": "ALTO TIETE",
    "SOU PLENO HOME II": "ALTO TIETE",
    "SOU PLENO JACAREI": "VALE DO PARAIBA",
    "SOU PLENO LIFE": "ALTO TIETE",
    "SOU PLENO LIFE II": "ALTO TIETE",
    "SOU PLENO PAISAGE": "GRANDE CAMPINAS",
    "SOU PLENO PAISAGE - HORTOLANDIA": "GRANDE CAMPINAS",
    "SOU PLENO PAISAGE II": "GRANDE CAMPINAS",
    "SOU PLENO VISAGE - HORTOLANDIA": "GRANDE CAMPINAS",
    "SOU SPECIAL MOMENT": "ALTO TIETE",
    "SOU SPECIAL PLACE": "ALTO TIETE",
    "SOU VIVER ALTOS DE SÃO JOSÉ": "VALE DO PARAIBA",
    "SOU VIVER DIADEMA": "GRANDE SÃO PAULO",
    "SOU VIVER DIADEMA II": "GRANDE SÃO PAULO",
    "SOU VIVER ITATIBA I": "GRANDE CAMPINAS",
    "SOU VIVER ITATIBA II": "GRANDE CAMPINAS",
    "SOU VIVER JACAREI": "VALE DO PARAIBA",
    "SOU VIVER JACAREI (DAVI LINO)": "VALE DO PARAIBA",
    "SOU VIVER NOVA ODESSA": "GRANDE CAMPINAS",
    "SOU VIVER POA": "ALTO TIETE",
    "SOU VIVER RAVENNA": "VALE DO PARAIBA",
    "SOU VIVER RAVENNA II": "VALE DO PARAIBA",
    "SOU VIVER ROMA": "VALE DO PARAIBA",
    "SOU VIVER SOROCABA": "GRANDE CAMPINAS",
    "SOU VIVER TAUBATE": "VALE DO PARAIBA",
    "SOU VIVER TAUBATE II": "VALE DO PARAIBA",
    "SOU VIVER UP": "ALTO TIETE",
    "SOU VIVER VERONA": "VALE DO PARAIBA",
    "SOU VIVER VICENZA": "VALE DO PARAIBA",
    "TANGARA II": "VALE DO PARAIBA",
    "TANGARA III": "VALE DO PARAIBA",
    "VIDALIA": "VALE DO PARAIBA",
    "SOU VIVER MILÃO": "GRANDE SÃO PAULO"
}

def get_regional_by_emp(emp_name):
    if not emp_name: return "OUTROS"
    emp_upper = emp_name.upper().strip()
    for key, regional in MAPA_REGIONAIS.items():
        if key in emp_upper:
            return regional
    return "OUTROS"

# Configuração do Login
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message = 'Por favor, faça login para acessar esta página.'
login_manager.login_message_category = 'warning'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()
    # Inicializar configuração padrão se não existir
    if not Configuracao.query.first():
        for tipo in ['Adiantamento', 'Repasse', 'Prêmio', 'Premiação - Metas', 'House', 'Staff']:
            conf = Configuracao(
                tipo=tipo,
                link_form='https://forms.gle/exemplo',
                link_form_retroativo='https://forms.gle/exemplo_retroativo',
                data_limite_envio='15/05 às 15:00',
                data_pagamento='20 e 30',
                mes_referencia='Abril 2026'
            )
            db.session.add(conf)
        db.session.commit()
    
    # Criar usuário admin padrão se não existir
    if not User.query.filter_by(username='admin').first():
        hashed_pw = generate_password_hash('admin123')
        admin = User(username='admin', password_hash=hashed_pw, is_admin=True)
        db.session.add(admin)
        db.session.commit()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Usuário ou senha inválidos.', 'error')
            
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    total_enviados = EnvioLog.query.filter_by(status='Sucesso').count()
    total_erros = EnvioLog.query.filter_by(status='Erro').count()
    ultimos_logs = EnvioLog.query.order_by(EnvioLog.data_envio.desc()).limit(10).all()
    return render_template('dashboard.html', total_enviados=total_enviados, total_erros=total_erros, logs=ultimos_logs)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
@admin_required
def upload():
    if request.method == 'POST':
        tipo_envio = request.form.get('tipo_envio')
        file = request.files.get('planilha')
        
        if not file or (not file.filename.endswith('.xlsx') and not file.filename.endswith('.xls')):
            flash('Por favor, envie um arquivo Excel (.xlsx ou .xls) válido.', 'error')
            return redirect(url_for('upload'))
            
        caminho_temporario = os.path.join(app.root_path, 'uploads', 'temp.xlsx')
        os.makedirs(os.path.dirname(caminho_temporario), exist_ok=True)
        file.save(caminho_temporario)
        
        # Processar
        resultado = processar_planilha_base(caminho_temporario, tipo_envio)
        if not resultado['sucesso']:
            flash(f"Erro ao ler planilha: {resultado.get('erro')}", 'error')
            return redirect(url_for('upload'))
            
        df = resultado['dataframe']
        
        config = Configuracao.query.filter_by(tipo=tipo_envio).first()
        mes_ref = config.mes_referencia if config else 'N/A'
        link_form = config.link_form if config else ''
        
        # Gerar PDFs
        resultado_pdf = gerar_pdfs(df, tipo_envio, mes_ref, link_form)
        if not resultado_pdf['sucesso']:
            flash(f"Ocorreram erros ao gerar alguns PDFs. Verifique os logs.", 'warning')
            
        # Limpar fila anterior e adicionar novos
        FilaUpload.query.delete()
        
        for pdf_data in resultado_pdf['pdfs']:
            corretor_nome = pdf_data['corretor']
            emps = resultado['empreendimentos_por_corretor'].get(corretor_nome, "")
            
            # Resolver email do destinatário
            corretor_nome_clean = corretor_nome.strip()
            c = Corretor.query.filter(db.func.lower(Corretor.nome) == corretor_nome_clean.lower()).first()
            dest_email = c.email if c else None
            
            # Resolver emails dos supervisores em CC
            cc_emails_list = []
            if emps:
                lista_emps = [e.strip() for e in emps.split(',')]
                for emp in lista_emps:
                    if not emp: continue
                    # Busca robusta (Insensível a maiúsculas/minúsculas)
                    emp_sup = EmpreendimentoSupervisor.query.filter(
                        db.func.lower(EmpreendimentoSupervisor.empreendimento) == emp.lower()
                    ).first()
                    
                    # Se não achar exato, tenta busca parcial (ex: "SAFIRA" achar "SAFIRA I")
                    if not emp_sup:
                        emp_sup = EmpreendimentoSupervisor.query.filter(
                            EmpreendimentoSupervisor.empreendimento.ilike(f"%{emp}%")
                        ).first()

                    if emp_sup:
                        if emp_sup.supervisor and '@' in emp_sup.supervisor and emp_sup.supervisor not in cc_emails_list:
                            cc_emails_list.append(emp_sup.supervisor.strip())
                        if emp_sup.supervisor2 and '@' in emp_sup.supervisor2 and emp_sup.supervisor2 not in cc_emails_list:
                            cc_emails_list.append(emp_sup.supervisor2.strip())
                        
            # Detectar Regional (Pega a regional do primeiro empreendimento da lista)
            regional_item = "OUTROS"
            if emps:
                primeiro_emp = emps.split(',')[0].strip()
                regional_item = get_regional_by_emp(primeiro_emp)

            cc_emails_str = ", ".join(cc_emails_list) if cc_emails_list else None
            
            novo_fila = FilaUpload(
                corretor_nome=corretor_nome,
                tipo=tipo_envio,
                caminho_pdf=pdf_data['caminho_relativo'],
                empreendimentos=emps,
                destinatario_email=dest_email,
                cc_emails=cc_emails_str,
                regional=regional_item
            )
            db.session.add(novo_fila)
        
        db.session.commit()
        
        # Apagar temp
        if os.path.exists(caminho_temporario):
            import time
            for _ in range(5): # Tenta 5 vezes
                try:
                    os.remove(caminho_temporario)
                    break
                except PermissionError:
                    time.sleep(0.5)
                except:
                    break
            
        flash(f"Planilha processada com sucesso! {len(resultado_pdf['pdfs'])} PDFs gerados. Verifique a fila de envio.", 'success')
        return redirect(url_for('fila'))

    return render_template('upload.html')

@app.route('/fila')
@login_required
@admin_required
def fila():
    query_fila = FilaUpload.query
    if current_user.role != 'admin':
        query_fila = query_fila.filter_by(regional=current_user.regional)
    itens_fila = query_fila.all()
    # Identificar se o corretor existe no banco para vincular email
    fila_com_dados = []
    for item in itens_fila:
        # Busca robusta para exibir na fila
        corretor = Corretor.query.filter(db.func.lower(Corretor.nome) == item.corretor_nome.lower().strip()).first()
        
        # Buscar última mensagem de erro se o status for Erro
        erro_msg = None
        if item.status == 'Erro':
            ultimo_log = EnvioLog.query.filter_by(corretor_id=corretor.id if corretor else 1, tipo=item.tipo).order_by(EnvioLog.data_envio.desc()).first()
            if ultimo_log:
                erro_msg = ultimo_log.mensagem_erro

        fila_com_dados.append({
            'fila': item,
            'corretor': corretor,
            'erro_msg': erro_msg
        })
    return render_template('fila.html', fila=fila_com_dados)

@app.route('/importar_corretores', methods=['POST'])
@login_required
@admin_required
def importar_corretores():
    file = request.files.get('file_corretores')
    if not file:
        flash('Arquivo não enviado.', 'error')
        return redirect(url_for('configuracoes'))
    
    try:
        df = pd.read_excel(file, sheet_name='dados_colaboradores', engine='openpyxl')
    except Exception:
        try:
            df = pd.read_excel(file, engine='openpyxl') # Tenta primeira aba
        except Exception as e:
            flash(f'Erro ao ler arquivo: {str(e)}', 'error')
            return redirect(url_for('configuracoes'))

    # Espera-se colunas parecidas com NOME, EMAIL, SUPERVISOR
    colunas_map = {c.upper().strip(): c for c in df.columns}
    
    if 'NOME' not in colunas_map or 'EMAIL' not in colunas_map:
        flash('Planilha deve conter as colunas NOME e EMAIL.', 'error')
        return redirect(url_for('configuracoes'))
        
    inseridos = 0
    atualizados = 0
    processados = set()
    
    for _, row in df.iterrows():
        if pd.isna(row[colunas_map['NOME']]): continue
        nome = str(row[colunas_map['NOME']]).strip()
        email = str(row[colunas_map['EMAIL']]).strip()
        sup_col = colunas_map.get('SUPERVISOR')
        supervisor = str(row[sup_col]).strip() if sup_col and pd.notna(row[sup_col]) else 'sousaaraujo.contato@gmail.com'
        
        reg_col = colunas_map.get('REGIONAL')
        regional = str(row[reg_col]).strip().upper() if reg_col and pd.notna(row[reg_col]) else None
        
        c = Corretor.query.filter_by(nome=nome).first()
        if not c:
            c = Corretor(nome=nome, email=email, supervisor=supervisor, regional=regional)
            db.session.add(c)
            inseridos += 1
        else:
            c.email = email
            c.supervisor = supervisor
            if regional: c.regional = regional
            atualizados += 1
        processados.add(nome)
            
    db.session.commit()
    flash(f'Planilha lida! {inseridos} novos corretores cadastrados e {atualizados} atualizados. (Total: {inseridos + atualizados} únicos)', 'success')
    return redirect(url_for('configuracoes'))

@app.route('/importar_supervisores', methods=['POST'])
@login_required
@admin_required
def importar_supervisores():
    file = request.files.get('file_supervisores')
    if not file:
        flash('Arquivo não enviado.', 'error')
        return redirect(url_for('configuracoes'))
    
    try:
        df = pd.read_excel(file, sheet_name='tabel_supervisor', engine='openpyxl')
    except Exception:
        try:
            df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            flash(f'Erro ao ler arquivo: {str(e)}', 'error')
            return redirect(url_for('configuracoes'))

    # Limpar tabela antes de importar novo arquivo
    try:
        query_del = EmpreendimentoSupervisor.query
        if current_user.role != 'admin':
            query_del = query_del.filter_by(regional=current_user.regional)
        query_del.delete()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao limpar tabela base: {str(e)}', 'error')
        return redirect(url_for('configuracoes'))

    colunas_map = {c.upper().strip(): c for c in df.columns}
    
    if 'EMPREENDIMENTO' not in colunas_map or 'SUPERVISOR' not in colunas_map:
        flash('Planilha deve conter as colunas EMPREENDIMENTO e SUPERVISOR.', 'error')
        return redirect(url_for('configuracoes'))
        
    inseridos = 0
    atualizados = 0
    processed_emps = {}

    for i, row in df.iterrows():
        try:
            emp_raw = row[colunas_map['EMPREENDIMENTO']]
            if pd.isna(emp_raw): continue
            emp = str(emp_raw).strip()
            if not emp or emp.lower() == 'nan': continue
            
            sup = str(row[colunas_map['SUPERVISOR']]).strip() if pd.notna(row[colunas_map['SUPERVISOR']]) else None
            sup2_col = colunas_map.get('SUPERVISOR 2') or colunas_map.get('SUPERVISOR2')
            sup2 = str(row[sup2_col]).strip() if sup2_col and pd.notna(row[sup2_col]) else None
            
            regional = get_regional_by_emp(emp)
            
            if emp in processed_emps:
                es = processed_emps[emp]
                es.supervisor = sup
                es.supervisor2 = sup2
                atualizados += 1
            else:
                es = EmpreendimentoSupervisor(empreendimento=emp, supervisor=sup, supervisor2=sup2, regional=regional)
                db.session.add(es)
                processed_emps[emp] = es
                inseridos += 1
        except Exception as e:
            continue
            
    db.session.commit()
    flash(f'Tabela de Empreendimentos atualizada! {inseridos} empreendimentos processados.', 'success')
    return redirect(url_for('configuracoes'))

@app.route('/zerar_supervisores', methods=['POST'])
def zerar_supervisores():
    try:
        query_del = EmpreendimentoSupervisor.query
        if current_user.role != 'admin':
            query_del = query_del.filter_by(regional=current_user.regional)
        query_del.delete()
        db.session.commit()
        flash('Tabela de supervisores zerada com sucesso.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao zerar tabela: {str(e)}', 'error')
    return redirect(url_for('configuracoes'))

# Função rodando em thread separada
def processar_fila_background():
    global thread_ativa
    thread_ativa = True
    stop_envio.clear()
    
    with app.app_context():
        # Processar tanto Pendentes quanto os que deram Erro anteriormente
        from sqlalchemy import or_
        itens = FilaUpload.query.filter(or_(FilaUpload.status == 'Pendente', FilaUpload.status == 'Erro')).all()
        for item in itens:
            # Verificar se foi solicitado para parar
            if stop_envio.is_set():
                break
                
            item.status = 'Processando'
            db.session.commit()
            
            # Busca robusta (insensível a maiúsculas/minúsculas)
            corretor = Corretor.query.filter(db.func.lower(Corretor.nome) == item.corretor_nome.lower().strip()).first()
            if not corretor:
                item.status = 'Erro'
                log = EnvioLog(corretor_id=1, tipo=item.tipo, status='Erro', mensagem_erro='Corretor não encontrado no banco', caminho_anexo=item.caminho_pdf, regional=item.regional)
                db.session.add(log)
                db.session.commit()
                continue
                
            # Pré-validações de disparo
            if not item.destinatario_email or '@' not in item.destinatario_email:
                item.status = 'Erro'
                log = EnvioLog(corretor_id=corretor.id, tipo=item.tipo, status='Erro', mensagem_erro='E-mail do destinatário ausente ou inválido', caminho_anexo=item.caminho_pdf, regional=item.regional)
                db.session.add(log)
                db.session.commit()
                continue
                
            config = Configuracao.query.filter_by(tipo=item.tipo).first()
            if not config:
                config_dict = {'tipo': item.tipo}
            else:
                config_dict = {
                    'tipo': config.tipo,
                    'link_form': config.link_form,
                    'link_form_retroativo': config.link_form_retroativo,
                    'data_limite_envio': config.data_limite_envio,
                    'data_pagamento': config.data_pagamento,
                    'mes_referencia': config.mes_referencia
                }
                
            log = EnvioLog(
                corretor_id=corretor.id,
                tipo=item.tipo,
                status='Processando',
                caminho_anexo=item.caminho_pdf,
                regional=item.regional
            )
            db.session.add(log)
            db.session.commit()

            # Resolver caminho do anexo (Suporte a caminhos antigos e novos)
            anexo_path = item.caminho_pdf
            if '\\' in anexo_path or ':' in anexo_path:
                # Caminho antigo do Windows - pega só o nome do arquivo
                nome_f = anexo_path.replace('\\', '/').split('/')[-1]
                anexo_path = os.path.join(app.root_path, 'uploads', item.tipo.lower(), nome_f)
            elif not os.path.isabs(anexo_path):
                anexo_path = os.path.join(app.root_path, 'uploads', anexo_path)

            sucesso, msg = enviar_email_smtp(
                email_colaborador=item.destinatario_email,
                nome_colaborador=item.corretor_nome,
                supervisor=item.cc_emails,
                supervisor2=None,
                anexo_pdf=anexo_path,
                config=config_dict,
                token=log.token
            )
            
            log.status = 'Sucesso' if sucesso else 'Erro'
            log.mensagem_erro = msg if not sucesso else None
            item.status = 'Concluido' if sucesso else 'Erro'
            db.session.commit()
            
            time.sleep(random.uniform(5, 8)) # Pausa segura entre 5 e 8 segundos para evitar bloqueios do Google
            
    thread_ativa = False

@app.route('/api/status_envio')
def status_envio():
    query_log = EnvioLog.query
    query_fila = FilaUpload.query

    # Indicadores históricos (Dashboard)
    total_sucesso = query_log.filter_by(status='Sucesso').count()
    total_erro = query_log.filter_by(status='Erro').count()
    
    # Indicadores da fila atual
    pendentes = query_fila.filter_by(status='Pendente').count()
    processando = query_fila.filter_by(status='Processando').count()
    concluidos = query_fila.filter_by(status='Concluido').count()
    erros = query_fila.filter_by(status='Erro').count()
    total = query_fila.count()
    
    # Logs recentes
    logs_data = []
    for l in query_log.order_by(EnvioLog.data_envio.desc()).limit(10).all():
        logs_data.append({
            'corretor': l.corretor.nome if l.corretor else 'Desconhecido',
            'email': l.destinatario_email or (l.corretor.email if l.corretor else ''),
            'cc': l.cc_emails or '',
            'tipo': l.tipo,
            'data': l.data_envio.strftime('%d/%m/%Y %H:%M'),
            'status': l.status,
            'erro': l.mensagem_erro or '',
            'caminho_anexo': l.caminho_anexo or ''
        })
    
    return jsonify({
        'concluidos': total_sucesso,
        'erros': total_erro,
        'pendentes': pendentes,
        'processando': processando,
        'fila_concluidos': concluidos,
        'fila_erros': erros,
        'total': total,
        'progresso': int((concluidos + erros) / total * 100) if total > 0 else 0,
        'logs': logs_data,
        'ativo': thread_ativa
    })

@app.route('/limpar_logs', methods=['POST'])
def limpar_logs():
    try:
        query_del = EnvioLog.query
        if current_user.role != 'admin':
            query_del = query_del.filter_by(regional=current_user.regional)
        query_del.delete()
        db.session.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/parar_envios', methods=['POST'])
@login_required
@admin_required
def parar_envios():
    stop_envio.set()
    return jsonify({'sucesso': True, 'mensagem': 'Solicitação de parada enviada.'})

@app.route('/iniciar_envios', methods=['POST'])
@login_required
@admin_required
def iniciar_envios():
    global thread_ativa
    if thread_ativa:
        return jsonify({'sucesso': False, 'erro': 'Já existe um envio em andamento.'}), 400
        
    thread = threading.Thread(target=processar_fila_background)
    thread.start()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
        return jsonify({'sucesso': True, 'mensagem': 'Disparos iniciados!'})
        
    flash('Envios iniciados em segundo plano. Acompanhe pelo Dashboard.', 'success')
    return redirect(url_for('fila'))

@app.route('/limpar_fila', methods=['POST'])
@login_required
@admin_required
def limpar_fila():
    try:
        query_del = FilaUpload.query
        if current_user.role != 'admin':
            query_del = query_del.filter_by(regional=current_user.regional)
        query_del.delete()
        db.session.commit()
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'sucesso': True, 'mensagem': 'Fila limpa com sucesso!'})
        flash('Fila de envios limpa com sucesso!', 'success')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json:
            return jsonify({'sucesso': False, 'erro': str(e)}), 500
        flash(f'Erro ao limpar fila: {str(e)}', 'error')
    return redirect(url_for('fila'))

@app.route('/api/atualizar_email', methods=['POST'])
@login_required
@admin_required
def atualizar_email():
    try:
        data = request.json
        nome = data.get('nome', '').strip()
        email = data.get('email', '').strip()
        
        if not nome or not email:
            return jsonify({'sucesso': False, 'erro': 'Nome e E-mail são obrigatórios.'}), 400
            
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({'sucesso': False, 'erro': 'Formato de e-mail inválido.'}), 400
            
        # Buscar corretor (Busca robusta)
        c = Corretor.query.filter(db.func.lower(Corretor.nome) == nome.lower()).first()
        criado_novo = False
        
        if not c:
            # Criar novo corretor
            c = Corretor(nome=nome, email=email, supervisor='', supervisor2='', regional=current_user.regional)
            db.session.add(c)
            criado_novo = True
        else:
            c.email = email
            
        # Atualizar todos os itens na fila para este beneficiário
        itens_fila = FilaUpload.query.filter_by(corretor_nome=nome).all()
        for item in itens_fila:
            item.destinatario_email = email
            # Se estava com erro por falta de e-mail, agora está pronto para envio
            if item.status == 'Erro':
                item.status = 'Pendente'
                
        db.session.commit()
        return jsonify({
            'sucesso': True, 
            'email': email, 
            'status': 'Criado' if criado_novo else 'Atualizado',
            'mensagem': 'Corretor criado com sucesso!' if criado_novo else 'E-mail atualizado com sucesso!'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': f'Erro interno: {str(e)}'}), 500

@app.route('/api/enviar_unidade', methods=['POST'])
def enviar_unidade():
    try:
        data = request.json
        fila_id = data.get('id')
        
        item = FilaUpload.query.get(fila_id)
        if not item:
            return jsonify({'sucesso': False, 'erro': 'Item não encontrado na fila.'}), 404
            
        # Busca robusta do corretor
        corretor = Corretor.query.filter(db.func.lower(Corretor.nome) == item.corretor_nome.lower().strip()).first()
        if not corretor:
            return jsonify({'sucesso': False, 'erro': 'Corretor não encontrado no banco de dados.'}), 404

        if not item.destinatario_email or '@' not in item.destinatario_email:
            return jsonify({'sucesso': False, 'erro': 'E-mail do destinatário ausente ou inválido.'}), 400

        item.status = 'Processando'
        db.session.commit()
        
        config = Configuracao.query.filter_by(tipo=item.tipo).first()
        config_dict = {
            'tipo': config.tipo if config else item.tipo,
            'link_form': config.link_form if config else '',
            'link_form_retroativo': config.link_form_retroativo if config else '',
            'data_limite_envio': config.data_limite_envio if config else '',
            'data_pagamento': config.data_pagamento if config else '',
            'mes_referencia': config.mes_referencia if config else '',
            'custom_message': config.custom_message if config else None,
            'email_titulo': config.email_titulo if config else None,
            'email_subtitulo': config.email_subtitulo if config else None,
            'email_alerta_amarelo': config.email_alerta_amarelo if config else None,
            'email_alerta_vermelho': config.email_alerta_vermelho if config else None,
            'email_rodape': config.email_rodape if config else None,
            'email_cnpjs': config.email_cnpjs if config else None,
            'email_prazo': config.email_prazo if config else None,
            'email_retroativo_titulo': config.email_retroativo_titulo if config else None,
            'email_retroativo_texto': config.email_retroativo_texto if config else None
        }

        log = EnvioLog(
            corretor_id=corretor.id,
            tipo=item.tipo,
            status='Processando',
            caminho_anexo=item.caminho_pdf,
            destinatario_email=item.destinatario_email,
            cc_emails=item.cc_emails,
            regional=item.regional
        )
        db.session.add(log)
        db.session.commit()

        # Resolver caminho do anexo
        anexo_path = item.caminho_pdf
        if '\\' in anexo_path or ':' in anexo_path:
            nome_f = anexo_path.replace('\\', '/').split('/')[-1]
            anexo_path = os.path.join(app.root_path, 'uploads', item.tipo.lower(), nome_f)
        elif not os.path.isabs(anexo_path):
            anexo_path = os.path.join(app.root_path, 'uploads', anexo_path)

        sucesso, msg = enviar_email_smtp(
            email_colaborador=item.destinatario_email,
            nome_colaborador=item.corretor_nome,
            supervisor=item.cc_emails,
            supervisor2=None,
            anexo_pdf=anexo_path,
            config=config_dict,
            token=log.token
        )
        
        log.status = 'Sucesso' if sucesso else 'Erro'
        log.mensagem_erro = msg if not sucesso else None
        item.status = 'Concluido' if sucesso else 'Erro'
        db.session.commit()
        
        return jsonify({'sucesso': sucesso, 'mensagem': msg})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': f'Erro interno: {str(e)}'}), 500

@app.route('/corretores_lista')
@login_required
def corretores_lista():
    corretores = Corretor.query.all()
    supervisores = EmpreendimentoSupervisor.query.all()
    return render_template('configuracoes_view.html', corretores=corretores, supervisores=supervisores)

@app.route('/configuracoes', methods=['GET', 'POST'])
@login_required
def configuracoes():
    if current_user.role != 'admin':
        return redirect(url_for('corretores_lista'))

    # Admin tem acesso total
    email_conf = EmailConfig.query.first()
    if not email_conf:
        email_conf = EmailConfig()
        db.session.add(email_conf)
        db.session.commit()

    # Garantir que todos os tipos de configuração existem
    for tipo in ['Adiantamento', 'Repasse', 'Prêmio', 'Premiação - Metas', 'House', 'Staff']:
        if not Configuracao.query.filter_by(tipo=tipo).first():
            db.session.add(Configuracao(tipo=tipo))
    db.session.commit()

    if request.method == 'POST':
        section_type = request.form.get('section_type')
        
        if section_type == 'smtp':
            # Atualizar Config de Email
            if request.form.get('smtp_user'):
                email_conf.smtp_server = request.form.get('smtp_server')
                email_conf.smtp_port = int(request.form.get('smtp_port') or 587)
                email_conf.smtp_user = request.form.get('smtp_user')
                if request.form.get('smtp_pass'):
                    email_conf.smtp_pass = request.form.get('smtp_pass')
                email_conf.from_name = request.form.get('from_name')
                db.session.commit()
                flash('Servidor de e-mail atualizado com sucesso.', 'success')
        
        elif section_type == 'config_tipo':
            tipo = request.form.get('tipo_alvo')
            conf = Configuracao.query.filter_by(tipo=tipo).first()
            if conf:
                old_date = conf.data_limite_envio
                old_pgto = conf.data_pagamento
                old_mes = conf.mes_referencia
                
                new_date = request.form.get("data_limite_envio")
                new_pgto = request.form.get("data_pagamento")
                new_mes = request.form.get("mes_referencia")

                conf.link_form = request.form.get("link_form")
                conf.link_form_retroativo = request.form.get("link_form_retroativo")
                conf.data_limite_envio = new_date
                conf.data_pagamento = new_pgto
                conf.mes_referencia = new_mes

                # Sincronizar com o HTML customizado se ele existir
                if conf.email_prazo and old_date and old_date != new_date:
                    conf.email_prazo = conf.email_prazo.replace(old_date, new_date)
                
                if conf.email_rodape and old_pgto and old_pgto != new_pgto:
                    conf.email_rodape = conf.email_rodape.replace(old_pgto, new_pgto)

                if conf.email_titulo and old_mes and old_mes != new_mes:
                    conf.email_titulo = conf.email_titulo.replace(old_mes, new_mes)

                db.session.commit()
                flash(f'Configurações de {tipo} salvas com sucesso.', 'success')

        return redirect(url_for('configuracoes'))
        
    configs = Configuracao.query.all()
    corretores_count = Corretor.query.count()
    
    # Contar supervisores únicos
    sup_emails = set()
    for es in EmpreendimentoSupervisor.query.all():
        if es.supervisor and '@' in es.supervisor: sup_emails.add(es.supervisor.strip())
        if es.supervisor2 and '@' in es.supervisor2: sup_emails.add(es.supervisor2.strip())
    supervisores_count = len(sup_emails)
    
    return render_template('configuracoes.html', 
                         configs=configs, 
                         corretores_count=corretores_count, 
                         supervisores_count=supervisores_count,
                         email_conf=email_conf)

@app.route('/colaboradores')
@login_required
def colaboradores():
    corretores = Corretor.query.all()
    empreendimentos = EmpreendimentoSupervisor.query.all()
    return render_template('colaboradores.html', corretores=corretores, empreendimentos=empreendimentos)

@app.route('/arquivos')
def arquivos():
    base_uploads = os.path.join(app.root_path, 'uploads')
    lista_arquivos = []
    
    if os.path.exists(base_uploads):
        for root, dirs, files in os.walk(base_uploads):
            for file in files:
                if file == '.gitkeep': continue
                caminho_completo = os.path.join(root, file)
                rel_path = os.path.relpath(caminho_completo, base_uploads)
                tipo = os.path.dirname(rel_path) or 'Raiz'
                stats = os.stat(caminho_completo)
                
                lista_arquivos.append({
                    'nome': file,
                    'caminho': rel_path.replace('\\', '/'),
                    'tipo': tipo.capitalize(),
                    'tamanho': f"{stats.st_size / 1024:.1f} KB",
                    'data': datetime.fromtimestamp(stats.st_mtime).strftime('%d/%m/%Y %H:%M')
                })
                
    return render_template('arquivos.html', arquivos=lista_arquivos)


@app.route('/api/excluir_arquivos', methods=['POST'])
def excluir_arquivos():
    data = request.json
    selecionados = data.get('arquivos', [])
    base_uploads = os.path.join(app.root_path, 'uploads')
    sucesso = 0
    erros = 0
    
    for rel_path in selecionados:
        try:
            caminho = os.path.join(base_uploads, rel_path)
            if os.path.exists(caminho):
                os.remove(caminho)
                sucesso += 1
        except:
            erros += 1
            
    return jsonify({'sucesso': True, 'mensagem': f'{sucesso} arquivos excluídos, {erros} erros.'})

@app.route('/api/visualizar_arquivo/<path:filename>')
def visualizar_arquivo(filename):
    from flask import send_file
    base_uploads = os.path.join(app.root_path, 'uploads')
    caminho = os.path.join(base_uploads, filename)
    if os.path.exists(caminho):
        return send_file(caminho)
    return "Arquivo não encontrado", 404

@app.route('/api/upload_manual', methods=['POST'])
def upload_manual():
    tipo = request.form.get('tipo', 'Outros').lower()
    files = request.files.getlist('files')
    
    if not files or files[0].filename == '':
        return jsonify({'sucesso': False, 'erro': 'Nenhum arquivo selecionado.'}), 400
        
    base_uploads = os.path.join(app.root_path, 'uploads', tipo)
    os.makedirs(base_uploads, exist_ok=True)
    
    sucesso = 0
    for file in files:
        if file.filename:
            file.save(os.path.join(base_uploads, file.filename))
            sucesso += 1
            
    return jsonify({'sucesso': True, 'mensagem': f'{sucesso} arquivos enviados com sucesso.'})

@app.route('/api/download_massa')
def download_massa():
    import zipfile
    import io
    from flask import send_file
    
    selecionados = request.args.getlist('arquivos')
    if not selecionados:
        return "Nenhum arquivo selecionado", 400
        
    base_uploads = os.path.join(app.root_path, 'uploads')
    memory_file = io.BytesIO()
    
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for rel_path in selecionados:
            caminho = os.path.join(base_uploads, rel_path)
            if os.path.exists(caminho):
                # Organizar por pastas dentro do ZIP (Capitalizando o nome da pasta)
                partes = rel_path.split('/')
                if len(partes) > 1:
                    partes[0] = partes[0].capitalize()
                nome_no_zip = '/'.join(partes)
                zf.write(caminho, arcname=nome_no_zip)
                
    memory_file.seek(0)
    return send_file(memory_file, 
                     mimetype='application/zip',
                     as_attachment=True,
                     download_name=f'arquivos_comissao_{datetime.now().strftime("%d%m%Y_%H%M")}.zip')

@app.route('/api/editar_corretor', methods=['POST'])
def editar_corretor():
    data = request.json
    corretor_id = data.get('id')
    
    if corretor_id:
        corretor = Corretor.query.get(corretor_id)
        if not corretor:
            return jsonify({'sucesso': False, 'erro': 'Corretor não encontrado.'}), 404
    else:
        corretor = Corretor()
        db.session.add(corretor)
        
    corretor.nome = data.get('nome')
    corretor.email = data.get('email')
    corretor.supervisor = data.get('supervisor')

    if not corretor.regional:
        corretor.regional = data.get('regional') or current_user.regional
    
    # Se não for admin, força a regional do usuário
    if current_user.role != 'admin':
        corretor.regional = current_user.regional

    try:
        db.session.commit()
        return jsonify({'sucesso': True, 'id': corretor.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/editar_empreendimento', methods=['POST'])
def editar_empreendimento():
    data = request.json
    emp_id = data.get('id')
    
    if emp_id:
        emp = EmpreendimentoSupervisor.query.get(emp_id)
        if not emp:
            return jsonify({'sucesso': False, 'erro': 'Empreendimento não encontrado.'}), 404
    else:
        # Criar novo se não houver ID
        emp = EmpreendimentoSupervisor()
        emp.empreendimento = data.get('empreendimento')
        db.session.add(emp)
        
    emp.supervisor = data.get('supervisor')
    emp.supervisor2 = data.get('supervisor2')
    
    if not emp.regional:
        emp.regional = data.get('regional') or current_user.regional
        
    # Se não for admin, força a regional do usuário
    if current_user.role != 'admin':
        emp.regional = current_user.regional
    
    try:
        db.session.commit()
        return jsonify({'sucesso': True, 'id': emp.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/salvar_template', methods=['POST'])
def salvar_template():
    try:
        data = request.json
        tipo = data.get('tipo')
        conf = Configuracao.query.filter_by(tipo=tipo).first()
        if not conf:
            conf = Configuracao(tipo=tipo)
            db.session.add(conf)
        
        conf.email_titulo = data.get('titulo')
        conf.email_subtitulo = data.get('subtitulo')
        conf.email_alerta_amarelo = data.get('alerta_amarelo')
        conf.email_alerta_vermelho = data.get('alerta_vermelho')
        conf.custom_message = data.get('corpo')
        conf.email_rodape = data.get('rodape')
        conf.email_cnpjs = data.get('cnpjs')
        conf.email_prazo = data.get('prazo')
        conf.email_retroativo_titulo = data.get('retroativo_titulo')
        conf.email_retroativo_texto = data.get('retroativo_texto')
        
        db.session.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/v/<token>')
def view_email(token):
    log = EnvioLog.query.filter_by(token=token).first()
    if not log:
        return "Mensagem não encontrada.", 404
        
    corretor_nome = log.corretor.nome if log.corretor else "Colaborador"
    config = Configuracao.query.filter_by(tipo=log.tipo).first()
    
    # Simular config dict para o gerador
    config_dict = {
        'tipo': log.tipo,
        'link_form': config.link_form if config else '#',
        'link_form_retroativo': config.link_form_retroativo if config else '#',
        'data_limite_envio': config.data_limite_envio if config else '',
        'data_pagamento': config.data_pagamento if config else '',
        'mes_referencia': config.mes_referencia if config else '',
        'custom_message': config.custom_message if config else None,
        'email_titulo': config.email_titulo if config else None,
        'email_subtitulo': config.email_subtitulo if config else None,
        'email_alerta_amarelo': config.email_alerta_amarelo if config else None,
        'email_alerta_vermelho': config.email_alerta_vermelho if config else None,
        'email_rodape': config.email_rodape if config else None,
        'email_cnpjs': config.email_cnpjs if config else None,
        'email_prazo': config.email_prazo if config else None,
        'email_retroativo_titulo': config.email_retroativo_titulo if config else None,
        'email_retroativo_texto': config.email_retroativo_texto if config else None
    }
    
    email_html = gerar_html_email(corretor_nome, log.tipo, config_dict)
    return email_html

@app.route('/anotacoes')
@login_required
def anotacoes():
    # Removido filtro de regional para que todos vejam as planilhas gerais
    lista_db = Anotacao.query.order_by(Anotacao.data_criacao.desc()).all()
    anotacoes = []
    for a in lista_db:
        try:
            cols = json.loads(a.colunas) if a.colunas else []
            rows = json.loads(a.dados) if a.dados else []
            layout = json.loads(a.layout) if a.layout else {}
        except:
            cols = []
            rows = []
            layout = {}
            
        anotacoes.append({
            'id': a.id,
            'titulo': a.titulo,
            'colunas': cols,
            'dados': rows,
            'layout': layout
        })
    return render_template('anotacoes.html', anotacoes=anotacoes)

@app.route('/api/anotacoes', methods=['POST'])
@login_required
@admin_required
def salvar_anotacao():
    data = request.json
    id_planilha = data.get('id')
    
    titulo = data.get('titulo', 'Nova Planilha')
    colunas = json.dumps(data.get('colunas', []))
    dados = json.dumps(data.get('dados', []))
    layout = json.dumps(data.get('layout', {}))
    
    try:
        if id_planilha:
            a = Anotacao.query.get(id_planilha)
            if a:
                a.titulo = titulo
                a.colunas = colunas
                a.dados = dados
                a.layout = layout
        else:
            a = Anotacao(titulo=titulo, colunas=colunas, dados=dados, layout=layout)
            db.session.add(a)
        db.session.commit()
        return jsonify({'sucesso': True, 'id': a.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/api/anotacoes/<int:id>', methods=['DELETE'])
@login_required
@admin_required
def excluir_anotacao(id):
    anotacao = Anotacao.query.get(id)
    if not anotacao:
        return jsonify({'sucesso': False, 'erro': 'Anotação não encontrada.'}), 404
        
    try:
        db.session.delete(anotacao)
        db.session.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/preview_email')
@login_required
@admin_required
def preview_email():
    tipo = request.args.get('tipo', 'Adiantamento')
    conf = Configuracao.query.filter_by(tipo=tipo).first()
    
    config_dict = {
        'tipo': tipo,
        'link_form': conf.link_form if conf else '#',
        'link_form_retroativo': conf.link_form_retroativo if conf else '#',
        'data_limite_envio': conf.data_limite_envio if conf else '15/05 às 15:59',
        'data_pagamento': conf.data_pagamento if conf else '25 e 30',
        'mes_referencia': conf.mes_referencia if conf else 'Maio 2026',
        'custom_message': conf.custom_message if conf else None,
        'email_titulo': conf.email_titulo if conf else None,
        'email_subtitulo': conf.email_subtitulo if conf else None,
        'email_alerta_amarelo': conf.email_alerta_amarelo if conf else None,
        'email_alerta_vermelho': conf.email_alerta_vermelho if conf else None,
        'email_rodape': conf.email_rodape if conf else None,
        'email_cnpjs': conf.email_cnpjs if conf else None,
        'email_prazo': conf.email_prazo if conf else None,
        'email_retroativo_titulo': conf.email_retroativo_titulo if conf else None,
        'email_retroativo_texto': conf.email_retroativo_texto if conf else None
    }
    
    email_html = gerar_html_email("Nome do Corretor Teste", tipo, config_dict)
    return render_template('preview_editor.html', email_html=email_html, tipo=tipo)

# --- GESTÃO DE USUÁRIOS (ADMIN) ---
@app.route('/usuarios')
@login_required
@admin_required
def listar_usuarios():
    if current_user.role != 'admin':
        flash('Acesso negado.', 'error')
        return redirect(url_for('index'))
    usuarios = User.query.all()
    return render_template('usuarios.html', usuarios=usuarios)

@app.route('/usuarios/novo', methods=['POST'])
@login_required
@admin_required
def novo_usuario():
    if current_user.role != 'admin': return jsonify({'sucesso': False, 'erro': 'Negado'})
    data = request.form
    username = data.get('username')
    password = data.get('password')
    role = data.get('role', 'user')
    regional = data.get('regional')
    
    if User.query.filter_by(username=username).first():
        flash('Usuário já existe.', 'error')
        return redirect(url_for('listar_usuarios'))
        
    hashed_pw = generate_password_hash(password)
    user = User(username=username, password_hash=hashed_pw, role=role, regional=regional, is_admin=(role=='admin'))
    db.session.add(user)
    db.session.commit()
    flash('Usuário criado!', 'success')
    return redirect(url_for('listar_usuarios'))

@app.route('/usuarios/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_usuario(id):
    if current_user.role != 'admin': return jsonify({'sucesso': False})
    if id == current_user.id:
        flash('Você não pode excluir a si mesmo.', 'error')
        return redirect(url_for('listar_usuarios'))
    user = User.query.get(id)
    if user:
        db.session.delete(user)
        db.session.commit()
        flash('Usuário excluído.', 'success')
    return redirect(url_for('listar_usuarios'))

# --- GESTÃO DE LINKS ---
@app.route('/links')
@login_required
def listar_links():
    links = LinkForm.query.all()
    return render_template('links.html', links=links)

@app.route('/links/novo', methods=['POST'])
@login_required
@admin_required
def novo_link():
    if current_user.role != 'admin': return jsonify({'sucesso': False})
    data = request.form
    link = LinkForm(
        nome=data.get('nome'),
        link=data.get('link'),
        prazo_abertura=data.get('prazo_abertura'),
        prazo_encerramento=data.get('prazo_encerramento'),
        status=data.get('status', 'Ativo'),
        regional=data.get('regional')
    )
    db.session.add(link)
    db.session.commit()
    flash('Link criado!', 'success')
    return redirect(url_for('listar_links'))

@app.route('/links/excluir/<int:id>', methods=['POST'])
@login_required
@admin_required
def excluir_link(id):
    if current_user.role != 'admin': return jsonify({'sucesso': False})
    link = LinkForm.query.get(id)
    if link:
        db.session.delete(link)
        db.session.commit()
        flash('Link excluído.', 'success')
    return redirect(url_for('listar_links'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
