import os.path
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- CONFIGURAÇÕES ---
SCOPES = [
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/spreadsheets.readonly'
]

# ID da sua planilha e aba
SPREADSHEET_ID = '1aHdRcZAc9uTGErnScxCgNQHGB1l0Rq5N5KGqVHDypUU'
NOME_ABA = 'Controle sistema' # Confirme se é Página1 ou Controle sistema
INTERVALO = f'{NOME_ABA}!A:M'

# --- MAPEAMENTO CORRIGIDO (SEM CONFUSÃO) ---
MAPA_NOMES = {
    'link_contrato': ['CONTRATO'],
    # REMOVIDO "OS" e "O.S." para não confundir com "DADOS", "FOTOS", "ADITIVOS"
    'link_os': ['ORDEM DE SERVIÇO', 'ORDEM DE SERVICO'], 
    'link_decoration': ['DECORAÇÃO', 'DECORACAO'],
    'link_layout': ['LAYOUT']
}

def autenticar_google():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists('credentials.json'):
                print("ERRO: 'credentials.json' não encontrado!")
                exit()
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def ler_eventos_para_processar(service_sheets):
    print(">>> Lendo planilha de controle...")
    sheet = service_sheets.spreadsheets()
    result = sheet.values().get(spreadsheetId=SPREADSHEET_ID, range=INTERVALO).execute()
    rows = result.get('values', [])
    
    eventos_filtrados = []
    
    for i, row in enumerate(rows[1:], start=2):
        if not row: continue
        codigo = row[0].strip()
        if not codigo: continue

        # Função segura para pegar coluna
        def get_col(idx): return row[idx].strip().upper() if len(row) > idx else ""
        
        # Colunas H(7) a L(11) = OK, M(12) = Vazio
        col_h, col_i, col_j, col_k, col_l = get_col(7), get_col(8), get_col(9), get_col(10), get_col(11)
        col_m = get_col(12)
        
        if (col_h=="OK" and col_i=="OK" and col_j=="OK" and col_k=="OK" and col_l=="OK") and col_m=="":
            print(f"  [Linha {i}] Evento {codigo} aprovado.")
            eventos_filtrados.append(codigo)
            
    return eventos_filtrados

def buscar_links_no_drive(service_drive, lista_codigos):
    print(f"\n>>> Buscando arquivos no Drive para {len(lista_codigos)} eventos...")
    dados_finais = []
    
    for codigo in lista_codigos:
        print(f"--> Procurando pastas do evento: {codigo}")
        
        # 1. Busca a pasta âncora "DOCUMENTOS - E..."
        query = f"mimeType = 'application/vnd.google-apps.folder' and name contains 'DOCUMENTOS - {codigo}' and trashed = false"
        results = service_drive.files().list(q=query, fields="files(id, name, parents)").execute()
        pastas = results.get('files', [])
        
        if not pastas:
            print(f"    X Pasta 'DOCUMENTOS - {codigo}' não encontrada.")
            continue
            
        pasta_doc = pastas[0]
        
        # 2. Sobe para a pasta Pai (onde estão Contrato, OS, Layout...)
        if 'parents' in pasta_doc:
            id_pasta_evento = pasta_doc['parents'][0]
            
            # Pega TUDO o que tem na pasta do evento
            query_conteudo = f"'{id_pasta_evento}' in parents and trashed = false"
            conteudo = service_drive.files().list(
                q=query_conteudo, 
                fields="files(id, name, webViewLink, mimeType)" # Adicionei mimeType
            ).execute().get('files', [])
            
            evento_obj = {"codigo": codigo}
            
            for item in conteudo:
                # --- NOVO FILTRO: SÓ ACEITA SE FOR PASTA ---
                # Isso impede que ele pegue arquivos PDF soltos
                if item['mimeType'] != 'application/vnd.google-apps.folder':
                    continue

                nome_pasta = item['name'].upper()
                link = item['webViewLink']
                
                for chave_json, palavras in MAPA_NOMES.items():
                    # Verifica se contém a palavra chave (Ex: CONTRATO)
                    if any(p in nome_pasta for p in palavras):
                        evento_obj[chave_json] = link
                        print(f"    ✓ {chave_json}: {item['name']}")
            
            dados_finais.append(evento_obj)
            
    return dados_finais

def main():
    creds = autenticar_google()
    service_sheets = build('sheets', 'v4', credentials=creds)
    service_drive = build('drive', 'v3', credentials=creds)
    
    codigos = ler_eventos_para_processar(service_sheets)
    
    if codigos:
        resultado = buscar_links_no_drive(service_drive, codigos)
        with open('db.json', 'w', encoding='utf-8') as f:
            json.dump(resultado, f, indent=4, ensure_ascii=False)
        print("\n" + "="*50)
        print(f"SUCESSO! {len(resultado)} eventos salvos.")
    else:
        print("Nenhum evento na fila.")

if __name__ == '__main__':
    main()