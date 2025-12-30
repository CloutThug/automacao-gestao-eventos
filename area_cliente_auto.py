import os.path
from dotenv import load_dotenv
from selenium.webdriver.chrome.options import Options
import time
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# Bibliotecas do Google
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# ==========================================
# CONFIGURAÇÕES
# ==========================================

# 1. Carrega as variáveis de ambiente (Força bruta para achar o arquivo)
caminho_env = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(caminho_env)

# Teste de segurança (Para vermos se carregou)
ID_TESTE = os.getenv('SPREADSHEET_ID')
if not ID_TESTE:
    print("ERRO CRÍTICO: Não consegui ler o SPREADSHEET_ID do arquivo .env")
    print("Verifique se o arquivo .env está na mesma pasta e sem espaços (EX: ID=123)")
    exit()

# Configurações do Google
SCOPES = [
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/spreadsheets'
]
SPREADSHEET_ID = ID_TESTE # Usa o ID que acabamos de carregar
NOME_ABA = 'Controle sistema' #
INTERVALO_LEITURA = f'{NOME_ABA}!A:M'

# 2. Configurações do Site
URL_LOGIN = "https://areadocliente.eventosindaia.com.br/home"
URL_PADRAO_EDICAO = "https://areadocliente.eventosindaia.com.br/eventos-edit?evento-codigo="

# 3. Mapeamento de Pastas (O que procurar no Drive)
MAPA_PASTAS_DRIVE = {
    'link_contrato': ['CONTRATO'],
    'link_os': ['ORDEM DE SERVIÇO', 'ORDEM DE SERVICO'], 
    'link_decoration': ['DECORAÇÃO', 'DECORACAO'],
    'link_layout': ['LAYOUT']
}

# 4. Mapeamento do Site (Campos do HTML)
MAPA_CAMPOS_SITE = {
    "link_contrato": "link_contrato",
    "link_os": "link_os",
    "link_decoration": "link_decoration", 
    "link_layout": "link_layout"
}

# ==========================================
# FUNÇÕES DO GOOGLE (SCANNER + PLANILHA)
# ==========================================

def autenticar_google():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def ler_planilha_filtros(service_sheets):
    print(">>> [1/5] Lendo planilha de controle...")
    sheet = service_sheets.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=INTERVALO_LEITURA).execute()
    rows = result.get('values', [])
    
    eventos_pendentes = []
    
    for i, row in enumerate(rows[1:], start=2):
        if not row: continue
        codigo = row[0].strip()
        if not codigo: continue

        def get_col(idx): return row[idx].strip().upper() if len(row) > idx else ""
        
        # Filtro: H até L = OK e M = Vazio
        col_h, col_i, col_j, col_k, col_l = get_col(7), get_col(8), get_col(9), get_col(10), get_col(11)
        col_m = get_col(12)
        
        if (col_h=="OK" and col_i=="OK" and col_j=="OK" and col_k=="OK" and col_l=="OK") and col_m=="":
            print(f"  [Linha {i}] Evento {codigo} entra na fila.")
            eventos_pendentes.append({"codigo": codigo, "linha": i})
            
    return eventos_pendentes

def buscar_links_drive(service_drive, eventos):
    print(f"\n>>> [2/5] Escaneando Google Drive ({len(eventos)} eventos)...")
    eventos_com_links = []
    
    for evt in eventos:
        codigo = evt['codigo']
        print(f"--> Buscando pastas: {codigo}")
        
        # Busca pasta principal
        query = f"mimeType = 'application/vnd.google-apps.folder' and name contains 'DOCUMENTOS - {codigo}' and trashed = false"
        results = service_drive.files().list(q=query, fields="files(id, name, parents)").execute()
        pastas = results.get('files', [])
        
        if not pastas:
            print(f"    X Pasta 'DOCUMENTOS - {codigo}' não encontrada.")
            continue
            
        # Sobe para pasta Pai e lista conteúdo
        pasta_doc = pastas[0]
        if 'parents' in pasta_doc:
            id_pai = pasta_doc['parents'][0]
            query_tudo = f"'{id_pai}' in parents and trashed = false"
            conteudo = service_drive.files().list(
                q=query_tudo, 
                fields="files(id, name, webViewLink, mimeType)"
            ).execute().get('files', [])
            
            evt_dados = evt.copy() # Copia código e número da linha
            encontrou = False

            for item in conteudo:
                # Só aceita pastas
                if item['mimeType'] != 'application/vnd.google-apps.folder':
                    continue

                nome_pasta = item['name'].upper().strip()
                link = item['webViewLink']
                
                for chave_json, palavras in MAPA_PASTAS_DRIVE.items():
                    if any(p in nome_pasta for p in palavras):
                        evt_dados[chave_json] = link
                        print(f"    ✓ {chave_json}: {item['name']}")
                        encontrou = True
            
            if encontrou:
                eventos_com_links.append(evt_dados)
            else:
                print("    ! Nenhuma pasta relevante encontrada.")
                
    return eventos_com_links

def dar_baixa_planilha(service_sheets, linha):
    """Escreve OK na coluna M da linha especificada."""
    try:
        range_atualizacao = f"{NOME_ABA}!M{linha}"
        body = {'values': [['OK']]}
        service_sheets.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=range_atualizacao,
            valueInputOption="RAW",
            body=body
        ).execute()
        print(f"    ✓ Planilha atualizada (Linha {linha})")
    except Exception as e:
        print(f"    X Erro ao atualizar planilha: {e}")

# ==========================================
# FUNÇÃO PRINCIPAL
# ==========================================
def main():
    # 1. Autenticação
    creds = autenticar_google()
    service_sheets = build('sheets', 'v4', credentials=creds)
    service_drive = build('drive', 'v3', credentials=creds)
    
    # 2. Scanner (Planilha + Drive)
    fila_processamento = ler_planilha_filtros(service_sheets)
    
    if not fila_processamento:
        print("Nenhum evento pendente na planilha.")
        return

    dados_finais = buscar_links_drive(service_drive, fila_processamento)
    

    if not dados_finais:
        print("Nenhum link encontrado no Drive para os eventos pendentes.")
        return

    print(f"\n>>> [3/5] Iniciando Navegador com Perfil Persistente...")
    
    # --- CONFIGURAÇÃO DO PERFIL SALVO ---
    chrome_options = Options()
    # Cria uma pasta "perfil_chrome" dentro do seu projeto para salvar o login
    caminho_perfil = os.path.join(os.getcwd(), "perfil_chrome")
    chrome_options.add_argument(f"user-data-dir={caminho_perfil}") 
    
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
    wait = WebDriverWait(driver, 20)

    try:
        # Tenta acessar a Home
        driver.get("https://areadocliente.eventosindaia.com.br/home")
        time.sleep(3) # Espera um pouco para ver se redireciona

        # --- LÓGICA DE LOGIN INTELIGENTE ---
        # Verifica se caiu na tela de login (url mudou ou tem campo de senha)
        if "login" in driver.current_url or len(driver.find_elements(By.NAME, "password")) > 0:
            print("\n" + "="*50)
            print(">>> NÃO ESTAMOS LOGADOS (PRIMEIRO ACESSO OU SESSÃO EXPIROU) <<<")
            print("1. O navegador abriu.")
            print("2. Faça o login manualmente e marque 'Lembrar-me'.")
            print("3. Volte aqui e pressione ENTER.")
            print("="*50 + "\n")
            input()
        else:
            print("  ✓ Login recuperado com sucesso! Seguindo direto...")

        # Loop de Preenchimento (Continua igual ao seu código anterior)
        print(">>> [4/5] Preenchendo Site e Atualizando Planilha...")
        
        # ... (Restante do código: for item in dados_finais...)
        
        for item in dados_finais:
            codigo = item['codigo']
            linha_planilha = item['linha']
            print(f"\nProcessando: {codigo}...")
            
            try:
                # Navega
                driver.get(f"{URL_PADRAO_EDICAO}{codigo}")
                
                # Verifica carregamento
                try:
                    wait.until(EC.visibility_of_element_located((By.NAME, "link_contrato")))
                except:
                    print(f"  X Site não carregou para {codigo}.")
                    continue

                # Preenche
                preencheu = False
                for campo_site, chave_dados in MAPA_CAMPOS_SITE.items():
                    valor = item.get(chave_dados)
                    if valor:
                        try:
                            elm = driver.find_element(By.NAME, campo_site)
                            elm.clear()
                            elm.send_keys(valor)
                            preencheu = True
                        except:
                            pass
                
                # Salva e Dá Baixa
                if preencheu:
                    botao = driver.find_element(By.XPATH, "//button[contains(., 'Salvar')]")
                    
                    # CLIQUE REAL
                    botao.click()
                    print("  ✓ Salvo no Site.")
                    time.sleep(2) 
                    
                    # Atualiza Planilha
                    dar_baixa_planilha(service_sheets, linha_planilha)
                else:
                    print("  ! Nada preenchido (faltam links no Drive).")

            except Exception as e:
                print(f"  X Erro no navegador: {e}")
                driver.save_screenshot(f"erro_{codigo}.png")

        print("\n>>> [5/5] PROCESSO CONCLUÍDO COM SUCESSO! <<<")

    except Exception as e:
        print(f"Erro fatal: {e}")
    finally:
        input("Pressione ENTER para fechar...")
        driver.quit()

if __name__ == '__main__':
    main()