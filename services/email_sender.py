import smtplib
from email.message import EmailMessage
import os
import time

def enviar_email_smtp(email_colaborador, nome_colaborador, supervisor, supervisor2, anexo_pdf, config, token=None):
    """
    Envia e-mail utilizando SMTP (Background).
    """
    from models import EmailConfig
    
    email_conf = EmailConfig.query.first()
    if not email_conf or not email_conf.smtp_pass:
        return False, "Configuração de e-mail ou senha SMTP não encontrada nas Configurações."

    try:
        SMTP_SERVER = email_conf.smtp_server
        SMTP_PORT = email_conf.smtp_port
        SMTP_USER = email_conf.smtp_user
        SMTP_PASS = email_conf.smtp_pass
        FROM_NAME = email_conf.from_name

        msg = EmailMessage()
        
        tipo = config.get('tipo', 'Adiantamento')
        mes_ref = config.get('mes_referencia', 'Abril 2026')
        
        msg['Subject'] = f"Solicitação de Nota de {tipo} – {mes_ref} | {nome_colaborador}"
        msg['From'] = f"{FROM_NAME} <{SMTP_USER}>"
        msg['To'] = email_colaborador
        
        # CC: No máximo 3 pessoas (1ª é sempre sousaaraujo.contato@gmail.com, as outras duas são supervisores)
        cc_set = set()
        
        def adicionar_emails(campo_texto):
            if campo_texto:
                partes = str(campo_texto).split(',')
                for p in partes:
                    email_limpo = p.strip()
                    if '@' in email_limpo:
                        if email_limpo.lower() != 'sousaaraujo.contato@gmail.com':
                            cc_set.add(email_limpo)

        adicionar_emails(supervisor)
        adicionar_emails(supervisor2)
        
        supervisores_ordenados = list(cc_set)
        cc_final = ["sousaaraujo.contato@gmail.com"] + supervisores_ordenados[:2]
        
        msg['Cc'] = ", ".join(cc_final)

        html_body = gerar_html_email(nome_colaborador, tipo, config, token=token)
        msg.set_content("Por favor, ative a visualização de HTML para ver este e-mail.")
        msg.add_alternative(html_body, subtype='html')

        if os.path.exists(anexo_pdf):
            with open(anexo_pdf, 'rb') as f:
                pdf_data = f.read()
                nome_arquivo = os.path.basename(anexo_pdf)
                msg.add_attachment(pdf_data, maintype='application', subtype='pdf', filename=nome_arquivo)
        else:
            return False, f"Anexo {anexo_pdf} não encontrado."

        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        return True, "E-mail enviado com sucesso"
        
    except Exception as e:
        return False, f"Erro SMTP: {str(e)}"


def gerar_html_email(nome_colaborador, tipo, config, token=None):
    link_form = config.get('link_form', '#')
    link_retroativo = config.get('link_form_retroativo', '#')
    data_limite = config.get('data_limite_envio', '15/05 às 15h59')
    data_pagamento = config.get('data_pagamento', '27/05 e 30/05')
    mes_ref = config.get('mes_referencia', 'Abril 2026')

    # Link de visualização web
    view_link_html = ""
    if token:
        base_url = os.getenv('BASE_URL', 'http://localhost:5000')
        view_url = f"{base_url}/v/{token}"
        view_link_html = f'''
            <div style="text-align: center; margin-bottom: 10px;">
                <a href="{view_url}" style="color: #666; font-size: 11px; text-decoration: underline;">Visualizar mensagem no navegador</a>
            </div>
        '''

    # Obter textos customizados com fallbacks
    titulo = config.get('email_titulo') or f"Solicitação de emissão de nota fiscal – {mes_ref}"
    subtitulo = config.get('email_subtitulo') or "Favor emitir e enviar a(s) nota(s) fiscal(is) conforme as orientações abaixo."
    
    msg_corpo = config.get('custom_message') or f"Boa tarde, <b>{nome_colaborador}</b>.<br><br>Solicitamos a emissão da(s) nota(s) fiscal(is) referente(s) ao {tipo.lower()} listado no anexo deste e-mail. O arquivo contém o valor total na última coluna (<b>VALOR TOTAL</b>)."
    if '<' not in msg_corpo: msg_corpo = msg_corpo.replace('\n', '<br>')
    
    alerta_amarelo = config.get('email_alerta_amarelo') or "<b>Atenção – Emissão de Nota Fiscal:</b><br>Ao emitir notas para o <b>CNPJ 10.268.911/0001-58</b>, verifiquem se o endereço está preenchido corretamente.<br>O endereço correto para emissão é:<br><b>R GENERAL CARNEIRO, 380 – Centro</b>"
    if '<br>' not in alerta_amarelo and '<p>' not in alerta_amarelo: alerta_amarelo = alerta_amarelo.replace('\n', '<br>')
    
    alerta_vermelho = config.get('email_alerta_vermelho') or "<b>Atenção – Enquadramento Tributário:</b><br>Favor atentarem-se ao correto enquadramento no <b>regime de tributação</b> (IR, entre outros). Dessa forma, o setor fiscal <b>não realizará a retenção de impostos</b> em notas emitidas de forma incorreta. Confirme sua situação junto ao <b>seu contador</b>."
    if '<br>' not in alerta_vermelho and '<p>' not in alerta_vermelho: alerta_vermelho = alerta_vermelho.replace('\n', '<br>')
    
    prazo_html = config.get('email_prazo')
    if not prazo_html:
        prazo_html = f'<b style="color:#7a0f0f;">Prazo:</b> enviar até <b>{data_limite}</b>.<br>Envios após esse horário serão programados para pagamento no mês seguinte.'
    else:
        # Sincronização dinâmica: tenta injetar a data atual se encontrar o padrão de texto
        import re
        if 'enviar até' in prazo_html:
            # Substitui o conteúdo dentro do <b> que segue "enviar até"
            prazo_html = re.sub(r'(enviar até\s*<b>).*?(</b>)', rf'\g<1>{data_limite}\g<2>', prazo_html, flags=re.IGNORECASE)
    
    rodape = config.get('email_rodape')
    if not rodape:
        rodape = f"Pagamentos programados entre <b>{data_pagamento}</b>. Em caso de divergências na emissão, o pagamento poderá ser prorrogado.<br><br>Dúvidas: WhatsApp <b>(12) 99178-8835</b>"
    else:
        # Sincronização dinâmica para o rodapé
        import re
        if 'programados entre' in rodape:
            rodape = re.sub(r'(programados entre\s*<b>).*?(</b>)', rf'\g<1>{data_pagamento}\g<2>', rodape, flags=re.IGNORECASE)
    
    retro_titulo = config.get('email_retroativo_titulo') or 'Envio de Notas Retroativas'
    retro_texto = config.get('email_retroativo_texto') or 'Caso tenha perdido o prazo de envio ou tenha notas referentes a meses anteriores, encaminhe pelo formulário abaixo:'

    # Lista de CNPJs (Padrão se vazio)
    cnpjs_html = config.get('email_cnpjs')
    if not cnpjs_html:
        cnpjs_html = """
        <table style="width:100%; border-collapse:collapse; margin-top:10px; font-size:12px; border:1px solid #e5e7eb;">
          <thead>
            <tr style="background:#f9fafb; text-align:left;">
              <th style="padding:8px; border:1px solid #e5e7eb; color:#7a0f0f;">Empreendimento</th>
              <th style="padding:8px; border:1px solid #e5e7eb; color:#7a0f0f;">CNPJ</th>
            </tr>
          </thead>
          <tbody>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">AMETISTA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">36.366.418/0001-64</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">GRAN PORTINARI</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">42.810.302/0001-75</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">MONET I</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">43.436.481/0001-95</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">MONET II</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">43.436.481/0001-95</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">PORTAL DO LAGO</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">23.532.828/0001-96</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SAFIRA I</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">22.620.409/0001-43</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SAFIRA II</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">22.620.409/0001-43</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SIENA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">43.434.336/0001-75</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU PLENO HOME I</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">39.793.905/0001-00</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU PLENO JACAREÍ</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">10.268.911/0001-58</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER NOVA ODESSA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">37.886.357/0001-29</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER POÁ</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">32.225.532/0001-13</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">TANGARÁ III</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">10.268.911/0001-58</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">VIDÁLIA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">29.080.196/0001-53</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">BOSQUE DAS CEREJEIRAS I</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">32.197.085/0001-36</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">BOSQUE DAS CEREJEIRAS II</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">32.197.085/0001-36</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER JACAREÍ DAVI LINO</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">10.268.911/0001-58</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER FLORENÇA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">43.827.950/0001-05</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU MAIS GUAIANASES</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">42.043.862/0001-41</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER DIADEMA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">54.476.342/0001-01</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER DIADEMA II</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">54.476.342/0001-01</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU MAIS DIADEMA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">54.476.342/0001-01</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER VERONA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">43.827.950/0001-05</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER RAVENNA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">10.268.911/0001-58</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER RAVENNA II</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">10.268.911/0001-58</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU MAIS SUZANO</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">54.457.770/0001-97</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU PLENO COTIA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">56.006.995/0001-52</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU SPECIAL PLACE</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">10.268.911/0001-58</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">DUMONT</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">31.423.606/0001-63</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">DA VINCI</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">32.197.053/0001-30</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU MAIS URBAN</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">57.624.202/0001-21</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER ITATIBA I</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">54.457.613/0001-81</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER ITATIBA II</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">54.457.613/0001-81</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER ROMA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">43.827.950/0001-05</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER ALTOS DE SÃO JOSÉ</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">58.094.959/0001-13</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">SOU VIVER UP</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">58.149.372/0001-64</td></tr>
            <tr><td style="padding:6px 8px; border:1px solid #e5e7eb;">RESIDENCIAL SOROCABA</td><td style="padding:6px 8px; border:1px solid #e5e7eb;">60.837.640/0001-82</td></tr>
          </tbody>
        </table>
        """

    # Template HTML com IDs para o editor
    html = f"""
    <div style="margin:0;padding:0;background:#f3f4f6;">
      <div style="max-width:760px;margin:0 auto;padding:28px 18px;
                  font-family:'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
                  color:#111827;">

        <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;
                    box-shadow:0 10px 28px rgba(0,0,0,0.08);">
          {view_link_html}

          <div style="height:3px;background:#7a0f0f;"></div>

          <div style="padding:22px 26px 10px 26px;">
            <div style="font-size:12px;letter-spacing:0.14em;text-transform:uppercase;color:#6b7280;">
              {tipo}
            </div>

            <h1 id="edit-titulo" style="margin:8px 0 0 0;font-size:18px;line-height:1.35;color:#111827;font-weight:700;">
              {titulo}
            </h1>

            <p id="edit-subtitulo" style="margin:8px 0 0 0;font-size:13.5px;line-height:1.65;color:#4b5563;">
              {subtitulo}
            </p>
          </div>

          <!-- Alerta Endereço -->
          <div style="margin:16px auto 18px auto; padding:14px 16px; border-radius:12px; border:1px solid #facc15; background:#fffbcc; max-width:620px;">
            <div id="edit-alerta-amarelo" style="font-size:13.8px;line-height:1.75;color:#374151;">
              <span style="font-size:18px;margin-right:6px;">⚠️</span>
              {alerta_amarelo}
            </div>
          </div>

          <!-- Alerta Fiscal -->
          <div style="margin:16px auto 18px auto; padding:14px 16px; border-radius:12px; border:1px solid #fecaca; background:#fffafa; max-width:620px;">
            <div id="edit-alerta-vermelho" style="font-size:13.8px;line-height:1.75;color:#374151;">
              {alerta_vermelho}
            </div>
          </div>

          <!-- Body -->
          <div style="padding:0 26px 8px 26px;">
            <p id="edit-corpo" style="margin:10px 0 14px 0;font-size:14px;line-height:1.8;color:#374151;">
              {msg_corpo}
            </p>

            <!-- Nota CNPJ -->
            <div style="margin:16px 0 16px 0;padding:12px 14px;border-radius:12px; border:1px solid #e5e7eb;background:#ffffff;">
              <div id="edit-conferencia" style="font-size:13.5px;line-height:1.7;color:#374151;">
                <b style="color:#7a0f0f;">Conferência obrigatória:</b> antes de emitir, valide o <b>CNPJ do empreendimento</b>.
              </div>
              <div id="edit-cnpjs">
                {cnpjs_html}
              </div>
            </div>

            <!-- CTA -->
            <div style="margin:8px 0 16px 0;">
              <div style="font-size:14px;margin:0 0 10px 0;color:#374151;">
                Envie a nota pelo formulário:
              </div>
              <a href="{link_form}" style="display:inline-block; padding:11px 16px; border-radius:999px; background:#7a0f0f; color:#ffffff; text-decoration:none; font-size:13.5px; font-weight:700; margin-bottom:18px;">
                Acessar formulário
              </a>
            </div>

            <!-- Prazo -->
            <div id="edit-prazo-box" style="margin:0 0 18px 0; padding:12px 14px; border-radius:12px; border:1px solid #e5e7eb;">
              <div id="edit-prazo" style="font-size:13.5px;line-height:1.7;color:#374151;">
                {prazo_html}
              </div>
            </div>

            <!-- Formulário Retroativo -->
            <div id="edit-retroativo-box" style="margin:20px 0 16px 0; padding:16px; border-radius:12px; background:#fefce8; border:1px solid #fde047;">
                <div id="edit-retroativo-titulo" style="font-size:13.5px;font-weight:700;color:#854d0e;margin-bottom:8px;">
                    {retro_titulo}
                </div>
                <div id="edit-retroativo-texto" style="font-size:13px;color:#713f12;line-height:1.6;margin-bottom:12px;">
                    {retro_texto}
                </div>
                <a href="{link_retroativo}" style="display:inline-block;padding:9px 16px;border-radius:999px;background:#facc15;color:#422006;text-decoration:none;font-size:13px;font-weight:700;">
                    Formulário de Retroativas
                </a>
            </div>

            <p id="edit-rodape" style="margin:0 0 10px 0;font-size:13.8px;line-height:1.8;color:#374151;">
              {rodape}
            </p>
          </div>

          <div style="padding:16px 26px 22px 26px;border-top:1px solid #e5e7eb;background:#ffffff;">
            <p style="margin:0 0 10px 0;font-size:13.5px;color:#374151;">
              Atenciosamente, Construtora Sousa Araújo
            </p>
          </div>
        </div>

        <div style="text-align:center;margin-top:12px;font-size:11.5px;color:#9ca3af;">
          Mensagem automática — favor não responder.
        </div>
      </div>
    </div>
    """
    return html
