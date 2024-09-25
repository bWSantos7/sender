from flask import Flask, render_template, request, redirect, url_for
import pythoncom
import win32com.client as win32
import os
from datetime import datetime  # Importando datetime para data e hora

pp = Flask(__name__)

# Lista para armazenar os colaboradores que receberam e-mails
emails_enviados = []

# Função para gerar os dados dos colaboradores (simulando CSV)
def gerar_dados():
    dados_colaboradores = [
        {'id': 1, 'nome': 'Bruno', 'email': 'brunowsantos15@gmail.com', 'anexo': 'C:\\Users\\Usuario\\Desktop\\local_host\\upload_notas\\nota_bruno.pdf', 'supervisor': 'bruno.alves@sousaaraujo.com.br'},
        {'id': 2, 'nome': 'Kamille', 'email': 'kamillebenedito@gmai.com', 'anexo': 'C:\\Users\\Usuario\\Desktop\\upload_notas\\nota_kamille.pdf', 'supervisor': 'bruno.alves@sousaaraujo.com.br'},
    ]
    return dados_colaboradores

@pp.route('/')
def index():
    colaboradores = gerar_dados()  # Obtém os dados dos colaboradores
    return render_template('index.html', colaboradores=colaboradores, emails_enviados=emails_enviados)

@pp.route('/enviar_emails', methods=['POST'])
def enviar_emails():
    colaboradores = gerar_dados()  # Obtém os dados dos colaboradores
    
    id_colaborador = request.form.get('id_colaborador')  # Obtém o ID do colaborador do formulário

    if id_colaborador:
        # Enviar e-mail apenas para o colaborador específico
        colaborador = next((c for c in colaboradores if c['id'] == int(id_colaborador)), None)
        if colaborador:
            enviar_email(
                colaborador['email'],
                colaborador['nome'],
                colaborador['supervisor'],
                'rafael.calderaro@sousaaraujo.com.br',
                colaborador['anexo']
            )
            # Adiciona o colaborador na lista de e-mails enviados com data e hora
            emails_enviados.append({
                'id': colaborador['id'],
                'nome': colaborador['nome'],
                'email': colaborador['email'],
                'data_envio': datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Data e hora formatadas
            })
        else:
            print("Colaborador não encontrado.")
    else:
        # Enviar e-mails para todos os colaboradores se nenhum ID for fornecido
        for colaborador in colaboradores:
            enviar_email(
                colaborador['email'],
                colaborador['nome'],
                colaborador['supervisor'],
                'rafael.calderaro@sousaaraujo.com.br',
                colaborador['anexo']
            )
            # Adiciona o colaborador na lista de e-mails enviados com data e hora
            emails_enviados.append({
                'id': colaborador['id'],
                'nome': colaborador['nome'],
                'email': colaborador['email'],
                'data_envio': datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Data e hora formatadas
            })

    return redirect(url_for('index'))  # Redireciona para a página principal após enviar os e-mails

def enviar_email(email_colaborador, nome_colaborador, supervisor, rafael, anexo_pdf):
    pythoncom.CoInitialize()  # Inicia o COM
    try:
        outlook = win32.Dispatch('outlook.application')
        email = outlook.CreateItem(0)

        email.To = email_colaborador
        email.CC = f"{rafael}; {supervisor}"
        email.Subject = f"Solicitação de Nota Comissão {nome_colaborador}"
        email.HTMLBody = f"""
        <p>Boa tarde, {nome_colaborador}</p>
        <p>Estou entrando em contato para solicitar a emissão da(s) nota(s) fiscal(is) referente a(s) comissão(oes) listada(s) em anexo, no arquivo, contém o valor e o CNPJ no qual a nota deve ser emitida.</p>
        <p>A nota deverá ser postada no forms abaixo;</p>
        <p>https://forms.gle/kPESuNP1LKYQwntr5</p>
        <p>Para garantir que todas as nossas obrigações sejam cumpridas de maneira adequada, as notas devem ser emitidas e enviadas até a data de 10/10 às 18:00 (Notas enviadas posteriormente serão programadas para pagamento no mês seguinte).</p>
        <p>O pagamento das notas deverá ser efetuado entre as datas de 20/10 e 25/10 (Em caso de erro na emissão da nota a data para pagamento poderá ser prorrogada)</p>
        <p>Observações:</P>
        <p>Deverá ser emitida uma nota por empreendimento</p>
        <p>Preencha o corpo da nota com os dados bancários da sua conta PJ (contas físicas não serão aceitas).</p>
        <p>Agradeço a atenção e fico à disposição para quaisquer dúvidas.</p>
        <p>Atenciosamente,</p>
        <img src="https://i.postimg.cc/qBYQbpqg/assinatura-bruno-alves.png" alt="Assinatura" width="400" style="display: block; margin: 0 auto;">
        """

        if os.path.exists(anexo_pdf):
            email.Attachments.Add(anexo_pdf)
        else:
            print(f"Anexo {anexo_pdf} não encontrado.")
        
        email.Send()
        print(f"E-mail enviado para {email_colaborador}")
    finally:
        pythoncom.CoUninitialize()  # Finaliza o COM

if __name__ == "__main__":
    pp.run(debug=True)
