import time
import pandas as pd
import requests 
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

class BotQRPedir:
    def __init__(self, usuario, senha, log_callback=None):
        if not usuario or not senha:
            raise ValueError("Usuário e senha não podem ser vazios!")
        self.usuario = usuario
        self.senha = senha
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
        self.driver = webdriver.Chrome(options=options) 
        self.driver.get("https://station.qrpedir.com/login")
        
        wait = WebDriverWait(self.driver, 10)
        
        try:
            campo_usuario = wait.until(EC.presence_of_element_located((By.NAME, "username"))) 
            campo_senha = self.driver.find_element(By.NAME, "password")
            
            self.log("... Preenchendo credenciais QRPedir")
            campo_usuario.send_keys(self.usuario)
            campo_senha.send_keys(self.senha)
            
            botao_login = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            # Clique via JavaScript
            self.driver.execute_script("arguments[0].click();", botao_login)

            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Pedidos')]")))
            self.log("✅ Login no QRPedir realizado com sucesso!")

            self.log("... Acessando o Cardápio")
            cardapio_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//p[text()='Cardápio']")))
            # Clique via JavaScript
            self.driver.execute_script("arguments[0].click();", cardapio_link)

            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Categorias')]")))
            self.log("✅ Página do Cardápio carregada!")

        except Exception as e:
            self.log(f"❌ Erro ao fazer login ou acessar cardápio no QRPedir: {e}")
            raise

    # --- FUNÇÃO AUXILIAR: LIMPAR E DIGITAR ---
    def _limpar_e_digitar(self, elemento, valor):
        """Clica, Seleciona Tudo, Apaga e Digita o valor."""
        try:
            valor_str = str(valor)
            if valor_str.endswith(".0"):
                valor_str = valor_str[:-2]
            
            # Força o elemento a aparecer no centro da tela antes de digitar
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", elemento)
            time.sleep(0.2)
            
            elemento.click()
            time.sleep(0.1)
            elemento.send_keys(Keys.CONTROL, "a")
            time.sleep(0.1)
            elemento.send_keys(Keys.BACK_SPACE)
            time.sleep(0.1)
            elemento.send_keys(valor_str)
            time.sleep(0.2)
        except Exception as e:
            self.log(f"⚠️ Erro ao digitar '{valor}': {e}")

    def encontrar_grupo(self, nome_do_grupo):
        nome_grupo_upper = nome_do_grupo.strip().upper() 
        self.log(f"... Verificando se o grupo '{nome_grupo_upper}' existe...")
        time.sleep(0.5)
        
        try:
            xpath_h6 = f"//h6[text()='{nome_grupo_upper}']"
            lista_h6 = self.driver.find_elements(By.XPATH, xpath_h6)
            
            if len(lista_h6) > 0:
                self.log("✅ Grupo encontrado! Retornando o botão de expandir.")
                h6_element = lista_h6[0]
                summary_button = h6_element.find_element(By.XPATH, "./ancestor::button[contains(@class, 'MuiAccordionSummary-root')]")
                
                # Rola a tela até o grupo encontrado para garantir que ele está visível
                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", summary_button)
                time.sleep(0.3)
                return summary_button
            else:
                self.log("❌ Grupo não encontrado.")
                return None
        except Exception as e:
            self.log(f"Erro ao encontrar grupo: {e}")
            return None

    def _fechar_modal_produto(self):
        self.log("... Fechando pop-up do produto com a tecla ESC (via ActionChains)...")
        try:
            wait = WebDriverWait(self.driver, 10)
            action = ActionChains(self.driver)
            action.send_keys(Keys.ESCAPE).perform()
            
            wait.until(EC.invisibility_of_element_located((By.NAME, "nome")))
            self.log("... Pop-up fechado.")
            time.sleep(1)
        except Exception as e:
            self.log(f"❌ Erro ao tentar fechar o pop-up com ESC: {e}")

    def _cadastrar_grupo_complemento(self, grupo_data):
        min_val = grupo_data.get('min')
        max_val = grupo_data.get('max')
        ordem_val = grupo_data.get('ordem')
        
        self.log(f"... Cadastrando Grupo: {grupo_data['descricao_complemento']} (Ordem: {ordem_val})")
        try:
            wait = WebDriverWait(self.driver, 10)
            
            add_comp_button = wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Adicionar Complemento')]"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", add_comp_button)
            time.sleep(0.2)
            self.driver.execute_script("arguments[0].click();", add_comp_button)
            time.sleep(1)

            self.log("... Preenchendo dados do Grupo.")
            campo_desc_grupo = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Sabores tradicionais']"))
            )
            self._limpar_e_digitar(campo_desc_grupo, grupo_data['descricao_complemento'])
            
            if min_val and str(min_val).strip():
                campo_min = self.driver.find_element(By.NAME, "min")
                self._limpar_e_digitar(campo_min, min_val)
            
            if max_val and str(max_val).strip():
                campo_max = self.driver.find_element(By.NAME, "max")
                self._limpar_e_digitar(campo_max, max_val)

            if ordem_val and str(ordem_val).strip():
                try:
                    campo_ordem = self.driver.find_element(By.NAME, "ordem")
                    self._limpar_e_digitar(campo_ordem, ordem_val)
                except Exception as e_ordem:
                    self.log(f"⚠️ Não foi possível preencher a Ordem: {e_ordem}")

            for i, item in enumerate(grupo_data['itens']):
                self.log(f"... Adicionando item: {item['item_descricao']}")
                
                xpath_anchor = "//input[@placeholder='Ex: MARGHERITA']"
                campos_atuais = self.driver.find_elements(By.XPATH, xpath_anchor)
                count_antes = len(campos_atuais)

                if i > 0:
                    btn_add_item = wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Adicionar item')]")))
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", btn_add_item)
                    time.sleep(0.2)
                    self.driver.execute_script("arguments[0].click();", btn_add_item)
                    
                    wait.until(
                        lambda driver: len(driver.find_elements(By.XPATH, xpath_anchor)) > count_antes
                    )

                campos_item_desc = wait.until(EC.presence_of_all_elements_located((By.XPATH, xpath_anchor)))
                self._limpar_e_digitar(campos_item_desc[-1], item['item_descricao'])
                
                if item.get('item_desc_comp'):
                    campos_desc_comp = self.driver.find_elements(By.NAME, "descricaoComplementar")
                    self._limpar_e_digitar(campos_desc_comp[-1], item['item_desc_comp'])
                
                if item.get('item_codigo'):
                    campos_codigo = self.driver.find_elements(By.NAME, "codigoExterno")
                    self._limpar_e_digitar(campos_codigo[-1], item['item_codigo'])
                
                if item.get('item_valor'):
                    campos_valor = self.driver.find_elements(By.NAME, "valor")
                    self._limpar_e_digitar(campos_valor[-1], item['item_valor'])
                
                time.sleep(0.3)
            
            self.log("... Itens preenchidos. Salvando Grupo de Complemento.")
            botao_salvar_comp = wait.until(EC.presence_of_element_located((By.XPATH, "//button[text()='SALVAR COMPLEMENTO']")))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_salvar_comp)
            time.sleep(0.2)
            self.driver.execute_script("arguments[0].click();", botao_salvar_comp)
            
            wait.until(EC.invisibility_of_element_located(
                (By.XPATH, "//button[text()='SALVAR COMPLEMENTO']")
            ))
            self.log(f"✅ Grupo '{grupo_data['descricao_complemento']}' salvo.")
            time.sleep(1)
            return True
            
        except Exception as e:
            self.log(f"❌ Erro ao cadastrar Grupo de Complemento: {e}")
            return False

    def _acessar_complementos(self, item_data):
        self.log("-> Acessando aba 'Complementos'...")
        try:
            wait = WebDriverWait(self.driver, 10)
            
            aba_complementos = wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[text()='Complementos']"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", aba_complementos)
            time.sleep(0.2)
            self.driver.execute_script("arguments[0].click();", aba_complementos)
            
            self.log("... Esperando conteúdo da aba 'Complementos' carregar...")
            wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Adicionar Complemento')]"))
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
                EC.presence_of_element_located((By.XPATH, "//button[text()='SALVAR']"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_salvar_principal)
            time.sleep(0.2)
            self.driver.execute_script("arguments[0].click();", botao_salvar_principal)
            
            time.sleep(1.5) 
            
            self.log("... Salvamento finalizado. Fechando modal.")
            self._fechar_modal_produto()

        except Exception as e:
            self.log(f"❌ Erro ao acessar ou finalizar complementos: {e}")
            self._fechar_modal_produto()

    def _preencher_modal_produto(self, item_data):
        self.log("... Preenchendo dados do produto no pop-up...")
        try:
            wait = WebDriverWait(self.driver, 10)
            campo_nome = wait.until(EC.presence_of_element_located((By.NAME, "nome")))
            time.sleep(0.5)

            self.log(f"    -> Nome: {item_data['Nome']}")
            self._limpar_e_digitar(campo_nome, item_data["Nome"])
            
            if item_data.get("CodigoExterno"):
                campo_codigo = self.driver.find_element(By.NAME, "codigoExterno")
                self._limpar_e_digitar(campo_codigo, item_data["CodigoExterno"])
            
            if item_data.get("Preco"):
                campo_preco = self.driver.find_element(By.NAME, "preco")
                self._limpar_e_digitar(campo_preco, item_data["Preco"])
                
            if item_data.get("Descricao"):
                campo_desc = self.driver.find_element(By.NAME, "descricao")
                self._limpar_e_digitar(campo_desc, item_data["Descricao"])
            
            time.sleep(0.5)

            self.log("... Clicando em 'SALVAR' o produto.")
            botao_salvar_produto = wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[text()='SALVAR']"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_salvar_produto)
            time.sleep(0.2)
            self.driver.execute_script("arguments[0].click();", botao_salvar_produto)

            self.log("... Aguardando aba 'Complementos' ficar disponível...")
            wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[text()='Complementos']"))
            )
            self.log(f"✅ Produto '{item_data['Nome']}' salvo (fase 1).")
            
            if str(item_data.get("PossuiComplemento")).strip().upper() == 'S':
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
        self.log("-> Procurando botão 'Novo Grupo'...")
        try:
            xpath_novo_grupo = "//button[contains(text(), 'Novo Grupo')]"
            wait = WebDriverWait(self.driver, 10)

            botao_novo_grupo = wait.until(
                EC.presence_of_element_located((By.XPATH, xpath_novo_grupo))
            )
            
            self.log("... Rolando o botão 'Novo Grupo' para a vista.")
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_novo_grupo)
            time.sleep(1.0) 
            
            self.log("... Clicando em 'Novo Grupo' via JavaScript.")
            self.driver.execute_script("arguments[0].click();", botao_novo_grupo)
            
            time.sleep(1.5) 

            self.log(f"... Preenchendo nome: {nome_do_grupo}")
            campo_descricao_grupo = wait.until(
                EC.presence_of_element_located((By.NAME, "descricao")) 
            )
            self._limpar_e_digitar(campo_descricao_grupo, nome_do_grupo.strip().upper())
            time.sleep(0.5)

            self.log("... Clicando em 'SALVAR'.")
            botao_salvar_grupo = wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[text()='SALVAR']"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_salvar_grupo)
            time.sleep(0.2)
            self.driver.execute_script("arguments[0].click();", botao_salvar_grupo)
            
            self.log("... Aguardando criação do grupo...")
            xpath_h6_novo = f"//h6[text()='{nome_do_grupo.strip().upper()}']"
            
            # Procura pelo título do novo grupo e garante que a tela role até ele
            novo_grupo_criado = wait.until(EC.presence_of_element_located((By.XPATH, xpath_h6_novo)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", novo_grupo_criado)
            
            self.log(f"✅ Grupo '{nome_do_grupo}' criado com sucesso.")
            return True 
            
        except Exception as e:
            self.log(f"❌ Erro ao tentar criar 'Novo Grupo': {e}")
            return False 

    def processar_item_cardapio(self, item_data):
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
            
            # Garante que o grupo está no centro da tela antes de qualquer coisa
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", grupo_button)
            time.sleep(0.5)

            if grupo_button.get_attribute("aria-expanded") == "false":
                # Clique JS super seguro
                self.driver.execute_script("arguments[0].click();", grupo_button)
                time.sleep(1.5)
            else:
                self.log("... Grupo já estava expandido.")

            accordion_root = grupo_button.find_element(By.XPATH, "./ancestor::div[contains(@class, 'MuiAccordion-root')]")
            xpath_novo_produto = ".//button[text()='Novo Produto']"
            wait = WebDriverWait(accordion_root, 10)
            botao_novo_prod = wait.until(EC.presence_of_element_located((By.XPATH, xpath_novo_produto)))
            
            self.log("-> Clicando em 'Novo Produto'...")
            # Rola a tela até o botão 'Novo Produto' específico deste grupo
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", botao_novo_prod)
            time.sleep(0.5)
            
            # Clique JS para não ser interceptado por outros elementos flutuantes
            self.driver.execute_script("arguments[0].click();", botao_novo_prod)
            time.sleep(1)
            
            self._preencher_modal_produto(item_data)
            
        except Exception as e:
            self.log(f"❌ Erro ao expandir ou clicar em 'Novo Produto': {e}")
            self._fechar_modal_produto()
            raise e

    def fechar(self):
        if self.driver:
            try:
                self.driver.quit()
                self.log("✅ Navegador QRPedir fechado.")
            except Exception as e:
                self.log(f"❌ Erro ao fechar QRPedir: {e}")
            finally:
                self.driver = None