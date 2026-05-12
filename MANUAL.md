# Guia do Usuário – Sistema de Comissões Sousa Araújo

Este guia explica passo a passo como utilizar as funcionalidades do sistema para processar comissões e enviar e-mails.

---

## 1. Configuração Inicial (Primeiro Acesso)

Antes de começar a enviar e-mails, você precisa configurar o servidor SMTP:

1.  Acesse a aba **Configurações**.
2.  Clique no ícone de **Lápis** no bloco "Servidor de E-mail" para desbloquear.
3.  Preencha o nome do remetente, seu e-mail e a **Senha de Aplicativo** (se usar Gmail).
4.  Clique em **Salvar Todas as Configurações**.
5.  *Dica:* Configure também os links dos formulários e o mês de referência.

---

## 2. Gestão de Corretores e Supervisores

Para que o sistema saiba para quem enviar os e-mails, é necessário ter os contatos cadastrados:

-   **Importação**: Vá em **Corretores e Supervisores** e arraste uma planilha Excel com as colunas: `Nome`, `Email`, `Empreendimento` e `Tipo` (Corretor ou Supervisor).
-   **Manual**: Use os botões de "Adicionar" para cadastrar um novo nome rapidamente.
-   **Importante**: Cada empreendimento deve ter pelo menos um Supervisor cadastrado para que ele receba a cópia (CC) do e-mail.

---

## 3. Processamento de Comissões

1.  No **Dashboard** ou na aba **Comissões**, selecione o tipo de comissão (Adiantamento, Repasse ou Prêmio).
2.  Arraste o arquivo Excel da comissão para a área de upload.
3.  O sistema irá processar a planilha e gerar automaticamente os **PDFs individuais**.
4.  Após o processamento, os corretores aparecerão na **Fila de Envio**.

---

## 4. Gerenciamento de Arquivos (PDFs)

1.  Acesse a aba **Arquivos**.
2.  Lá você verá todos os PDFs gerados pelo sistema.
3.  Você pode **Visualizar** o PDF direto no navegador, fazer o **Download** ou **Excluir** arquivos antigos para manter o sistema limpo.

---

## 5. Fila de Processamento e Envio de E-mails

Esta é a tela principal de operação:

1.  **Visualizar E-mail**: Clique no ícone de "Olho" para ver como o e-mail será enviado para aquele corretor específico.
2.  **Editar Manualmente**: Se precisar alterar o corpo do e-mail de um corretor específico antes de enviar, você pode editar e salvar. O sistema lembrará dessa edição para esse usuário no futuro.
3.  **Enviar Individual**: Clique no botão de enviar ao lado do nome do corretor.
4.  **Enviar Todos**: Use o botão de envio em massa no topo da página para disparar todos os e-mails pendentes de uma vez.

---

## 6. Customização Visual do E-mail (Editor "Live")

Se quiser mudar o texto padrão que todos os corretores recebem:

1.  Vá em **Configurações**.
2.  No bloco "Parâmetros das Comissões", localize a categoria (ex: Adiantamento) e clique em **PREVIEW**.
3.  Uma tela com o layout do e-mail abrirá. **Clique em qualquer texto** (Título, Corpo, Tabela de CNPJ, Prazo) para editar.
4.  Após fazer as alterações, clique em **SALVAR ALTERAÇÕES** no topo da tela.
5.  A partir desse momento, todos os novos e-mails gerados usarão esse novo modelo.

---

## 💡 Dicas Importantes

-   **Tabela de CNPJ**: A tabela de CNPJs nas configurações é editável. Se um novo empreendimento surgir, você pode adicioná-lo manualmente na tabela dentro do editor de Preview.
-   **Notas Retroativas**: O campo amarelo de "Notas Retroativas" também é editável no editor de Preview.
-   **Supervisores em Cópia**: O sistema busca automaticamente o supervisor vinculado ao empreendimento do corretor. Se não houver supervisor cadastrado para aquele empreendimento, o e-mail será enviado apenas para o corretor.
