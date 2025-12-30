import json
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# --- CONFIGURAÇÕES ---
URL_LOGIN = "https://areadocliente.eventosindaia.com.br/home"
URL_PADRAO_EDICAO = "https://areadocliente.eventosindaia.com.br/eventos-edit?evento-codigo="

# --- CARREGAR DADOS ---
try:
    with open('db.json', 'r', encoding='utf-8') as file:
        data = json.load(file)
    print(f"Carregados {len(data)} eventos para processar.")
except FileNotFoundError:
    print("ERRO: O arquivo 'db.json' não foi encontrado na pasta.")
    exit()

# --- INICIAR ROBÔ ---
print(">>> Iniciando navegador...")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
wait = WebDriverWait(driver, 20)

try:
    # 1. ACESSO E LOGIN
    driver.get(URL_LOGIN)
    
    print("\n" + "="*50)
    print(">>> PAUSA PARA LOGIN MANUAL <<<")
    print("1. Faça o login.")
    print("2. Espere carregar a tela inicial.")
    print("3. Volte aqui e pressione ENTER.")
    print("="*50 + "\n")
    input() 

    # 2. LOOP PELOS EVENTOS
    for item in data:
        codigo = item.get('codigo')
        print(f"\nProcessando evento: {codigo}...")

        try:
            # Navegação Direta
            link_direto = f"{URL_PADRAO_EDICAO}{codigo}"
            print(f"  > Acessando: {link_direto}")
            driver.get(link_direto)

            # Aguarda carregamento
            print("  > Preenchendo campos...")
            try:
                wait.until(EC.visibility_of_element_located((By.NAME, "link_contrato")))
            except:
                print(f"  X ERRO: Página do evento {codigo} não carregou ou evento inválido.")
                continue 

            # Mapeamento e Preenchimento
            mapa_campos = {
                "link_contrato": "link_contrato",
                "link_os": "link_os",
                "link_decoration": "link_decoration", 
                "link_layout": "link_layout",
                "link_cardapio": "link_cardapio",
                "link_check_list": "link_check_list"
            }

            preencheu_algo = False
            for campo_html, chave_json in mapa_campos.items():
                valor = item.get(chave_json)
                if valor:
                    try:
                        input_campo = driver.find_element(By.NAME, campo_html)
                        input_campo.clear()
                        input_campo.send_keys(valor)
                        preencheu_algo = True
                        print(f"    ✓ {campo_html}")
                    except:
                        pass # Campo não existe na tela, segue o jogo

            # --- AQUI ESTÁ A MUDANÇA: SALVAR ATIVADO ---
            if preencheu_algo:
                try:
                    botao_salvar = driver.find_element(By.XPATH, "//button[contains(., 'Salvar')]")
                    
                    # O CLIQUE AGORA É REAL:
                    botao_salvar.click()
                    
                    print("  ✓ SALVO COM SUCESSO!")
                    
                    # Pausa de 3 segundos para o site processar o envio antes de mudar de página
                    time.sleep(3) 
                except:
                    print("  X ERRO: Botão de Salvar não encontrado!")
            else:
                print("  ! Nenhum dado novo para preencher neste evento.")

        except Exception as e:
            print(f"  X ERRO CRÍTICO no evento {codigo}: {e}")
            driver.save_screenshot(f"erro_{codigo}.png")

    print("\n" + "="*50)
    print(">>> FIM DO PROCESSO <<<")
    print("="*50)

except Exception as e:
    print(f"Erro fatal: {e}")

input("Pressione ENTER para fechar...")
driver.quit()