import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

class BotSischef:
    def __init__(self, usuario, senha, arquivo_csv=None):
        if not usuario or not senha:
            raise ValueError("Usuário e senha não podem ser vazios!")
        self.usuario = usuario
        self.senha = senha
        self.arquivo_csv = arquivo_csv
        self.driver = None
        self.rodando = True # Flag para parada do Sischef

    def iniciar(self):
        print("🔹 Abrindo navegador Sischef...")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)

        # Login
        self.driver.get("https://sistema.sischef.com")
        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "j_username")))
        time.sleep(1)

        self.driver.find_element(By.ID, "j_username").send_keys(self.usuario)
        self.driver.find_element(By.ID, "j_password").send_keys(self.senha)
        time.sleep(0.5)
        self.driver.find_element(By.ID, "login").click()

        WebDriverWait(self.driver, 15).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        print("✅ Login Sischef realizado!")

        url_cadastro = "https://sistema.sischef.com/admin/produtos/produto.jsf"
        time.sleep(1)
        self.driver.execute_script("window.location.href = arguments[0];", url_cadastro)

        WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
        print("✅ Tela de cadastro Sischef aberta!")

    def cadastrar_produtos(self, callback_progresso=None):
        if not self.arquivo_csv:
            print("❌ Nenhum arquivo CSV selecionado.")
            return

        dados = pd.read_csv(self.arquivo_csv)

        # Mapeamento CSV → campos do sistema
        mapeamento_campos = {
            "Descricao": "tabSessoesProduto:descricao",
            "Grupo": "tabSessoesProduto:grupoProduto_input",
            "CodigoBarras": "tabSessoesProduto:codigoBarras",
            "NCM": "tabSessoesProduto:ncm",
            "PrecoCompra": "tabSessoesProduto:valorUnitarioCompra",
            "PrecoVenda": "tabSessoesProduto:valorUnitarioVenda"
        }

        for col in mapeamento_campos.keys():
            if col not in dados.columns:
                raise ValueError(f"❌ Coluna '{col}' não encontrada no CSV!")

        total = len(dados)
        print(f"📦 Total de produtos a cadastrar: {total}")

        for i, row in dados.iterrows():
            print(f"🔹 Cadastrando produto {i+1}/{total}: {row['Descricao']}")
            try:
                # Preenche os campos
                for col_csv, campo_id in mapeamento_campos.items():
                    valor = str(row[col_csv]).strip()

                    # 🔹 Garantir duas casas decimais para preços
                    if campo_id in ["tabSessoesProduto:valorUnitarioCompra", "tabSessoesProduto:valorUnitarioVenda"]:
                        try:
                            valor_numerico = float(valor.replace(",", "."))
                            valor = f"{valor_numerico:.2f}".replace(".", ",")  # usa vírgula como separador
                        except ValueError:
                            print(f"⚠️ Valor inválido no campo {col_csv}: '{valor}'. Usando '0,00'.")
                            valor = "0,00"

                    input_elem = self.driver.find_element(By.ID, campo_id)
                    input_elem.clear()
                    time.sleep(0.5)
                    input_elem.send_keys(valor)
                    time.sleep(0.5)

                    # Se for o campo do grupo, esperar e apertar Enter
                    if campo_id == "tabSessoesProduto:grupoProduto_input":
                        time.sleep(1)
                        input_elem.send_keys(u'\ue007')  # Enter

                # Salvar via Alt + S
                self.driver.find_element(By.ID, "tabSessoesProduto:descricao").click()
                time.sleep(0.5)
                self.driver.find_element(By.ID, "tabSessoesProduto:descricao").send_keys(Keys.ALT, "s")
                print("💾 Produto salvo.")
                time.sleep(2)

                # Clicar em Novo
                botao_novo = WebDriverWait(self.driver, 5).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, "a.mui-btn.mui-btn-text"))
                )
                botao_novo.click()
                time.sleep(2)

                # 🔄 Atualiza a interface
                if callback_progresso:
                    callback_progresso(i + 1, total)

            except Exception as e:
                print(f"❌ Erro ao cadastrar produto {i+1}: {e}")

        print("✅ Cadastro de todos os produtos concluído!")

    def fechar(self):
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Navegador fechado com sucesso!")
            except Exception as e:
                print(f"❌ Erro ao fechar navegador: {e}")
            finally:
                self.driver = None

        self.rodando = False # Sinaliza para o loop parar
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Navegador Sischef fechado.")
            except Exception as e:
                print(f"❌ Erro ao fechar Sischef: {e}")
            finally:
                self.driver = None

# ==========================================================
# CLASSE QRPEDIR (LIMPA E CORRIGIDA)
# ==========================================================
class BotQRPedir:
    def __init__(self, usuario, senha):
        if not usuario or not senha:
            raise ValueError("Usuário e senha não podem ser vazios!")
        self.usuario = usuario
        self.senha = senha
        self.driver = None

    def iniciar(self):
        print("🔹 Abrindo navegador para QRPedir...")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        self.driver = webdriver.Chrome(options=options)
        self.driver.get("https://station.qrpedir.com/login")
        
        wait = WebDriverWait(self.driver, 10)
        
        try:
            # --- Login ---
            campo_usuario = wait.until(EC.presence_of_element_located((By.NAME, "username"))) 
            campo_senha = self.driver.find_element(By.NAME, "password")
            
            print("... Preenchendo credenciais QRPedir")
            campo_usuario.send_keys(self.usuario)
            campo_senha.send_keys(self.senha)
            
            botao_login = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
            botao_login.click()

            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Pedidos')]")))
            print("✅ Login no QRPedir realizado com sucesso!")

            # --- Acessa o Cardápio ---
            print("... Acessando o Cardápio")
            cardapio_link = wait.until(EC.element_to_be_clickable((By.XPATH, "//p[text()='Cardápio']")))
            cardapio_link.click()

            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Categorias')]")))
            print("✅ Página do Cardápio carregada!")

        except Exception as e:
            print(f"❌ Erro ao fazer login ou acessar cardápio no QRPedir: {e}")
            raise

    def encontrar_grupo(self, nome_do_grupo):
        """Verifica se um grupo existe e retorna o BOTAO DE EXPANDIR."""
        nome_grupo_upper = nome_do_grupo.strip().upper() 
        print(f"... Verificando se o grupo '{nome_grupo_upper}' existe...")
        time.sleep(0.5)
        
        try:
            xpath_h6 = f"//h6[text()='{nome_grupo_upper}']"
            lista_h6 = self.driver.find_elements(By.XPATH, xpath_h6)
            
            if len(lista_h6) > 0:
                print("✅ Grupo encontrado! Retornando o botão de expandir.")
                h6_element = lista_h6[0]
                summary_button = h6_element.find_element(By.XPATH, "./ancestor::button[contains(@class, 'MuiAccordionSummary-root')]")
                return summary_button
            else:
                print("❌ Grupo não encontrado.")
                return None
        except Exception as e:
            print(f"Erro ao encontrar grupo: {e}")
            return None

    def _fechar_modal_produto(self):
        """Fecha o pop-up com ActionChains (confiável)."""
        print("... Fechando pop-up do produto com a tecla ESC (via ActionChains)...")
        try:
            wait = WebDriverWait(self.driver, 10)
            
            # 1. Cria uma "Ação"
            action = ActionChains(self.driver)
            
            # 2. Envia a tecla ESCAPE
            action.send_keys(Keys.ESCAPE).perform()
            
            # 3. Espera o modal fechar
            wait.until(EC.invisibility_of_element_located((By.NAME, "nome")))
            print("... Pop-up fechado.")
            time.sleep(1) # Pausa antes do próximo item
            
        except Exception as e:
            print(f"❌ Erro ao tentar fechar o pop-up com ESC: {e}")

    def _cadastrar_grupo_complemento(self, grupo_data):
        """Cadastra um grupo de complemento (SABORES) e seus itens (MARGHERITA...)."""
        print(f"... Cadastrando Grupo de Complemento: {grupo_data['descricao_complemento']}")
        try:
            wait = WebDriverWait(self.driver, 10)
            
            # 1. Clicar em "Adicionar Complemento"
            add_comp_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Adicionar Complemento')]"))
            )
            add_comp_button.click()
            time.sleep(1)

            # 2. Preencher os dados do GRUPO (SABORES)
            print("... Preenchendo dados do Grupo de Complemento")
            campo_desc_grupo = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Sabores tradicionais']"))
            )
            campo_desc_grupo.send_keys(grupo_data['descricao_complemento'])
            time.sleep(0.3)
            
            # (Lógica de Min/Max/Tipo foi removida)
            
            # 3. Loop para cadastrar os ITENS (COM CORREÇÃO DE DUPLICAÇÃO)
            for i, item in enumerate(grupo_data['itens']):
                print(f"... Adicionando item: {item['item_descricao']}")
                
                xpath_anchor = "//input[@placeholder='Ex: MARGHERITA']"
                campos_atuais = self.driver.find_elements(By.XPATH, xpath_anchor)
                count_antes = len(campos_atuais)

                if i > 0:
                    wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Adicionar item')]"))).click()
                    
                    # [CORREÇÃO DA DUPLICAÇÃO] Espera o novo campo aparecer
                    wait.until(
                        lambda driver: len(driver.find_elements(By.XPATH, xpath_anchor)) > count_antes
                    )
                    print(f"... Novos campos de item (total: {count_antes + 1}) apareceram.")

                # Descrição do Item
                campos_item_desc = wait.until(EC.presence_of_all_elements_located((By.XPATH, xpath_anchor)))
                campos_item_desc[-1].send_keys(item['item_descricao'])
                
                # Descrição Complementar
                if item.get('item_desc_comp'):
                    campos_desc_comp = self.driver.find_elements(By.NAME, "descricaoComplementar")
                    campos_desc_comp[-1].send_keys(item['item_desc_comp'])
                
                # Código Externo
                if item.get('item_codigo'):
                    campos_codigo = self.driver.find_elements(By.NAME, "codigoExterno")
                    campos_codigo[-1].send_keys(item['item_codigo'])
                
                # Valor (com Ctrl+A)
                if item.get('item_valor'):
                    campos_valor = self.driver.find_elements(By.NAME, "valor")
                    campo_alvo_valor = campos_valor[-1]
                    valor_do_csv = str(item['item_valor'])
                    
                    campo_alvo_valor.click(); time.sleep(0.1)
                    campo_alvo_valor.send_keys(Keys.CONTROL, "a"); time.sleep(0.1)
                    campo_alvo_valor.send_keys(Keys.BACK_SPACE); time.sleep(0.1)
                    campo_alvo_valor.send_keys(valor_do_csv)
                
                time.sleep(0.5)
            
            # 4. Salvar o GRUPO de Complemento
            print("... Itens preenchidos. Salvando Grupo de Complemento.")
            wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//button[text()='SALVAR COMPLEMENTO']")
            )).click()
            
            # 5. Esperar o modal do GRUPO fechar
            wait.until(EC.invisibility_of_element_located(
                (By.XPATH, "//button[text()='SALVAR COMPLEMENTO']")
            ))
            print(f"✅ Grupo de Complemento '{grupo_data['descricao_complemento']}' salvo.")
            time.sleep(1)
            return True
            
        except Exception as e:
            print(f"❌ Erro ao cadastrar Grupo de Complemento: {e}")
            return False

    def _acessar_complementos(self, item_data):
        """Espera a aba carregar, cadastra grupos, clica em SALVAR e fecha com ESC."""
        print("-> Acessando aba 'Complementos'...")
        try:
            wait = WebDriverWait(self.driver, 10)
            
            aba_complementos = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Complementos']"))
            )
            aba_complementos.click()
            
            print("... Esperando conteúdo da aba 'Complementos' carregar...")
            wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Adicionar Complemento')]"))
            )
            
            grupos_complemento_data = item_data.get("grupos_complemento", [])
            print(f"✅ Aba 'Complementos' aberta. {len(grupos_complemento_data)} grupos para cadastrar.")
            
            for grupo_data in grupos_complemento_data:
                self._cadastrar_grupo_complemento(grupo_data)

            print("... Todos os grupos de complementos foram processados.")
            print("... Clicando em 'SALVAR' (principal) para salvar as associações.")
            
            botao_salvar_principal = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='SALVAR']"))
            )
            botao_salvar_principal.click()
            
            time.sleep(1.5) # Pausa para salvar
            
            print("... Salvamento finalizado. Fechando modal.")
            self._fechar_modal_produto()

        except Exception as e:
            print(f"❌ Erro ao acessar ou finalizar complementos: {e}")
            self._fechar_modal_produto()

    def _preencher_modal_produto(self, item_data):
        """Preenche o formulário, salva, e decide se acessa complementos ou fecha."""
        print("... Preenchendo dados do produto no pop-up...")
        try:
            wait = WebDriverWait(self.driver, 10)
            campo_nome = wait.until(EC.presence_of_element_located((By.NAME, "nome")))
            time.sleep(0.5)

            # --- 1. Preenche os campos do PRODUTO ---
            print(f"    -> Nome: {item_data['Nome']}")
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

            # --- 2. Clica em "SALVAR" ---
            print("... Clicando em 'SALVAR' o produto.")
            botao_salvar_produto = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='SALVAR']"))
            )
            botao_salvar_produto.click()

            # --- 3. Espera a aba Complementos aparecer ---
            print("... Aguardando aba 'Complementos' ficar disponível...")
            wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Complementos']"))
            )
            print(f"✅ Produto '{item_data['Nome']}' salvo.")
            
            # --- 4. Decide o que fazer (S ou N) ---
            if str(item_data.get("PossuiComplemento")).strip().upper() == 'S':
                print("... (S) Encontrado. Acessando complementos.")
                self._acessar_complementos(item_data)
            else:
                print("... Produto não possui complementos. Fechando modal.")
                self._fechar_modal_produto()
                
            return True
            
        except Exception as e:
            print(f"❌ Erro ao preencher ou salvar o produto: {e}")
            return False

    def criar_novo_grupo(self, nome_do_grupo):
        """Clica em 'Novo Grupo', preenche o nome e salva."""
        print("-> Procurando botão 'Novo Grupo'...")
        try:
            xpath_novo_grupo = "//button[contains(text(), 'Novo Grupo')]"
            wait = WebDriverWait(self.driver, 10)
            botao_novo_grupo = wait.until(
                EC.element_to_be_clickable((By.XPATH, xpath_novo_grupo))
            )
            time.sleep(0.5)
            botao_novo_grupo.click()
            time.sleep(1.5) 

            print(f"... Preenchendo nome: {nome_do_grupo}")
            campo_descricao_grupo = wait.until(
                EC.presence_of_element_located((By.NAME, "descricao")) 
            )
            campo_descricao_grupo.send_keys(nome_do_grupo.strip().upper())
            time.sleep(0.5)

            print("... Clicando em 'SALVAR'.")
            botao_salvar_grupo = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='SALVAR']"))
            )
            botao_salvar_grupo.click()
            
            print("... Aguardando criação do grupo...")
            xpath_h6_novo = f"//h6[text()='{nome_do_grupo.strip().upper()}']"
            wait.until(EC.presence_of_element_located((By.XPATH, xpath_h6_novo)))
            
            print(f"✅ Grupo '{nome_do_grupo}' criado com sucesso.")
            return True 
            
        except Exception as e:
            print(f"❌ Erro ao tentar criar 'Novo Grupo': {e}")
            return False 

    def processar_item_cardapio(self, item_data):
        """Método principal: Encontra/Cria Grupo, Expande, Clica 'Novo Produto'."""
        nome_do_grupo = item_data["Grupo"]
        print(f"--- Processando Produto: {item_data['Nome']} (Grupo: {nome_do_grupo}) ---")
        
        grupo_button = self.encontrar_grupo(nome_do_grupo)
        
        if not grupo_button:
            print(f"❌ Grupo '{nome_do_grupo}' não encontrado.")
            sucesso_criacao = self.criar_novo_grupo(nome_do_grupo)
            if not sucesso_criacao:
                 print("❌ Falha ao criar o grupo. Abortando este item.")
                 return
            time.sleep(1) 
            grupo_button = self.encontrar_grupo(nome_do_grupo)
            if not grupo_button:
                print("❌ Erro: Não foi possível encontrar o grupo após criá-lo.")
                return

        try:
            print(f"-> Expandindo grupo '{nome_do_grupo}'...")
            if grupo_button.get_attribute("aria-expanded") == "false":
                grupo_button.click()
                time.sleep(1.5)
            else:
                print("... Grupo já estava expandido.")

            accordion_root = grupo_button.find_element(By.XPATH, "./ancestor::div[contains(@class, 'MuiAccordion-root')]")
            xpath_novo_produto = ".//button[text()='Novo Produto']"
            wait = WebDriverWait(accordion_root, 10)
            botao_novo_prod = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_novo_produto)))
            
            print("-> Clicando em 'Novo Produto'...")
            time.sleep(0.5)
            botao_novo_prod.click()
            time.sleep(1)
            
            self._preencher_modal_produto(item_data)
            
        except Exception as e:
            print(f"❌ Erro ao expandir ou clicar em 'Novo Produto': {e}")

    def fechar(self):
        """Fecha o navegador QRPedir."""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ Navegador QRPedir fechado.")
            except Exception as e:
                print(f"❌ Erro ao fechar QRPedir: {e}")
            finally:
                self.driver = None