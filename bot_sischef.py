import time
import pandas as pd
import requests
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

# Importa a classe do outro arquivo
from bot_ncm_editor import BotNCMEditor 

class BotSischef:
    # --- CONSTANTES ---
    URL_VERIFICACAO_CONEXAO = "http://www.google.com" 
    URL_LISTAGEM_PRODUTOS = "https://sistema.sischef.com/admin/produtos/produtoList.jsf"
    URL_CADASTRO_PRODUTO = "https://sistema.sischef.com/admin/produtos/produto.jsf"
    
    ID_CAMPO_BUSCA_LISTAGEM = "_input-busca-generica_" 
    
    # Seletor para QUALQUER pop-up de mensagem (erro, aviso, sucesso)
    SELECTOR_MENSAGEM_POPUP = "//div[contains(@class, 'ui-growl-item-container')]"
    SELECTOR_ERRO_GLOBAL = f"{SELECTOR_MENSAGEM_POPUP}[contains(@class, 'ui-state-error')]" # Apenas Erros
    
    # Seletor do pop-up modal que trava a tela
    SELECTOR_MODAL_INTERCEPT = "div[id$='ajaxErrorHandlerDialog_modal']"


    def __init__(self, usuario, senha, log_callback=None):
        if not usuario or not senha:
            raise ValueError("Usuário e senha não podem ser vazios!")
        self.usuario = usuario
        self.senha = senha
        
        self.arquivo_csv_cadastro = None 
        
        self.driver = None
        self.rodando = True
        self.start_index = 0 # Para cadastro
        self.start_index_ncm = 0 # Para NCM
        
        self.log = log_callback if log_callback else print

    def _verificar_conexao(self):
        """Verifica se há conexão ativa com a internet."""
        try:
            requests.get(self.URL_VERIFICACAO_CONEXAO, timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    def iniciar(self):
        self.log("🔹 Abrindo navegador Sischef...")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        
        try:
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
        except Exception as e:
            try:
                self.log(f"⚠️ WebDriverManager falhou ({e}), tentando fallback...")
                self.driver = webdriver.Chrome(options=options)
            except Exception as e_fallback:
                 raise Exception(f"Erro ao iniciar o bot (Chrome/Driver): {e_fallback}")

        # 1. Login
        self.driver.get("https://sistema.sischef.com")
        wait = WebDriverWait(self.driver, 10) 
        
        wait.until(EC.presence_of_element_located((By.ID, "j_username")))
        time.sleep(1)

        self.driver.find_element(By.ID, "j_username").send_keys(self.usuario)
        self.driver.find_element(By.ID, "j_password").send_keys(self.senha)
        time.sleep(0.5)
        self.driver.find_element(By.ID, "login").click()

        # 2. VALIDAÇÃO PÓS-LOGIN
        self.log(f"🔄 Redirecionando para a lista de produtos: {self.URL_LISTAGEM_PRODUTOS}")
        self.driver.get(self.URL_LISTAGEM_PRODUTOS)
        
        try:
            WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA_LISTAGEM))
            )
            self.log("✅ Login realizado e tela de listagem de produtos carregada.")
        except TimeoutException:
            raise Exception(f"Timeout: A tela de listagem de produtos não carregou. Verifique as credenciais.")
            
    def cadastrar_produtos(self, callback_progresso=None, callback_rodando=None):
        if not self.arquivo_csv_cadastro: 
            self.log("❌ Nenhum arquivo CSV de Cadastro selecionado.")
            return

        try:
            # Força a leitura de colunas problemáticas como string
            dados = pd.read_csv(self.arquivo_csv_cadastro, 
                                dtype={'Grupo': str, 'NCM': str, 'UnidadeMedida': str, 'CodigoBarras': str})
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
                self.log("🔄 Direcionando para novo produto.")
                time.sleep(1)
                wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao"))) 
            except Exception as e:
                self.log(f"⚠️ Não foi possível clicar em 'Novo'. Prosseguindo. Erro: {e}")
        except Exception as e:
            raise Exception(f"❌ Não foi possível carregar a tela de cadastro: {e}")
            
        self.log("✅ Tela de cadastro de produtos pronta!")

        mapeamento_campos = {
            "Descricao": "tabSessoesProduto:descricao",
            "Grupo": "tabSessoesProduto:grupoProduto_input",
            "UnidadeMedida": "tabSessoesProduto:unidadeMedida", 
            "CodigoBarras": "tabSessoesProduto:codigoBarras",
            "NCM": "tabSessoesProduto:ncm",
            "PrecoCompra": "tabSessoesProduto:valorUnitarioCompra",
            "PrecoVenda": "tabSessoesProduto:valorUnitarioVenda"
        }

        # Validação de Colunas (sensível a maiúsculas/minúsculas)
        dados.columns = [col.lower() for col in dados.columns]
        mapeamento_lower = {k.lower(): v for k, v in mapeamento_campos.items()}
        
        colunas_encontradas = {}
        for col_csv_lower, campo_id in mapeamento_lower.items():
            if col_csv_lower in dados.columns:
                 # Renomeia o dataframe para o nome 'bonito' (ex: "Descricao")
                original_capitalized_key = next(k for k, v in mapeamento_campos.items() if v == campo_id)
                dados.rename(columns={col_csv_lower: original_capitalized_key}, inplace=True)
                colunas_encontradas[original_capitalized_key] = campo_id
            else:
                self.log(f"⚠️ Coluna '{col_csv_lower}' não encontrada no CSV. Este campo será pulado.")
        
        total = len(dados)
        self.log(f"📦 Total de produtos a cadastrar: {total} (Campos mapeados: {list(colunas_encontradas.keys())})")
        
        is_rodando = callback_rodando if callback_rodando else lambda: True
        
        produto_index_atual = self.start_index # Começa de onde parou
        
        while produto_index_atual < total:
            
            if not is_rodando():
                self.log("ℹ️ Cadastro Sischef interrompido pelo usuário.")
                break 
            
            i = produto_index_atual
            row = dados.iloc[i]
            produto_descricao = str(row.get('Descricao', f'ITEM {i+1} SEM DESCRIÇÃO')).strip() 

            # Bloco de verificação de conexão
            if not self._verificar_conexao():
                self.log("🚨 CONEXÃO PERDIDA. PAUSANDO...")
                if callback_progresso:
                    callback_progresso(i, total, None) 
                while not self._verificar_conexao():
                    if not is_rodando():
                        self.log("ℹ️ Cadastro Sischef interrompido (sem conexão).")
                        return
                    time.sleep(10)
                
                self.log("🟢 CONEXÃO RESTABELECIDA. RETOMANDO...")
                self.driver.get(self.URL_CADASTRO_PRODUTO) 
                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
                if callback_progresso:
                    callback_progresso(i, total, None)
            
            log_msg_sischef = f"🔹 Cadastrando produto {i+1}/{total}: {produto_descricao}"
            self.log(log_msg_sischef)
            if callback_progresso:
                callback_progresso(i + 1, total, None) # Atualiza contador sem log

            try:
                codigo_barras_original = str(row.get("CodigoBarras", "")).strip()
                # Passa apenas as colunas que o CSV realmente tem
                self._preencher_e_salvar_sischef(wait, row, colunas_encontradas)

                # --- VERIFICAÇÃO DE ERRO/DUPLICATA ---
                try:
                    # Espera por QUALQUER mensagem de pop-up (Erro ou Aviso)
                    msg_container = WebDriverWait(self.driver, 1.5).until(
                        EC.presence_of_element_located((By.XPATH, self.SELECTOR_MENSAGEM_POPUP))
                    )
                    
                    msg_text = msg_container.find_element(By.TAG_NAME, 'p').text
                    
                    # LÓGICA DE CORREÇÃO DE CÓDIGO DE BARRAS
                    if "código de barras já cadastrado" in msg_text.lower():
                        self.log(f"🔔 Duplicata detectada: {msg_text}")
                        self._tentar_novo_codigo_barras(wait, row, colunas_encontradas, codigo_barras_original)
                    else:
                        # É um erro vermelho e fatal
                        raise Exception(f"ERRO DE VALIDAÇÃO: {msg_text}.")

                except TimeoutException:
                    # Nenhum pop-up apareceu = Sucesso
                    self.log("💾 Produto salvo.")
                
                time.sleep(0.5)

                # --- CLICAR EM "NOVO" ---
                try:
                    botao_novo = WebDriverWait(self.driver, 1.5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.mui-btn.mui-btn-text"))
                    )
                    botao_novo.click()
                    time.sleep(0.8) # Espera a tela recarregar
                
                # --- CORREÇÃO: Pega o erro 'ElementClickInterceptedException' ---
                except ElementClickInterceptedException as e_click:
                    self.log(f"⚠️ Pop-up de erro interceptou o clique em 'Novo'. Tentando fechar...")
                    try:
                        # Tenta fechar o modal de erro (que é o 'ajaxErrorHandlerDialog_modal')
                        self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                        time.sleep(1)
                        # Tenta clicar em "Novo" novamente após fechar
                        botao_novo = WebDriverWait(self.driver, 1.5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, "a.mui-btn.mui-btn-text"))
                        )
                        botao_novo.click()
                        time.sleep(0.8)
                    except Exception as e_fechar:
                        # --- MODIFICADO: PULA O ITEM ---
                        self.log(f"❌ NÃO FOI POSSÍVEL FECHAR O MODAL DE ERRO. PULANDO ESTE ITEM.")
                        self.log(f"❌ ITEM PULADO: {produto_descricao} (Índice {i + 1})")
                        # Recarrega a página para garantir um estado limpo
                        self.driver.get(self.URL_CADASTRO_PRODUTO)
                        wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
                # --- FIM DA CORREÇÃO ---

                # Atualiza o Índice e a Mensagem de Sucesso
                produto_index_atual += 1 
                log_msg_sischef = f"✅ Produto {i+1}/{total} SALVO com sucesso!"
                # self.log(log_msg_sischef) # Já logado pelo callback
                if callback_progresso:
                    callback_progresso(i + 1, total, log_msg_sischef)

            except Exception as e:
                # --- MODIFICADO: PULA O ITEM ---
                self.log(f"❌ Falha no ciclo do produto {i+1}: {e}")
                self.log(f"❌ ITEM PULADO: {produto_descricao} (Índice {i + 1})")
                
                # Avança o índice para não tentar este item novamente
                produto_index_atual += 1 
                
                # Tenta recarregar a página para o próximo item
                try:
                    self.log("... Recarregando a página para o próximo item.")
                    self.driver.get(self.URL_CADASTRO_PRODUTO)
                    wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
                except Exception as e_reload:
                    raise Exception(f"❌ Falha crítica ao tentar recarregar a página após erro. {e_reload}")

        # Se o loop terminou (não foi pausado), reseta o índice
        if produto_index_atual == total and is_rodando():
            self.start_index = 0
            
        self.log("✅ Cadastro de todos os produtos concluído!")
        return True

    def _preencher_e_salvar_sischef(self, wait, row_data, mapeamento_encontrado):
        """Função interna para preencher e salvar o formulário Sischef."""
        for col_csv, campo_id in mapeamento_encontrado.items():
            # A coluna JÁ FOI validada, então podemos usar .get()
            valor = str(row_data.get(col_csv, "")).strip()
            
            if col_csv == 'Grupo' and valor.endswith('.0'):
                valor = valor[:-2]
            if campo_id in ["tabSessoesProduto:valorUnitarioCompra", "tabSessoesProduto:valorUnitarioVenda"]:
                try:
                    valor_numerico = float(valor.replace(",", "."))
                    valor = f"{valor_numerico:.2f}".replace(".", ",") 
                except ValueError:
                    # self.log(f"⚠️ Valor inválido no campo {col_csv}: '{valor}'. Usando '0,00'.")
                    valor = "0,00"

            input_elem = wait.until(EC.element_to_be_clickable((By.ID, campo_id)))
            
            if campo_id == "tabSessoesProduto:unidadeMedida":
                if valor:
                    try:
                        Select(input_elem).select_by_value(valor)
                    except Exception as e_select:
                        self.log(f"⚠️ Falha ao selecionar UnidadeMedida '{valor}'. {e_select}")
                    time.sleep(0.5) 
                continue 
            
            input_elem.clear()
            time.sleep(0.5) 
            input_elem.send_keys(valor)
            time.sleep(0.3)
            
            if campo_id == "tabSessoesProduto:grupoProduto_input":
                time.sleep(1)
                input_elem.send_keys(u'\ue007')
        
        # Salvar via Alt + S
        self.driver.find_element(By.ID, "tabSessoesProduto:descricao").click()
        time.sleep(0.3)
        self.driver.find_element(By.ID, "tabSessoesProduto:descricao").send_keys(Keys.ALT, "s")

    def _tentar_novo_codigo_barras(self, wait, row_data, mapeamento_encontrado, codigo_original):
        """[NOVA FUNÇÃO] Tenta cadastrar novamente com um código de barras aleatório."""
        try:
            novo_codigo = f"{codigo_original}-{random.randint(100, 999)}"
            self.log(f"🔔 Tentando novamente com o código: {novo_codigo}")
            
            # Atualiza o valor na 'row' (para o caso de falhar de novo)
            row_data["CodigoBarras"] = novo_codigo
            
            # Encontra apenas o campo do código de barras e o atualiza
            campo_id_cb = mapeamento_encontrado.get("CodigoBarras")
            if not campo_id_cb:
                raise Exception("Campo 'CodigoBarras' não está no mapeamento.")

            input_elem = wait.until(EC.element_to_be_clickable((By.ID, campo_id_cb)))
            input_elem.clear()
            time.sleep(0.5) 
            input_elem.send_keys(novo_codigo)
            time.sleep(0.3)
            
            # Salva novamente
            self.driver.find_element(By.ID, "tabSessoesProduto:descricao").click()
            time.sleep(0.3)
            self.driver.find_element(By.ID, "tabSessoesProduto:descricao").send_keys(Keys.ALT, "s")
            
            # Verifica se deu erro DE NOVO
            try:
                erro_container = WebDriverWait(self.driver, 1.5).until(
                    EC.presence_of_element_located((By.XPATH, self.SELECTOR_MENSAGEM_POPUP))
                )
                msg_text = erro_container.find_element(By.TAG_NAME, 'p').text
                raise Exception(f"ERRO DE VALIDAÇÃO (2ª tentativa): {msg_text}.")
            
            except TimeoutException:
                # Nenhuma mensagem = SUCESSO na 2ª tentativa
                self.log("💾 Produto salvo (na 2ª tentativa).")
                
        except Exception as e:
            self.log(f"❌ Falha na segunda tentativa de salvamento: {e}")
            raise e # Para o bot
        
    def editar_ncm(self, arquivo_csv, callback_progresso):
        """Delega a tarefa de edição de NCM para a classe BotNCMEditor."""
        if not self.driver:
            raise Exception("Navegador não iniciado. Execute 'iniciar' primeiro.")

        if not arquivo_csv:
            raise FileNotFoundError("Caminho do CSV de NCM não definido.")
            
        self.log(f"Iniciando BotNCMEditor com CSV: {arquivo_csv}")

        ncm_editor = BotNCMEditor(
            driver=self.driver, 
            csv_path=arquivo_csv,
            callback_progresso=callback_progresso,
            log_callback=self.log,
            start_index=self.start_index_ncm # Passa o índice inicial
        )
        
        ncm_editor.editar_ncm()
        return True

    def fechar(self):
        self.rodando = False
        if self.driver:
            try:
                self.driver.quit()
                self.log("✅ Navegador Sischef fechado.")
            except Exception as e:
                self.log(f"❌ Erro ao fechar Sischef: {e}")
            finally:
                self.driver = None