import threading
import time
import random
from datetime import datetime, timedelta
import os
import io
import zipfile
import pandas as pd
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from models import db, Corretor, Configuracao, EmailConfig, EnvioLog, FilaUpload, EmpreendimentoSupervisor
from services.excel_parser import processar_planilha_base
from services.pdf_generator import gerar_pdfs
from services.email_sender import enviar_email_smtp, gerar_html_email

def get_brasilia_time():
    return datetime.utcnow() - timedelta(hours=3)

app = Flask(__name__)

# Controle global de disparos
stop_envio = threading.Event()
thread_ativa = False

app.secret_key = 'sousa_araujo_secreto'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    # Inicializar configuração padrão se não existir
    if not Configuracao.query.first():
        for tipo in ['Adiantamento', 'Repasse', 'Prêmio']:
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

@app.route('/')
def index():
    total_enviados = EnvioLog.query.filter_by(status='Sucesso').count()
    total_erros = EnvioLog.query.filter_by(status='Erro').count()
    ultimos_logs = EnvioLog.query.order_by(EnvioLog.data_envio.desc()).limit(10).all()
    return render_template('dashboard.html', total_enviados=total_enviados, total_erros=total_erros, logs=ultimos_logs)

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        tipo_envio = request.form.get('tipo_envio')
        file = request.files.get('file')
        
        if not file or not file.filename.endswith('.xlsx'):
            flash('Por favor, envie um arquivo Excel (.xlsx) válido.', 'error')
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
            c = Corretor.query.filter_by(nome=corretor_nome).first()
            dest_email = c.email if c else None
            
            # Resolver emails dos supervisores em CC
            cc_emails_list = []
            if emps:
                lista_emps = [e.strip() for e in emps.split(',')]
                for emp in lista_emps:
                    emp_sup = EmpreendimentoSupervisor.query.filter_by(empreendimento=emp).first()
                    if emp_sup:
                        if emp_sup.supervisor and '@' in emp_sup.supervisor and emp_sup.supervisor not in cc_emails_list:
                            cc_emails_list.append(emp_sup.supervisor.strip())
                        if emp_sup.supervisor2 and '@' in emp_sup.supervisor2 and emp_sup.supervisor2 not in cc_emails_list:
                            cc_emails_list.append(emp_sup.supervisor2.strip())
                        
            cc_emails_str = ", ".join(cc_emails_list) if cc_emails_list else None
            
            novo_fila = FilaUpload(
                corretor_nome=corretor_nome,
                tipo=tipo_envio,
                caminho_pdf=pdf_data['caminho'],
                empreendimentos=emps,
                destinatario_email=dest_email,
                cc_emails=cc_emails_str
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
def fila():
    itens_fila = FilaUpload.query.all()
    # Identificar se o corretor existe no banco para vincular email
    fila_com_dados = []
    for item in itens_fila:
        corretor = Corretor.query.filter_by(nome=item.corretor_nome).first()
        
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
        
        if nome in processados:
            continue
            
        sup_col = colunas_map.get('SUPERVISOR')
        supervisor = str(row[sup_col]).strip() if sup_col and pd.notna(row[sup_col]) else 'sousaaraujo.contato@gmail.com'
        
        c = Corretor.query.filter_by(nome=nome).first()
        if not c:
            c = Corretor(nome=nome, email=email, supervisor=supervisor)
            db.session.add(c)
            inseridos += 1
        else:
            c.email = email
            c.supervisor = supervisor
            atualizados += 1
            
        processados.add(nome)
            
    db.session.commit()
    flash(f'Planilha lida! {inseridos} novos corretores cadastrados e {atualizados} atualizados. (Total: {inseridos + atualizados} únicos)', 'success')
    return redirect(url_for('configuracoes'))

@app.route('/importar_supervisores', methods=['POST'])
def importar_supervisores():
    file = request.files.get('file_supervisores')
    if not file:
        flash('Arquivo não enviado.', 'error')
        return redirect(url_for('configuracoes'))
    
    try:
        # A aba se chamava tabel_supervisor
        df = pd.read_excel(file, sheet_name='tabel_supervisor', engine='openpyxl')
    except Exception:
        try:
            df = pd.read_excel(file, engine='openpyxl')
        except Exception as e:
            flash(f'Erro ao ler arquivo: {str(e)}', 'error')
            return redirect(url_for('configuracoes'))

    colunas_map = {c.upper().strip(): c for c in df.columns}
    
    if 'EMPREENDIMENTO' not in colunas_map or 'SUPERVISOR' not in colunas_map:
        flash('Planilha deve conter as colunas EMPREENDIMENTO e SUPERVISOR.', 'error')
        return redirect(url_for('configuracoes'))
        
    inseridos = 0
    atualizados = 0
    
    for _, row in df.iterrows():
        emp = str(row[colunas_map['EMPREENDIMENTO']]).strip()
        if pd.isna(row[colunas_map['EMPREENDIMENTO']]) or not emp or emp == 'nan': continue
        
        sup = str(row[colunas_map['SUPERVISOR']]).strip() if pd.notna(row[colunas_map['SUPERVISOR']]) else None
        sup2_col = colunas_map.get('SUPERVISOR 2') or colunas_map.get('SUPERVISOR2')
        sup2 = str(row[sup2_col]).strip() if sup2_col and pd.notna(row[sup2_col]) else None
        
        es = EmpreendimentoSupervisor.query.filter_by(empreendimento=emp).first()
        if not es:
            es = EmpreendimentoSupervisor(empreendimento=emp, supervisor=sup, supervisor2=sup2)
            db.session.add(es)
            inseridos += 1
        else:
            es.supervisor = sup
            es.supervisor2 = sup2
            atualizados += 1
            
    db.session.commit()
    flash(f'Tabela de Empreendimentos lida! {inseridos} novos vinculados e {atualizados} atualizados.', 'success')
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
            
            corretor = Corretor.query.filter_by(nome=item.corretor_nome).first()
            if not corretor:
                item.status = 'Erro'
                log = EnvioLog(corretor_id=1, tipo=item.tipo, status='Erro', mensagem_erro='Corretor não encontrado no banco', caminho_anexo=item.caminho_pdf)
                db.session.add(log)
                db.session.commit()
                continue
                
            # Pré-validações de disparo
            if not item.destinatario_email or '@' not in item.destinatario_email:
                item.status = 'Erro'
                log = EnvioLog(corretor_id=corretor.id, tipo=item.tipo, status='Erro', mensagem_erro='E-mail do destinatário ausente ou inválido', caminho_anexo=item.caminho_pdf)
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
                
            sucesso, msg = enviar_email_smtp(
                email_colaborador=item.destinatario_email,
                nome_colaborador=item.corretor_nome,
                supervisor=item.cc_emails,
                supervisor2=None,
                anexo_pdf=item.caminho_pdf,
                config=config_dict
            )
            
            log = EnvioLog(
                corretor_id=corretor.id,
                tipo=item.tipo,
                status='Sucesso' if sucesso else 'Erro',
                mensagem_erro=msg if not sucesso else None,
                caminho_anexo=item.caminho_pdf
            )
            db.session.add(log)
            item.status = 'Concluido' if sucesso else 'Erro'
            db.session.commit()
            
            time.sleep(random.uniform(5, 8)) # Pausa segura entre 5 e 8 segundos para evitar bloqueios do Google
            
    thread_ativa = False

@app.route('/api/status_envio')
def status_envio():
    # Indicadores históricos (Dashboard)
    total_sucesso = EnvioLog.query.filter_by(status='Sucesso').count()
    total_erro = EnvioLog.query.filter_by(status='Erro').count()
    
    # Indicadores da fila atual
    pendentes = FilaUpload.query.filter_by(status='Pendente').count()
    processando = FilaUpload.query.filter_by(status='Processando').count()
    concluidos = FilaUpload.query.filter_by(status='Concluido').count()
    erros = FilaUpload.query.filter_by(status='Erro').count()
    total = FilaUpload.query.count()
    
    # Logs recentes
    logs_data = []
    for l in EnvioLog.query.order_by(EnvioLog.data_envio.desc()).limit(10).all():
        logs_data.append({
            'corretor': l.corretor.nome if l.corretor else 'Desconhecido',
            'tipo': l.tipo,
            'data': l.data_envio.strftime('%d/%m/%Y %H:%M'),
            'status': l.status,
            'erro': l.mensagem_erro or ''
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
        EnvioLog.query.delete()
        db.session.commit()
        return jsonify({'sucesso': True})
    except Exception as e:
        return jsonify({'sucesso': False, 'erro': str(e)}), 500

@app.route('/parar_envios', methods=['POST'])
def parar_envios():
    stop_envio.set()
    return jsonify({'sucesso': True, 'mensagem': 'Solicitação de parada enviada.'})

@app.route('/iniciar_envios', methods=['POST'])
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
def limpar_fila():
    try:
        FilaUpload.query.delete()
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
def atualizar_email():
    try:
        data = request.json
        nome = data.get('nome')
        email = data.get('email')
        
        if not nome or not email:
            return jsonify({'sucesso': False, 'erro': 'Nome e E-mail são obrigatórios.'}), 400
            
        import re
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({'sucesso': False, 'erro': 'Formato de e-mail inválido.'}), 400
            
        # Buscar corretor
        c = Corretor.query.filter_by(nome=nome).first()
        criado_novo = False
        
        if not c:
            # Criar novo corretor com supervisores vazios (nullable=True no banco)
            c = Corretor(nome=nome, email=email, supervisor='', supervisor2='')
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

@app.route('/configuracoes', methods=['GET', 'POST'])
def configuracoes():
    email_conf = EmailConfig.query.first()
    if not email_conf:
        email_conf = EmailConfig()
        db.session.add(email_conf)
        db.session.commit()

    if request.method == 'POST':
        # Atualizar Links e Datas
        for tipo in ['Adiantamento', 'Repasse', 'Prêmio']:
            conf = Configuracao.query.filter_by(tipo=tipo).first()
            if not conf:
                conf = Configuracao(tipo=tipo)
                db.session.add(conf)
            
            conf.link_form = request.form.get(f'{tipo}_link_form')
            conf.link_form_retroativo = request.form.get(f'{tipo}_link_form_retroativo')
            conf.data_limite_envio = request.form.get(f'{tipo}_data_limite_envio')
            conf.data_pagamento = request.form.get(f'{tipo}_data_pagamento')
            conf.mes_referencia = request.form.get(f'{tipo}_mes_referencia')
            
        # Atualizar Config de Email
        if request.form.get('smtp_user'):
            email_conf.smtp_server = request.form.get('smtp_server')
            email_conf.smtp_port = int(request.form.get('smtp_port') or 587)
            email_conf.smtp_user = request.form.get('smtp_user')
            if request.form.get('smtp_pass'):
                email_conf.smtp_pass = request.form.get('smtp_pass')
            email_conf.from_name = request.form.get('from_name')

        db.session.commit()
        flash('Configurações salvas com sucesso.', 'success')
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
    corretor = Corretor.query.get(data.get('id'))
    if not corretor:
        return jsonify({'sucesso': False, 'erro': 'Corretor não encontrado.'}), 404
        
    corretor.nome = data.get('nome')
    corretor.email = data.get('email')
    db.session.commit()
    return jsonify({'sucesso': True})

@app.route('/api/editar_empreendimento', methods=['POST'])
def editar_empreendimento():
    data = request.json
    emp = EmpreendimentoSupervisor.query.get(data.get('id'))
    if not emp:
        return jsonify({'sucesso': False, 'erro': 'Empreendimento não encontrado.'}), 404
        
    emp.supervisor = data.get('supervisor')
    emp.supervisor2 = data.get('supervisor2')
    db.session.commit()
    return jsonify({'sucesso': True})

@app.route('/preview_email')
def preview_email():
    tipo = request.args.get('tipo', 'Adiantamento')
    conf = Configuracao.query.filter_by(tipo=tipo).first()
    config_dict = {
        'tipo': tipo,
        'link_form': conf.link_form if conf else '#',
        'link_form_retroativo': conf.link_form_retroativo if conf else '#',
        'data_limite_envio': conf.data_limite_envio if conf else '',
        'data_pagamento': conf.data_pagamento if conf else '',
        'mes_referencia': conf.mes_referencia if conf else ''
    }
    html = gerar_html_email("Nome do Corretor Teste", tipo, config_dict)
    return html

if __name__ == '__main__':
    app.run(debug=True, port=5000)
