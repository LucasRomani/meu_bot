import time
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

# Importa a classe do outro arquivo
from bot_ncm_editor import BotNCMEditor 

class BotSischef:
    # Definindo as URLs como constantes
    URL_VERIFICACAO_CONEXAO = "http://www.google.com" 
    URL_LISTAGEM_PRODUTOS = "https://sistema.sischef.com/admin/produtos/produtoList.jsf"
    URL_CADASTRO_PRODUTO = "https://sistema.sischef.com/admin/produtos/produto.jsf"
    
    # Seletor do campo de busca na listagem de produtos
    ID_CAMPO_BUSCA_LISTAGEM = "_input-busca-generica_" 
    
    # Seletor XPATH para a barra de notificação de ERRO
    SELECTOR_ERRO_GLOBAL = "//div[contains(@class, 'ui-growl-item-container') and contains(@class, 'ui-state-error')]"

    def __init__(self, usuario, senha):
        if not usuario or not senha:
            raise ValueError("Usuário e senha não podem ser vazios!")
        self.usuario = usuario
        self.senha = senha
        
        # O nome da variável é 'arquivo_csv_cadastro' (usado no método de cadastro)
        self.arquivo_csv_cadastro = None 
        
        self.driver = None
        self.rodando = True # Flag para parada

    def _verificar_conexao(self):
        """Verifica se há conexão ativa com a internet."""
        try:
            requests.get(self.URL_VERIFICACAO_CONEXAO, timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    def iniciar(self):
        print("🔹 Abrindo navegador Sischef...")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        
        try:
            # Usa o WebDriverManager
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            # Tenta fallback se o WebDriverManager falhar
            try:
                print("⚠️ WebDriverManager falhou, tentando fallback...")
                self.driver = webdriver.Chrome(options=options)
            except Exception as e_fallback:
                 raise Exception(f"Erro ao iniciar o bot (Chrome/Driver): {e_fallback}")

        # 1. Login
        self.driver.get("https://sistema.sischef.com")
        wait = WebDriverWait(self.driver, 10) 
        
        wait.until(EC.presence_of_element_located((By.ID, "j_username")))
        time.sleep(1) # Pausa para JS

        self.driver.find_element(By.ID, "j_username").send_keys(self.usuario)
        self.driver.find_element(By.ID, "j_password").send_keys(self.senha)
        time.sleep(0.5)
        self.driver.find_element(By.ID, "login").click()

        # 2. VALIDAÇÃO PÓS-LOGIN
        print(f"🔄 Redirecionando para a lista de produtos: {self.URL_LISTAGEM_PRODUTOS}")
        self.driver.get(self.URL_LISTAGEM_PRODUTOS)
        
        try:
            WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA_LISTAGEM))
            )
            print("✅ Login realizado e tela de listagem de produtos carregada.")
        except TimeoutException:
            raise Exception(f"Timeout: A tela de listagem de produtos não carregou. Verifique as credenciais.")
            
    def cadastrar_produtos(self, callback_progresso=None, callback_rodando=None):
        if not self.arquivo_csv_cadastro: 
            print("❌ Nenhum arquivo CSV de Cadastro selecionado.")
            return

        try:
            dados = pd.read_csv(self.arquivo_csv_cadastro, 
                                dtype={'Grupo': str, 'NCM': str, 'UnidadeMedida': str})
        except Exception as e:
            raise ValueError(f"❌ Erro ao ler o CSV: {e}")

        # 1. Navega para a tela de cadastro e clica em "Novo"
        self.driver.get(self.URL_CADASTRO_PRODUTO)
        wait = WebDriverWait(self.driver, 10)
        try:
            wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
            try:
                botao_novo = wait.until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.mui-btn.mui-btn-text"))
                )
                botao_novo.click()
                print("🔄 Direcionando para novo produto.")
                time.sleep(1)
                wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao"))) 
            except Exception as e:
                print(f"⚠️ Não foi possível clicar em 'Novo'. Prosseguindo. Erro: {e}")
        except Exception as e:
            raise Exception(f"❌ Não foi possível carregar a tela de cadastro: {e}")
            
        print("✅ Tela de cadastro de produtos pronta!")

        mapeamento_campos = {
            "Descricao": "tabSessoesProduto:descricao",
            "Grupo": "tabSessoesProduto:grupoProduto_input",
            "UnidadeMedida": "tabSessoesProduto:unidadeMedida", 
            "CodigoBarras": "tabSessoesProduto:codigoBarras",
            "NCM": "tabSessoesProduto:ncm",
            "PrecoCompra": "tabSessoesProduto:valorUnitarioCompra",
            "PrecoVenda": "tabSessoesProduto:valorUnitarioVenda"
        }

        # Validação das colunas
        for col in mapeamento_campos.keys():
            if col not in dados.columns:
                # Tenta encontrar com letras minúsculas
                if col.lower() not in dados.columns:
                    raise ValueError(f"❌ Coluna '{col}' não encontrada no CSV!")
                else:
                    # Renomeia a coluna no DataFrame
                    dados.rename(columns={col.lower(): col}, inplace=True)


        total = len(dados)
        print(f"📦 Total de produtos a cadastrar: {total}")
        
        is_rodando = callback_rodando if callback_rodando else lambda: True
        produto_index_atual = 0
        
        while produto_index_atual < total:
            
            if not is_rodando():
                print("ℹ️ Cadastro Sischef interrompido pelo usuário.")
                break 
            
            i = produto_index_atual
            row = dados.iloc[i]
            produto_descricao = str(row['Descricao']).strip()

            if not self._verificar_conexao():
                if callback_progresso:
                    callback_progresso(i, total, "🚨 CONEXÃO PERDIDA. PAUSANDO...")
                while not self._verificar_conexao():
                    if not is_rodando():
                        print("ℹ️ Cadastro Sischef interrompido (sem conexão).")
                        return
                    time.sleep(10)
                if callback_progresso:
                    self.driver.get(self.URL_CADASTRO_PRODUTO) 
                    WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
                    callback_progresso(i, total, "🟢 CONEXÃO RESTABELECIDA. RETOMANDO...")
            
            if callback_progresso:
                callback_progresso(i + 1, total, f"🔹 Cadastrando produto {i+1}/{total}: {produto_descricao}")

            try:
                for col_csv, campo_id in mapeamento_campos.items():
                    # Trata o caso de a coluna não existir (ex: 'UnidadeMedida' pode faltar)
                    if col_csv not in row:
                        print(f"⚠️ Coluna '{col_csv}' não encontrada na linha {i+1}, pulando campo.")
                        continue
                        
                    valor = str(row[col_csv]).strip()
                    
                    if col_csv == 'Grupo' and valor.endswith('.0'):
                        valor = valor[:-2]
                    if campo_id in ["tabSessoesProduto:valorUnitarioCompra", "tabSessoesProduto:valorUnitarioVenda"]:
                        try:
                            valor_numerico = float(valor.replace(",", "."))
                            valor = f"{valor_numerico:.2f}".replace(".", ",") 
                        except ValueError:
                            valor = "0,00"

                    input_elem = wait.until(EC.element_to_be_clickable((By.ID, campo_id)))
                    
                    if campo_id == "tabSessoesProduto:unidadeMedida":
                        if valor: # Só tenta selecionar se houver um valor
                            Select(input_elem).select_by_value(valor)
                            time.sleep(0.5) 
                        continue 
                    
                    input_elem.clear()
                    time.sleep(0.5) 
                    input_elem.send_keys(valor)
                    time.sleep(0.3)
                    
                    if campo_id == "tabSessoesProduto:grupoProduto_input":
                        time.sleep(1)
                        input_elem.send_keys(u'\ue007')
                
                self.driver.find_element(By.ID, "tabSessoesProduto:descricao").click()
                time.sleep(0.3)
                self.driver.find_element(By.ID, "tabSessoesProduto:descricao").send_keys(Keys.ALT, "s")
                
                try:
                    erro_container = WebDriverWait(self.driver, 0.8).until(
                        EC.presence_of_element_located((By.XPATH, self.SELECTOR_ERRO_GLOBAL))
                    )
                    erro_msg = erro_container.find_element(By.TAG_NAME, 'p').text
                    raise Exception(f"ERRO DE VALIDAÇÃO: {erro_msg}. Cadastro pausado.")
                except TimeoutException:
                    print("💾 Produto salvo.")
                except Exception as e:
                    if callback_progresso:
                        callback_progresso(i + 1, total, f"❌ {str(e)}")
                    raise e
                
                time.sleep(0.5)

                botao_novo = WebDriverWait(self.driver, 1.5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.mui-btn.mui-btn-text"))
                )
                botao_novo.click()
                time.sleep(0.8)

                produto_index_atual += 1 
                if callback_progresso:
                    callback_progresso(i + 1, total, f"✅ Produto {i+1}/{total} SALVO com sucesso!")

            except Exception as e:
                print(f"❌ Falha no ciclo do produto {i+1}: {e}")
                if "ERRO DE VALIDAÇÃO" in str(e):
                    raise e
                if isinstance(e, (TimeoutException, WebDriverException)):
                    raise Exception(f"❌ Erro de Sincronização. Processo pausado.")
                raise Exception(f"❌ Falha inesperada: {e}")

        print("✅ Cadastro de todos os produtos concluído!")
        return True
        
    def editar_ncm(self, arquivo_csv, callback_progresso):
        """Delega a tarefa de edição de NCM para a classe BotNCMEditor."""
        if not self.driver:
            raise Exception("Navegador não iniciado. Execute 'iniciar' primeiro.")

        if not arquivo_csv:
            raise FileNotFoundError("Caminho do CSV de NCM não definido.")
            
        print(f"Iniciando BotNCMEditor com CSV: {arquivo_csv}")

        ncm_editor = BotNCMEditor(
            driver=self.driver, 
            csv_path=arquivo_csv,
            callback_progresso=callback_progresso
        )
        
        ncm_editor.editar_ncm() # Chama o método da outra classe
        
        return True

    def fechar(self):
        self.rodando = False
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Navegador Sischef fechado.")
            except Exception as e:
                print(f"❌ Erro ao fechar Sischef: {e}")
            finally:
                self.driver = None