# 🤖 Automação de Gestão de Eventos (Indaiá Eventos)

Este projeto é uma solução de **RPA (Robotic Process Automation)** desenvolvida para automatizar o fluxo de cadastro e atualização de eventos entre planilhas de controle e o sistema web corporativo.

## 🚀 O Problema Resolvido
O processo manual exigia buscar links em pastas do Google Drive, logar no sistema, preencher formulários repetitivos e atualizar planilhas manualmente. Isso consumia horas e gerava erros humanos.

## 🛠️ Tecnologias Utilizadas
- **Python 3.13**
- **Selenium WebDriver:** Automação de interface web e interação com DOM.
- **Google Drive API v3:** Busca avançada de arquivos e pastas na nuvem.
- **Google Sheets API v4:** Leitura e escrita de dados em tempo real.
- **OAuth 2.0:** Autenticação segura.

## ⚙️ Funcionalidades
1. **Scanner Inteligente:** Lê a planilha de controle e identifica eventos pendentes.
2. **Busca no Drive:** Localiza pastas contratuais (Contrato, OS, Layout) usando lógica de palavras-chave para evitar erros.
3. **Preenchimento Web:** Acessa o CRM da empresa, preenche os links encontrados e salva as alterações.
4. **Feedback Automático:** Retorna à planilha original e marca o status como "OK" após o sucesso.

## 📦 Como rodar este projeto
1. Clone o repositório.
2. Instale as dependências:
   ```bash
   pip install -r requirements.txt