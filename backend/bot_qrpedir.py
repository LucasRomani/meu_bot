import time
import pandas as pd
import requests 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import WebDriverException, TimeoutException 
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService

class BotQRPedir:
    def __init__(self, usuario, senha, log_callback=None, screenshot_callback=None, headless=False):
        if not usuario or not senha:
            raise ValueError("Usuário e senha não podem ser vazios!")
        self.usuario = usuario
        self.senha = senha
        self.headless = headless
        self.screenshot_callback = screenshot_callback
        self.rodando = True
        self.driver = None
        self.log = log_callback if log_callback else print

    def _verificar_conexao(self):
        try:
            requests.get("http://www.google.com", timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    def iniciar(self):
        self.log("🔹 Abrindo navegador para QRPedir...")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument("--disable-blink-features=AutomationControlled")

        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
            options.add_argument("--password-store=basic")
            options.add_argument("--incognito")
            options.add_argument("--ignore-certificate-errors")
            options.add_argument("--no-first-run")
            options.add_argument("--no-service-autorun")
        
        try:
            # Abordagem 1: Tenta o Selenium 4 Nativo
            self.driver = webdriver.Chrome(options=options)
        except Exception as e_native:
            self.log("⚠️ Inicializador nativo falhou, tentando WebDriverManager...")
            try:
                # Abordagem 2: Fallback para o webdriver-manager clássico
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            except Exception as e_fallback:
                 raise Exception(f"Erro ao iniciar o bot QRPedir (Chrome/Driver): {e_fallback}")

        self.driver.get("https://station.qrpedir.com/login")
        
        wait_login = WebDriverWait(self.driver, 10)
        try:
            # Verifica se já está logado (cookies salvos ou redirecionamento automático)
            if "login" not in self.driver.current_url:
                self.log("... Já detectado como logado (sessão ativa).")
            else:
                campo_usuario = wait_login.until(EC.element_to_be_clickable((By.NAME, "username"))) 
                campo_senha = self.driver.find_element(By.NAME, "password")
                
                self.log("... Preenchendo credenciais QRPedir")
                campo_usuario.send_keys(self.usuario)
                campo_senha.send_keys(self.senha)
                
                botao_login = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
                botao_login.click()
                
                # Aguarda o redirecionamento (URL deixar de conter /login)
                self.log("... Aguardando autenticação...")
                WebDriverWait(self.driver, 25).until(lambda d: "login" not in d.current_url)
                self.log("✅ Login no QRPedir realizado com sucesso!")
                
                self.log("✅ Página do Cardápio carregada!")

        except Exception as e:
            # Se já estivermos fora da tela de login, podemos considerar como "meio-sucesso" para liberar o botão
            if "login" not in self.driver.current_url:
                self.log(f"⚠️ Aviso ignorável durante navegação: {e}")
                self.log("✅ Continuando pois o login parece ter sido bem sucedido.")
            else:
                self.log(f"❌ Erro fatal ao iniciar QRPedir: {e}")
                raise
        finally:
            self._iniciar_thread_screenshot()

    def _iniciar_thread_screenshot(self):
        """Inicia uma thread que tira screenshots a cada 2 segundos"""
        if not self.screenshot_callback: return
        import threading
        
        def run():
            while self.rodando and self.driver:
                try:
                    b64 = self.driver.get_screenshot_as_base64()
                    self.screenshot_callback(b64)
                except:
                    pass
                time.sleep(2.0)
                
        threading.Thread(target=run, daemon=True).start()

    def _limpar_e_digitar(self, elemento, valor):
        """Clica, Seleciona Tudo, Apaga e Digita o valor."""
        try:
            valor_str = str(valor)
            # Remove .0 se for número inteiro vindo do Excel (ex: '1.0' vira '1')
            if valor_str.endswith(".0"):
                valor_str = valor_str[:-2]
            
            elemento.click()
            time.sleep(0.1)
            elemento.send_keys(Keys.CONTROL, "a")
            time.sleep(0.1)
            elemento.send_keys(valor_str)
            time.sleep(0.2)
        except Exception as e:
            self.log(f"⚠️ Erro ao digitar '{valor}': {e}")

    def encontrar_grupo(self, nome_do_grupo):
        """Verifica se um grupo existe e retorna o BOTAO DE EXPANDIR."""
        nome_grupo_upper = nome_do_grupo.strip().upper() 
        self.log(f"... Verificando se o grupo '{nome_grupo_upper}' existe...")
        time.sleep(0.2)
        
        try:
            xpath_h6 = f"//h6[text()='{nome_grupo_upper}']"
            lista_h6 = self.driver.find_elements(By.XPATH, xpath_h6)
            
            if len(lista_h6) > 0:
                self.log("✅ Grupo encontrado! Retornando o botão de expandir.")
                h6_element = lista_h6[0]
                summary_button = h6_element.find_element(By.XPATH, "./ancestor::button[contains(@class, 'MuiAccordionSummary-root')]")
                return summary_button
            else:
                self.log("❌ Grupo não encontrado.")
                return None
        except Exception as e:
            self.log(f"Erro ao encontrar grupo: {e}")
            return None

    def _fechar_modal_produto(self):
        """Fecha o pop-up com ActionChains (confiável)."""
        self.log("... Fechando pop-up do produto com a tecla ESC (via ActionChains)...")
        try:
            wait = WebDriverWait(self.driver, 10)
            action = ActionChains(self.driver)
            action.send_keys(Keys.ESCAPE).perform()
            
            wait.until(EC.invisibility_of_element_located((By.NAME, "nome")))
            self.log("... Pop-up fechado.")
            time.sleep(0.2)
        except Exception as e:
            self.log(f"❌ Erro ao tentar fechar o pop-up com ESC: {e}")

    def _cadastrar_grupo_complemento(self, grupo_data):
        """Cadastra um grupo de complemento (com Min/Max/Ordem) e seus itens."""
        
        # Formata valores para garantir que sejam inteiros se possível
        min_val = grupo_data.get('min')
        max_val = grupo_data.get('max')
        ordem_val = grupo_data.get('ordem') # NOVO CAMPO
        
        try:
            if min_val: min_val = int(float(min_val))
            if max_val: max_val = int(float(max_val))
            if ordem_val: ordem_val = int(float(ordem_val))
        except ValueError:
            pass

        self.log(f"... Cadastrando Grupo: {grupo_data['descricao_complemento']} (Min: {min_val}, Max: {max_val}, Ordem: {ordem_val})")
        try:
            wait = WebDriverWait(self.driver, 10)
            
            # 1. Clica em "Adicionar Complemento"
            add_comp_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Adicionar Complemento')]"))
            )
            add_comp_button.click()
            time.sleep(0.5)

            # 2. Preenche a Descrição do Grupo
            self.log("... Preenchendo dados do Grupo.")
            campo_desc_grupo = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Sabores tradicionais']"))
            )
            self._limpar_e_digitar(campo_desc_grupo, grupo_data['descricao_complemento'])
            
            # 3. Preenche MIN e MAX
            if min_val is not None:
                campo_min = self.driver.find_element(By.NAME, "min")
                self._limpar_e_digitar(campo_min, min_val)
            
            if max_val is not None:
                campo_max = self.driver.find_element(By.NAME, "max")
                self._limpar_e_digitar(campo_max, max_val)

            # --- NOVO: Preenche ORDEM ---
            if ordem_val is not None:
                try:
                    campo_ordem = self.driver.find_element(By.NAME, "ordem")
                    self._limpar_e_digitar(campo_ordem, ordem_val)
                except Exception as e:
                    self.log(f"⚠️ Campo 'ordem' não encontrado ou erro ao preencher: {e}")                        
            # 4. Loop para cadastrar os ITENS
            for i, item in enumerate(grupo_data['itens']):
                self.log(f"... Adicionando item: {item['item_descricao']}")
                
                xpath_anchor = "//input[@placeholder='Ex: MARGHERITA']"
                campos_atuais = self.driver.find_elements(By.XPATH, xpath_anchor)
                count_antes = len(campos_atuais)

                if i > 0:
                    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Adicionar item')]"))).click()
                    
                    # CORREÇÃO DA DUPLICAÇÃO
                    wait.until(
                        lambda driver: len(driver.find_elements(By.XPATH, xpath_anchor)) > count_antes
                    )
                    self.log(f"... Novos campos de item (total: {count_antes + 1}) apareceram.")

                campos_item_desc = wait.until(EC.presence_of_all_elements_located((By.XPATH, xpath_anchor)))
                campos_item_desc[-1].send_keys(item['item_descricao'])
                
                if item.get('item_desc_comp'):
                    campos_desc_comp = self.driver.find_elements(By.NAME, "descricaoComplementar")
                    campos_desc_comp[-1].send_keys(item['item_desc_comp'])
                
                if item.get('item_codigo'):
                    campos_codigo = self.driver.find_elements(By.NAME, "codigoExterno")
                    campos_codigo[-1].send_keys(item['item_codigo'])
                
                if item.get('item_valor'):
                    campos_valor = self.driver.find_elements(By.NAME, "valor")
                    campo_alvo_valor = campos_valor[-1]
                    valor_do_csv = str(item['item_valor'])
                    
                    campo_alvo_valor.click(); time.sleep(0.1)
                    campo_alvo_valor.send_keys(Keys.CONTROL, "a"); time.sleep(0.1)
                    campo_alvo_valor.send_keys(Keys.BACK_SPACE); time.sleep(0.1)
                    campo_alvo_valor.send_keys(valor_do_csv)
                
                time.sleep(0.5)
            
            self.log("... Itens preenchidos. Salvando Grupo de Complemento.")
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[text()='SALVAR COMPLEMENTO']")
            )).click()
            
            wait.until(EC.invisibility_of_element_located(
                (By.XPATH, "//button[text()='SALVAR COMPLEMENTO']")
            ))
            self.log(f"✅ Grupo de Complemento '{grupo_data['descricao_complemento']}' salvo.")
            time.sleep(0.5)
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao cadastrar Grupo de Complemento: {e}")
            return False

    def _acessar_complementos(self, item_data):
        """Espera a aba carregar, cadastra grupos, clica em SALVAR e fecha com ESC."""
        self.log("-> Acessando aba 'Complementos'...")
        try:
            wait = WebDriverWait(self.driver, 10)
            
            aba_complementos = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Complementos']"))
            )
            aba_complementos.click()
            
            self.log("... Esperando conteúdo da aba 'Complementos' carregar...")
            wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Adicionar Complemento')]"))
            )
            
            grupos_complemento_data = item_data.get("grupos_complemento", [])
            self.log(f"✅ Aba 'Complementos' aberta. {len(grupos_complemento_data)} grupos para cadastrar.")
            
            for grupo_data in grupos_complemento_data:
                if not self._verificar_conexao():
                    self.log("🚨 CONEXÃO PERDIDA durante cadastro de complementos. Abortando item.")
                    raise Exception("Conexão perdida") 
                    
                self._cadastrar_grupo_complemento(grupo_data)

            self.log("... Todos os grupos de complementos foram processados.")
            self.log("... Clicando em 'SALVAR' (principal) para salvar as associações.")
            
            botao_salvar_principal = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='SALVAR']"))
            )
            botao_salvar_principal.click()
            
            time.sleep(0.8) # Pausa para salvar
            
            self.log("... Salvamento finalizado. Fechando modal.")
            self._fechar_modal_produto()

        except Exception as e:
            self.log(f"❌ Erro ao acessar ou finalizar complementos: {e}")
            self._fechar_modal_produto()

    def _preencher_modal_produto(self, item_data):
        """Preenche o formulário, salva, e decide se acessa complementos ou fecha."""
        self.log("... Preenchendo dados do produto no pop-up...")
        try:
            wait = WebDriverWait(self.driver, 10)
            campo_nome = wait.until(EC.presence_of_element_located((By.NAME, "nome")))
            time.sleep(0.5)

            self.log(f"    -> Nome: {item_data['Nome']}")
            campo_nome.send_keys(item_data["Nome"])
            
            if item_data.get("CodigoExterno"):
                self.driver.find_element(By.NAME, "codigoExterno").send_keys(item_data["CodigoExterno"])
            
            if item_data.get("Preco"):
                campo_preco = self.driver.find_element(By.NAME, "preco")
                valor_do_csv = str(item_data['Preco'])
                campo_preco.click(); time.sleep(0.1)
                campo_preco.send_keys(Keys.CONTROL, "a"); time.sleep(0.1)
                campo_preco.send_keys(Keys.BACK_SPACE); time.sleep(0.1)
                campo_preco.send_keys(valor_do_csv)
                
            if item_data.get("Descricao"):
                self.driver.find_element(By.NAME, "descricao").send_keys(item_data["Descricao"])
            time.sleep(0.5)

            self.log("... Clicando em 'SALVAR' o produto.")
            botao_salvar_produto = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='SALVAR']"))
            )
            botao_salvar_produto.click()

            self.log("... Aguardando aba 'Complementos' ficar disponível...")
            wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Complementos']"))
            )
            self.log(f"✅ Produto '{item_data['Nome']}' salvo (fase 1).")
            
            # Verifica S ou N
            possui = str(item_data.get("PossuiComplemento", "N")).strip().upper()
            
            if possui == 'S':
                self.log("... (S) Encontrado. Acessando complementos.")
                self._acessar_complementos(item_data)
            else:
                self.log("... Produto não possui complementos. Fechando modal.")
                self._fechar_modal_produto()
                
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao preencher ou salvar o produto: {e}")
            raise e 

    def criar_novo_grupo(self, nome_do_grupo):
        """Clica em 'Novo Grupo', preenche o nome e salva."""
        self.log("-> Procurando botão 'Novo Grupo'...")
        try:
            xpath_novo_grupo = "//button[contains(text(), 'Novo Grupo')]"
            wait = WebDriverWait(self.driver, 10)

            # --- CORREÇÃO: Scroll e Clique JS ---
            botao_novo_grupo = wait.until(
                EC.presence_of_element_located((By.XPATH, xpath_novo_grupo))
            )
            
            self.log("... Rolando o botão 'Novo Grupo' para a vista.")
            self.driver.execute_script("arguments[0].scrollIntoView(true);", botao_novo_grupo)
            time.sleep(1.0) 
            
            self.log("... Clicando em 'Novo Grupo' via JavaScript.")
            self.driver.execute_script("arguments[0].click();", botao_novo_grupo)
            # --- FIM DA CORREÇÃO ---
            
            time.sleep(1.5) 

            self.log(f"... Preenchendo nome: {nome_do_grupo}")
            campo_descricao_grupo = wait.until(
                EC.presence_of_element_located((By.NAME, "descricao")) 
            )
            campo_descricao_grupo.send_keys(nome_do_grupo.strip().upper())
            time.sleep(0.5)

            self.log("... Clicando em 'SALVAR'.")
            botao_salvar_grupo = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='SALVAR']"))
            )
            botao_salvar_grupo.click()
            
            self.log("... Aguardando criação do grupo...")
            xpath_h6_novo = f"//h6[text()='{nome_do_grupo.strip().upper()}']"
            wait.until(EC.presence_of_element_located((By.XPATH, xpath_h6_novo)))
            
            self.log(f"✅ Grupo '{nome_do_grupo}' criado com sucesso.")
            return True 
            
        except Exception as e:
            self.log(f"❌ Erro ao tentar criar 'Novo Grupo': {e}")
            return False 

    def processar_item_cardapio(self, item_data):
        """Método principal: Encontra/Cria Grupo, Expande, Clica 'Novo Produto'."""
        
        if not self._verificar_conexao():
            self.log("🚨 CONEXÃO PERDIDA. Abortando este item.")
            raise Exception("Conexão perdida antes de processar o item.")

        nome_do_grupo = item_data["Grupo"]
        self.log(f"--- Processando Produto: {item_data['Nome']} (Grupo: {nome_do_grupo}) ---")
        
        grupo_button = self.encontrar_grupo(nome_do_grupo)
        
        if not grupo_button:
            self.log(f"❌ Grupo '{nome_do_grupo}' não encontrado.")
            sucesso_criacao = self.criar_novo_grupo(nome_do_grupo)
            if not sucesso_criacao:
                 self.log("❌ Falha ao criar o grupo. Abortando este item.")
                 raise Exception(f"Falha ao criar grupo '{nome_do_grupo}'")
            time.sleep(1) 
            grupo_button = self.encontrar_grupo(nome_do_grupo)
            if not grupo_button:
                self.log("❌ Erro: Não foi possível encontrar o grupo após criá-lo.")
                return 

        try:
            self.log(f"-> Expandindo grupo '{nome_do_grupo}'...")
            if grupo_button.get_attribute("aria-expanded") == "false":
                grupo_button.click()
                time.sleep(1.5)
            else:
                self.log("... Grupo já estava expandido.")

            accordion_root = grupo_button.find_element(By.XPATH, "./ancestor::div[contains(@class, 'MuiAccordion-root')]")
            xpath_novo_produto = ".//button[text()='Novo Produto']"
            wait = WebDriverWait(accordion_root, 10)
            botao_novo_prod = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_novo_produto)))
            
            self.log("-> Clicando em 'Novo Produto'...")
            time.sleep(0.5)
            botao_novo_prod.click()
            time.sleep(1)
            
            self._preencher_modal_produto(item_data)
            
        except Exception as e:
            self.log(f"❌ Erro ao expandir ou clicar em 'Novo Produto': {e}")
            self._fechar_modal_produto()
            raise e

    def fechar(self):
        """Fecha o navegador QRPedir."""
        self.rodando = False
        if self.driver:
            try:
                self.driver.quit()
                self.log("✅ Navegador QRPedir fechado.")
            except Exception as e:
                self.log(f"❌ Erro ao fechar QRPedir: {e}")
            finally:
                self.driver = None