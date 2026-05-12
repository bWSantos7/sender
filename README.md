# Commission Sender – Sousa Araújo

Sistema inteligente para processamento de comissões, geração automatizada de relatórios em PDF e disparo de notificações por e-mail para corretores e supervisores.

## 🚀 Funcionalidades Principais

### 1. Processamento Inteligente de Planilhas
- **Upload Drag-and-Drop**: Arraste suas planilhas de comissão diretamente para o sistema.
- **Suporte a Múltiplos Formatos**: Processa automaticamente planilhas de **Adiantamento (House)**, **Staff (Repasse)** e **Prêmio**.
- **Extração Automática**: Identifica nomes, valores, empreendimentos e dados de contato.

### 2. Gestão de Documentos (PDF)
- **Geração Automatizada**: Cria relatórios personalizados em PDF para cada corretor.
- **Gerenciador de Arquivos**: Visualize, baixe ou exclua os PDFs gerados diretamente pelo navegador.
- **Histórico Persistente**: Acompanhe o que já foi gerado e enviado.

### 3. Comunicação Personalizada
- **Editor Visual "Live"**: Edite o corpo do e-mail, títulos, alertas e tabelas de CNPJ diretamente no preview, com salvamento instantâneo.
- **Disparos Automáticos**: Envio em massa ou individual via SMTP configurável.
- **Cópia de Supervisão**: Inclui automaticamente o supervisor do empreendimento em cópia nos disparos.

### 4. Cadastro e Configurações
- **Gestão de Corretores/Supervisores**: Adicione manualmente ou importe via planilha.
- **Controle de Prazos**: Configure datas limite de envio e datas de pagamento por categoria.
- **Bloqueio de Edição**: Interface de configuração protegida contra cliques acidentais.

## 🛠️ Tecnologias Utilizadas

- **Backend**: Python / Flask
- **Banco de Dados**: SQLite (SQLAlchemy)
- **Frontend**: HTML5, CSS3 (Tailwind CSS)
- **Iconografia**: Lucide Icons
- **Processamento de Dados**: Pandas / Openpyxl
- **Geração de PDF**: FPDF2

## 📦 Como Instalar

1. **Clonar o repositório**:
   ```bash
   git clone [url-do-repositorio]
   ```

2. **Instalar dependências**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Inicializar o Banco de Dados**:
   O sistema criará o banco automaticamente na primeira execução. Certifique-se de executar as migrações se estiver atualizando:
   ```bash
   python migrate_db_v2.py
   ```

4. **Executar**:
   ```bash
   python app.py
   ```

## ⚙️ Configuração de E-mail

Para que o envio funcione, configure o **Servidor de E-mail** na tela de configurações:
- Use uma **Senha de Aplicativo** (se usar Gmail).
- Verifique se a porta (ex: 587) e o host (ex: smtp.gmail.com) estão corretos.

---
*Desenvolvido para Construtora Sousa Araújo.*
