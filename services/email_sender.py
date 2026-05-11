import smtplib
from email.message import EmailMessage
import os
import time

def enviar_email_smtp(email_colaborador, nome_colaborador, supervisor, supervisor2, anexo_pdf, config):
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
        
        # CC Supervisors
        cc_list = []
        if supervisor and '@' in str(supervisor):
            cc_list.append(supervisor.strip())
        if supervisor2 and '@' in str(supervisor2):
            cc_list.append(supervisor2.strip())
        
        # Cópia oculta ou fixa se desejar
        # cc_list.append("sousaaraujo.contato@gmail.com")
        
        if cc_list:
            msg['Cc'] = ", ".join(cc_list)

        html_body = gerar_html_email(nome_colaborador, tipo, config)
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


def gerar_html_email(nome_colaborador, tipo, config):
    link_form = config.get('link_form', '#')
    link_retroativo = config.get('link_form_retroativo', '#')
    data_limite = config.get('data_limite_envio', '15/05 às 15h59')
    data_pagamento = config.get('data_pagamento', '27/05 e 30/05')
    mes_ref = config.get('mes_referencia', 'Abril 2026')
    
    # Template HTML
    html = f"""
    <div style="margin:0;padding:0;background:#f3f4f6;">
      <div style="max-width:760px;margin:0 auto;padding:28px 18px;
                  font-family:'Segoe UI', -apple-system, BlinkMacSystemFont, 'Helvetica Neue', Arial, sans-serif;
                  color:#111827;">

        <div style="background:#ffffff;border:1px solid #e5e7eb;border-radius:16px;overflow:hidden;
                    box-shadow:0 10px 28px rgba(0,0,0,0.08);">

          <div style="height:3px;background:#7a0f0f;"></div>

          <div style="padding:22px 26px 10px 26px;">
            <div style="font-size:12px;letter-spacing:0.14em;text-transform:uppercase;color:#6b7280;">
              {tipo}
            </div>

            <h1 style="margin:8px 0 0 0;font-size:18px;line-height:1.35;color:#111827;font-weight:700;">
              Solicitação de emissão de nota fiscal – {mes_ref}
            </h1>

            <p style="margin:8px 0 0 0;font-size:13.5px;line-height:1.65;color:#4b5563;">
              Favor emitir e enviar a(s) nota(s) fiscal(is) conforme as orientações abaixo.
            </p>
          </div>

          <!-- Alerta Endereço -->
          <div style="margin:16px auto 18px auto; padding:14px 16px; border-radius:12px; border:1px solid #facc15; background:#fffbcc; max-width:620px;">
            <div style="font-size:13.8px;line-height:1.75;color:#374151;">
              <span style="font-size:18px;margin-right:6px;">⚠️</span>
              <b style="color:#92400e;">Atenção – Emissão de Nota Fiscal:</b><br>
              Ao emitir notas para o <b>CNPJ 10.268.911/0001-58</b>, verifiquem se o endereço está preenchido corretamente.<br>
              O endereço correto para emissão é:<br>
              <b>R GENERAL CARNEIRO, 380 – Centro</b>
            </div>
          </div>

          <!-- Alerta Fiscal -->
          <div style="margin:16px auto 18px auto; padding:14px 16px; border-radius:12px; border:1px solid #fecaca; background:#fffafa; max-width:620px;">
            <div style="font-size:13.8px;line-height:1.75;color:#374151;">
              <b style="color:#7a0f0f;">Atenção – Enquadramento Tributário:</b><br>
              Favor atentarem-se ao correto enquadramento no <b>regime de tributação</b> (IR, entre outros).
              Dessa forma, o setor fiscal <b>não realizará a retenção de impostos</b> em notas emitidas de forma incorreta.
              Confirme sua situação junto ao <b>seu contador</b>.
            </div>
          </div>

          <!-- Body -->
          <div style="padding:0 26px 8px 26px;">
            <p style="margin:10px 0 12px 0;font-size:14px;line-height:1.8;color:#111827;">
              Boa tarde, <b>{nome_colaborador}</b>.
            </p>

            <p style="margin:0 0 14px 0;font-size:14px;line-height:1.8;color:#374151;">
              Solicitamos a emissão da(s) nota(s) fiscal(is) referente(s) ao {tipo.lower()} listado no anexo deste e-mail.
              O arquivo contém o valor total na última coluna (<b>VALOR TOTAL</b>).
            </p>

            <!-- Nota CNPJ -->
            <div style="margin:16px 0 16px 0;padding:12px 14px;border-radius:12px; border:1px solid #e5e7eb;background:#ffffff;">
              <div style="font-size:13.5px;line-height:1.7;color:#374151;">
                <b style="color:#7a0f0f;">Conferência obrigatória:</b> antes de emitir, valide o <b>CNPJ do empreendimento</b>.
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
            <div style="margin:0 0 18px 0; padding:12px 14px; border-radius:12px; border:1px solid #e5e7eb;">
              <div style="font-size:13.5px;line-height:1.7;color:#374151;">
                <b style="color:#7a0f0f;">Prazo:</b> enviar até <b>{data_limite}</b>.<br>
                Envios após esse horário serão programados para pagamento no mês seguinte.
              </div>
            </div>

            <!-- Formulário Retroativo -->
            <div style="margin:20px 0 16px 0; padding:16px; border-radius:12px; background:#fefce8; border:1px solid #fde047;">
                <div style="font-size:13.5px;font-weight:700;color:#854d0e;margin-bottom:8px;">
                    Envio de Notas Retroativas
                </div>
                <div style="font-size:13px;color:#713f12;line-height:1.6;margin-bottom:12px;">
                    Caso tenha perdido o prazo de envio ou tenha notas referentes a meses anteriores, encaminhe pelo formulário abaixo:
                </div>
                <a href="{link_retroativo}" style="display:inline-block;padding:9px 16px;border-radius:999px;background:#facc15;color:#422006;text-decoration:none;font-size:13px;font-weight:700;">
                    Formulário de Retroativas
                </a>
            </div>

            <p style="margin:0 0 10px 0;font-size:13.8px;line-height:1.8;color:#374151;">
              Pagamentos programados entre <b>{data_pagamento}</b>. Em caso de divergências na emissão, o pagamento poderá ser prorrogado.
            </p>

            <p style="margin:0 0 18px 0;font-size:13.8px;line-height:1.8;color:#374151;">
              Dúvidas: WhatsApp <b>(12) 99178-8835</b>
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
