import time
import pandas as pd
import requests
import random
import re
import unicodedata
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, ElementClickInterceptedException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.action_chains import ActionChains

# Importa a classe do outro arquivo
from bot_ncm_editor import BotNCMEditor 

class BotSischef:
    # --- CONSTANTES ---
    URL_VERIFICACAO_CONEXAO = "http://www.google.com" 
    URL_LISTAGEM_PRODUTOS = "https://sistema.sischef.com/admin/produtos/produtoList.jsf"
    URL_CADASTRO_PRODUTO = "https://sistema.sischef.com/admin/produtos/produto.jsf"
    
    # Novas Constantes de Receitas
    URL_LISTAGEM_RECEITAS = "https://sistema.sischef.com/admin/produtos/transformacao/receitaList.jsf"
    URL_CADASTRO_RECEITA = "https://sistema.sischef.com/admin/produtos/transformacao/receita.jsf"
    
    ID_CAMPO_BUSCA_LISTAGEM = "_input-busca-generica_" 
    
    # Seletor para QUALQUER pop-up de mensagem (erro, aviso, sucesso)
    SELECTOR_MENSAGEM_POPUP = "//div[contains(@class, 'ui-growl-item-container')]"
    SELECTOR_ERRO_GLOBAL = f"{SELECTOR_MENSAGEM_POPUP}[contains(@class, 'ui-state-error')]" 
    
    SELECTOR_MODAL_INTERCEPT = "div[id$='ajaxErrorHandlerDialog_modal']"

    def __init__(self, usuario, senha, log_callback=None, screenshot_callback=None, headless=False):
        if not usuario or not senha:
            raise ValueError("Usuário e senha não podem ser vazios!")
        self.usuario = usuario
        self.senha = senha
        self.headless = headless
        self.screenshot_callback = screenshot_callback
        
        self.arquivo_csv_cadastro = None 
        self.arquivo_csv_receitas = None # Novo CSV
        
        self.driver = None
        self.rodando = True
        self.start_index = 0 # Para cadastro de produtos/receitas
        self.start_index_ncm = 0 # Para NCM
        
        self.log = log_callback if log_callback else print

    def _verificar_conexao(self):
        try:
            requests.get(self.URL_VERIFICACAO_CONEXAO, timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    def iniciar(self):
        self.log("🔹 Abrindo navegador Sischef...")
        options = webdriver.ChromeOptions()
        options.add_argument("--start-maximized")
        if self.headless:
            options.add_argument("--headless=new")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
        
        try:
            # Abordagem 1: Tenta o Selenium 4 Nativo (evita o WinError 5 de bloqueio de pasta)
            self.driver = webdriver.Chrome(options=options)
        except Exception as e_native:
            self.log("⚠️ Inicializador nativo falhou, tentando WebDriverManager...")
            try:
                # Abordagem 2: Fallback para o webdriver-manager clássico
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            except Exception as e_fallback:
                 raise Exception(f"Erro ao iniciar o bot (Chrome/Driver): {e_fallback}")

        self.driver.get("https://sistema.sischef.com")
        wait = WebDriverWait(self.driver, 10) 
        
        wait.until(EC.presence_of_element_located((By.ID, "j_username")))
        time.sleep(1)

        self.driver.find_element(By.ID, "j_username").send_keys(self.usuario)
        self.driver.find_element(By.ID, "j_password").send_keys(self.senha)
        time.sleep(0.5)
        self.driver.find_element(By.ID, "login").click()

        self.log(f"🔄 Redirecionando para a lista de produtos...")
        self.driver.get(self.URL_LISTAGEM_PRODUTOS)
        
        try:
            WebDriverWait(self.driver, 15).until(
                EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA_LISTAGEM))
            )
            self.log("✅ Login realizado com sucesso.")
            self._iniciar_thread_screenshot()
        except TimeoutException:
            raise Exception(f"Timeout: A tela inicial não carregou.")

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

    # =========================================================================
    # LÓGICA DE LEITORES (PARSERS)
    # =========================================================================
    def _parse_csv_receitas(self, caminho_csv):
        """Lê o Excel no formato visual e traduz para uma estrutura lógica de RECEITAS."""
        df = pd.read_csv(caminho_csv, sep=None, engine='python', header=None, dtype=str).fillna('')
        receitas = []
        receita_atual = None
        
        for index, row in df.iterrows():
            vals = [str(v).strip() for v in row.values]
            if not any(vals): continue
                
            col_a = vals[int(0)] if len(vals) > 0 else ""
            if col_a:
                col_a_lower = col_a.lower()
                if 'ingredientes' in col_a_lower and ('quantidade' in " ".join(vals).lower() or 'unidade' in " ".join(vals).lower()):
                    continue
                elif col_a_lower == 'produto final':
                    dados_uteis = [v for v in vals[1:] if v]
                    if receita_atual and dados_uteis:
                        receita_atual['produto_final'] = {
                            'nome': dados_uteis[int(0)], 
                            'quantidade': dados_uteis[int(1)] if len(dados_uteis) > 1 else "1", 
                            'unidade': dados_uteis[int(2)] if len(dados_uteis) > 2 else "un"
                        }
                elif col_a_lower == 'modo de preparo':
                    dados_uteis = [v for v in vals[1:] if v]
                    if receita_atual and dados_uteis:
                        receita_atual['modo_preparo'] = "\n".join(dados_uteis)
                else:
                    if receita_atual: receitas.append(receita_atual)
                    receita_atual = {'nome': col_a, 'ingredientes': [], 'modo_preparo': ''}
            else:
                itens_uteis = [v for v in vals if v]
                if not itens_uteis: continue
                linha_texto = " ".join(itens_uteis).lower()
                if 'ingredientes' in linha_texto and ('quantidade' in linha_texto or 'quantidades' in linha_texto or 'unidade' in linha_texto):
                    continue
                if receita_atual and len(itens_uteis) >= 2:
                    def is_quantidade(texto): return str(texto).replace('.', '').replace(',', '').strip().isdigit()
                    primeiro_item = itens_uteis[int(0)]; segundo_item = itens_uteis[int(1)]
                    if primeiro_item.lower() == receita_atual['nome'].lower() and not is_quantidade(segundo_item):
                        itens_processar = itens_uteis[1:]
                    else:
                        itens_processar = itens_uteis
                        
                    if len(itens_processar) >= 2:
                        nome_ing = itens_processar[int(0)]; qtd_ing = itens_processar[int(1)]
                        unidade_ing = itens_processar[int(2)] if len(itens_processar) > 2 else "un"
                        valor_ing = itens_processar[int(3)] if len(itens_processar) > 3 else ""
                        if nome_ing.lower() not in ['ingredientes', 'produto final', 'modo de preparo']:
                            receita_atual['ingredientes'].append({
                                'nome': nome_ing, 'quantidade': qtd_ing, 'unidade': unidade_ing, 'valor_compra': valor_ing
                            })
        if receita_atual: receitas.append(receita_atual)
        return receitas

    def _parse_csv_fichas_tecnicas(self, caminho_csv):
        """Lê o Excel no formato específico de FICHAS TÉCNICAS (Ingredientes na Coluna A)."""
        df = pd.read_csv(caminho_csv, sep=None, engine='python', header=None, dtype=str).fillna('')
        fichas = []
        ficha_atual = None
        
        for index, row in df.iterrows():
            vals = [str(v).strip() for v in row.values]
            if not any(vals): continue
                
            linha_texto = " ".join(vals).lower()
            
            # IGNORA O CABEÇALHO (Ingredientes, Quantidades, Unidade)
            if 'ingredientes' in linha_texto and ('quantidade' in linha_texto or 'quantidades' in linha_texto or 'unidade' in linha_texto):
                continue
                
            col_a = vals[int(0)] if len(vals) > 0 else ""
            col_b = vals[int(1)] if len(vals) > 1 else ""
            col_c = vals[int(2)] if len(vals) > 2 else "" # Lemos a unidade para garantir
            
            def is_quantidade(texto):
                sobra = str(texto).replace('.', '').replace(',', '').strip()
                return sobra.isdigit()

            if col_a:
                # Se as colunas B e C estão vazias, significa que é um Nome de Ficha Técnica
                if not col_b and not col_c:
                    if ficha_atual:
                        fichas.append(ficha_atual)
                    ficha_atual = {'nome': col_a, 'ingredientes': []}
                else:
                    # Se tem algo na Col B ou Col C, é um ingrediente (mesmo sem quantidade)
                    if ficha_atual:
                        nome_ing = col_a
                        qtd_ing = str(col_b).strip() # Deixa vazio se não for informado
                        unidade_ing = col_c if str(col_c).strip() else "un"
                        valor_ing = vals[int(3)] if len(vals) > 3 else ""
                        
                        if nome_ing.lower() not in ['ingredientes']:
                            ficha_atual['ingredientes'].append({
                                'nome': nome_ing, 
                                'quantidade': qtd_ing,
                                'unidade': unidade_ing, 
                                'valor_compra': valor_ing
                            })
            else:
                # Fallback para caso os ingredientes venham deslocados para a direita
                itens_uteis = [v for v in vals if v]
                if itens_uteis and ficha_atual and len(itens_uteis) >= 2:
                    primeiro_item = itens_uteis[int(0)]
                    segundo_item = itens_uteis[int(1)]
                    
                    if primeiro_item.lower() == ficha_atual['nome'].lower() and not is_quantidade(segundo_item):
                        itens_processar = itens_uteis[1:]
                    else:
                        itens_processar = itens_uteis
                        
                    if len(itens_processar) >= 2:
                        nome_ing = itens_processar[int(0)]
                        qtd_ing = str(itens_processar[int(1)]).strip() if len(itens_processar) > 1 else "" # Deixa vazio se não for informado
                        unidade_ing = itens_processar[int(2)] if len(itens_processar) > 2 else "un"
                        valor_ing = itens_processar[int(3)] if len(itens_processar) > 3 else ""
                        
                        if nome_ing.lower() not in ['ingredientes']:
                            ficha_atual['ingredientes'].append({
                                'nome': nome_ing, 
                                'quantidade': qtd_ing,
                                'unidade': unidade_ing, 
                                'valor_compra': valor_ing
                            })

        if ficha_atual: 
            fichas.append(ficha_atual)
            
        return fichas

    # --- FLUXO 1: RECEITAS DE PRODUÇÃO ---
    def cadastrar_receitas(self, callback_progresso=None, callback_rodando=None):
        if not self.arquivo_csv_receitas:
            self.log("❌ Nenhum arquivo CSV de Receitas selecionado.")
            return

        try:
            receitas_processadas = self._parse_csv_receitas(self.arquivo_csv_receitas)
        except Exception as e:
            raise ValueError(f"❌ Erro ao organizar os dados do CSV de Receitas: {e}")

        total = len(receitas_processadas)
        self.log(f"📦 Foram identificadas {total} receitas no arquivo.")
        is_rodando = callback_rodando if callback_rodando else lambda: True
        
        wait = WebDriverWait(self.driver, 10)
        
        # Acesso inicial à tela de cadastro (Antes do Loop)
        self.driver.get(self.URL_CADASTRO_RECEITA)
        try:
            wait.until(EC.presence_of_element_located((By.ID, "form:descricao")))
            self.log("✅ Tela de cadastro de Receitas pronta!")
        except Exception as e:
            raise Exception(f"❌ Não foi possível carregar a tela de receitas: {e}")

        receita_index_atual = int(self.start_index)
        
        while receita_index_atual < total:
            if not is_rodando():
                self.log("ℹ️ Cadastro de Receitas interrompido pelo usuário.")
                break 
                
            receita = receitas_processadas[int(receita_index_atual)]
            self.log(f"🔹 Cadastrando Receita {receita_index_atual+1}/{total}: {receita['nome']}")
            if callback_progresso: callback_progresso(receita_index_atual + 1, total, None)
            
            try:
                # 1. Preenche Nome da Receita
                campo_descricao = wait.until(EC.presence_of_element_located((By.ID, "form:descricao")))
                campo_descricao.clear()
                time.sleep(0.3)
                campo_descricao.send_keys(receita['nome'])
                time.sleep(0.5)
                
                # 2. Adiciona Modo de Preparo
                if receita.get('modo_preparo') and is_rodando():
                    self.log("📝 Preenchendo Modo de Preparo...")
                    try:
                        campo_preparo = wait.until(EC.presence_of_element_located((By.ID, "form:descricaoCompleta")))
                        campo_preparo.clear()
                        time.sleep(0.3)
                        campo_preparo.send_keys(receita['modo_preparo'])
                        time.sleep(0.5)
                    except Exception as e_prep:
                        self.log(f"⚠️ Aviso: Não foi possível preencher o Modo de Preparo: {e_prep}")
                
                # 3. Adiciona Ingredientes
                self.log("📋 Processando Ingredientes...")
                for ing in receita['ingredientes']:
                    if not is_rodando(): break
                    self._adicionar_item_receita(wait, ing, tipo="ingrediente")
                    
                # 4. Adiciona Produto Final
                if 'produto_final' in receita and is_rodando():
                    self.log("🍰 Processando Produto Final...")
                    self._adicionar_item_receita(wait, receita['produto_final'], tipo="final")

                # 5. Salva a Receita
                if is_rodando():
                    self.log("💾 Rolando para o rodapé e salvando receita...")
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.8)
                    try:
                        ActionChains(self.driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                    except Exception:
                        self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ALT, 's')
                    
                    time.sleep(2.5)
                    
                    try:
                        avisos_regra = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Regra violada')]")
                        if any(aviso.is_displayed() for aviso in avisos_regra):
                            self.log(f"⚠️ Erro ao salvar receita (Pode já existir): {receita['nome']}")
                            try:
                                btn_ok = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Ok, obrigado')]")
                                self.driver.execute_script("arguments[0].click();", btn_ok)
                                time.sleep(1)
                            except:
                                self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                                time.sleep(1)
                        else:
                            self.log(f"✅ Receita '{receita['nome']}' salva com sucesso!")
                    except: pass
                        
                # 6. Prepara próxima receita
                receita_index_atual += 1
                
                if receita_index_atual < total and is_rodando():
                    self.log("➡️ Preparando para cadastrar a próxima receita...")
                    try:
                        self.driver.get(self.URL_LISTAGEM_RECEITAS)
                        time.sleep(1)
                        botao_nova_receita = WebDriverWait(self.driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/admin/produtos/transformacao/receita.jsf') and contains(@class, 'btn')]"))
                        )
                        self.driver.execute_script("arguments[0].click();", botao_nova_receita)
                        wait.until(EC.presence_of_element_located((By.ID, "form:descricao")))
                        time.sleep(1) 
                    except Exception as e_nav:
                        self.driver.get(self.URL_CADASTRO_RECEITA)
                        wait.until(EC.presence_of_element_located((By.ID, "form:descricao")))
                        time.sleep(1)
                
            except Exception as e:
                self.log(f"❌ Erro ao cadastrar receita {receita['nome']}: {e}")
                receita_index_atual += 1
                if is_rodando() and receita_index_atual < total:
                    try:
                        self.driver.get(self.URL_CADASTRO_RECEITA)
                        wait.until(EC.presence_of_element_located((By.ID, "form:descricao")))
                    except: pass
                
        if receita_index_atual == total and is_rodando():
            self.start_index = 0
            self.log("✅ Cadastro de todas as receitas concluído!")
        return True

    # --- FLUXO 2: FICHAS TÉCNICAS NO PRODUTO (NOVO) ---
    def cadastrar_fichas_tecnicas(self, callback_progresso=None, callback_rodando=None):
        if not self.arquivo_csv_receitas:
            self.log("❌ Nenhum arquivo CSV selecionado.")
            return

        try:
            fichas_processadas = self._parse_csv_fichas_tecnicas(self.arquivo_csv_receitas)
        except Exception as e:
            raise ValueError(f"❌ Erro ao organizar os dados do CSV de Fichas: {e}")

        total = len(fichas_processadas)
        self.log(f"📦 Foram identificadas {total} fichas técnicas no arquivo.")
        is_rodando = callback_rodando if callback_rodando else lambda: True
        
        wait = WebDriverWait(self.driver, 10)
        ficha_index_atual = int(self.start_index)
        
        while ficha_index_atual < total:
            if not is_rodando():
                self.log("ℹ️ Cadastro de Ficha Técnica interrompido.")
                break 
                
            ficha = fichas_processadas[int(ficha_index_atual)]
            nome_produto = str(ficha['nome']).strip()
            self.log(f"🔹 Processando Ficha Técnica {ficha_index_atual+1}/{total}: {nome_produto}")
            if callback_progresso: callback_progresso(ficha_index_atual + 1, total, None)
            
            try:
                # 1. Acessa a Listagem de Produtos
                self.driver.get(self.URL_LISTAGEM_PRODUTOS)
                campo_busca = wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                campo_busca.clear()
                time.sleep(0.3)
                campo_busca.send_keys(nome_produto)
                time.sleep(0.5)
                campo_busca.send_keys(Keys.ENTER)
                time.sleep(2.5)
                
                # 2. Verifica se encontrou o produto
                produto_nao_encontrado = False
                try:
                    self.driver.find_element(By.XPATH, "//td[contains(text(), 'Nada encontrado')]")
                    produto_nao_encontrado = True
                except:
                    pass
                
                # 3. Se não encontrou, realiza o cadastro rápido
                if produto_nao_encontrado:
                    self.log(f"⚠️ Produto '{nome_produto}' não encontrado. Realizando cadastro (PDV)...")
                    btn_novo = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.mui-btn.mui-btn-text")))
                    btn_novo.click()
                    time.sleep(1.5)
                    wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
                    
                    unidade_medida = ""
                    if 'produto_final' in ficha:
                        unidade_medida = ficha['produto_final'].get('unidade', '')
                    
                    row_falsa = {
                        'Descrição': nome_produto,
                        'Grupo': 'produtos PDV',
                        'Unidade de Medida': unidade_medida,
                        'Código de Barras': '',     # Deixando vazio o bot força o 'TAB + ENTER' para gerar
                        'NCM': '21069090',
                        'Preço de Compra': '0,00',
                        'Preço de Venda': '0,00'
                    }
                    
                    mapeamento = {
                        'Descrição': 'tabSessoesProduto:descricao',
                        'Grupo': 'tabSessoesProduto:grupoProduto_input',
                        'Unidade de Medida': 'tabSessoesProduto:unidadeMedida',
                        'Código de Barras': 'tabSessoesProduto:codigoBarras',
                        'NCM': 'tabSessoesProduto:ncm',
                        'Preço de Compra': 'tabSessoesProduto:valorUnitarioCompra',
                        'Preço de Venda': 'tabSessoesProduto:valorUnitarioVenda'
                    }
                    
                    self._preencher_e_salvar_sischef(wait, row_falsa, mapeamento)
                    time.sleep(2.5) # Aguarda salvar no servidor
                    self.log(f"✅ Produto base '{nome_produto}' cadastrado com sucesso.")
                    
                    # Volta para a listagem para encontrar o botão de Editar
                    self.driver.get(self.URL_LISTAGEM_PRODUTOS)
                    campo_busca = wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                    campo_busca.clear()
                    time.sleep(0.3)
                    campo_busca.send_keys(nome_produto)
                    time.sleep(0.5)
                    campo_busca.send_keys(Keys.ENTER)
                    time.sleep(2.5)
                
                # 4. Clica em Editar
                self.log(f"➡️ Abrindo modo de edição do produto '{nome_produto}'...")
                btn_edit = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn') and contains(., 'Editar')]")))
                self.driver.execute_script("arguments[0].click();", btn_edit)
                time.sleep(2)
                
                # 5. Vai para a aba Ficha Técnica / Composição
                self.log("➡️ Acessando a aba 'Composição' (Ficha técnica)...")
                try:
                    aba_ficha = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Composição') or contains(translate(text(), 'FICHATÉCNICA', 'fichatecnica'), 'ficha')]")))
                    self.driver.execute_script("arguments[0].click();", aba_ficha)
                    time.sleep(2.0) # Aumentei o tempo para garantir que a aba abra e carregue totalmente
                except Exception as e_aba:
                    self.log(f"⚠️ Não consegui clicar na aba Composição. Verifique se existe! ({e_aba})")
                
                # 6. Adiciona Ingredientes
                self.log("📋 Inserindo Ingredientes (Composição)...")
                for ing in ficha['ingredientes']:
                    if not is_rodando(): break
                    self._adicionar_item_ficha_tecnica(wait, ing)
                    
                # 7. Salva o Produto
                if is_rodando():
                    self.log("💾 Salvando Ficha Técnica...")
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.5)
                    try:
                        ActionChains(self.driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                    except Exception:
                        self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ALT, 's')
                    time.sleep(3.0)
                    self.log(f"✅ Ficha técnica de '{nome_produto}' concluída!")
                    
                ficha_index_atual += 1
                
            except Exception as e:
                self.log(f"❌ Erro ao processar ficha técnica '{nome_produto}': {e}")
                ficha_index_atual += 1
                # Volta para a listagem para limpar a tela de erro
                if is_rodando() and ficha_index_atual < total:
                    try:
                        self.driver.get(self.URL_LISTAGEM_PRODUTOS)
                        time.sleep(1.5)
                    except: pass
                
        if ficha_index_atual == total and is_rodando():
            self.start_index = 0
            self.log("✅ Cadastro de todas as Fichas Técnicas concluído!")
        return True

    def _adicionar_item_receita(self, wait, item, tipo="ingrediente"):
        """Insere um ingrediente ou produto final. Cria em nova aba se não existir."""
        if tipo == "ingrediente":
            xpath_btn_add = "//a[contains(@onclick, 'tabelaEntradas') and contains(., 'Adicionar novo ingrediente')]"
            id_tabela = "tabelaEntradas"
        else:
            xpath_btn_add = "//a[contains(@onclick, 'tabelaSaidas') and contains(., 'Adicionar produto final')]"
            id_tabela = "tabelaSaidas"
            
        # 1. Clica no botão (+)
        btn_add = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_btn_add)))
        self.driver.execute_script("arguments[0].click();", btn_add)
        time.sleep(1.0)
        
        # 2. Encontra o ÚLTIMO campo de busca
        xpath_inputs_produto = f"//input[contains(@id, '{id_tabela}') and contains(@id, 'produto_input')]"
        inputs_produto = self.driver.find_elements(By.XPATH, xpath_inputs_produto)
        
        if not inputs_produto:
            raise Exception(f"Campo de busca de {tipo} não abriu.")
            
        input_produto = inputs_produto[int(-1)]
        
        # 3. Pesquisa o produto
        input_produto.clear()
        time.sleep(0.3)
        input_produto.send_keys(item['nome'])
        time.sleep(1.5)
        
        def limpar_texto(t):
            if not t: return ""
            n = unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('utf-8')
            return re.sub(r'\s+', ' ', n).replace('/', '-').lower().strip()

        nome_busca_limpo = limpar_texto(item['nome'])
        item_encontrado = False
        
        try:
            opcoes_lista = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'ui-autocomplete-item')]")
            for opcao in opcoes_lista:
                texto_bruto = opcao.get_attribute("data-item-label")
                if not texto_bruto: 
                    texto_bruto = opcao.get_attribute("textContent")
                if not texto_bruto: 
                    texto_bruto = opcao.text
                    
                texto_opcao_limpo = limpar_texto(texto_bruto)
                
                is_match = False
                if texto_opcao_limpo == nome_busca_limpo:
                    is_match = True
                elif texto_opcao_limpo.startswith(nome_busca_limpo):
                    resto = texto_opcao_limpo[len(nome_busca_limpo):].strip()
                    if resto == "" or resto.startswith('-') or resto.startswith('/'):
                        is_match = True
                        
                if is_match:
                    try:
                        alvo_clique = opcao.find_element(By.TAG_NAME, "td")
                    except:
                        alvo_clique = opcao
                    
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", alvo_clique)
                    time.sleep(0.2)
                    try:
                        alvo_clique.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", alvo_clique)
                        
                    item_encontrado = True
                    time.sleep(0.5)
                    break
        except Exception: pass
            
        # 4. Cria em nova aba se não encontrou
        if not item_encontrado:
            self.log(f"⚠️ {tipo.capitalize()} '{item['nome']}' não encontrado. Criando em nova aba...")
            self._criar_produto_auxiliar(wait, item, tipo)
            
            inputs_produto = self.driver.find_elements(By.XPATH, xpath_inputs_produto)
            input_produto = inputs_produto[int(-1)]
            input_produto.clear()
            time.sleep(0.5)
            input_produto.send_keys(item['nome'])
            time.sleep(1.5)
            
            try:
                opcoes_lista = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'ui-autocomplete-item')]")
                item_clicado = False
                for opcao in opcoes_lista:
                    texto_bruto = opcao.get_attribute("data-item-label")
                    if not texto_bruto: 
                        texto_bruto = opcao.get_attribute("textContent")
                    if not texto_bruto: 
                        texto_bruto = opcao.text
                        
                    texto_opcao_limpo = limpar_texto(texto_bruto)
                    
                    is_match = False
                    if texto_opcao_limpo == nome_busca_limpo:
                        is_match = True
                    elif texto_opcao_limpo.startswith(nome_busca_limpo):
                        resto = texto_opcao_limpo[len(nome_busca_limpo):].strip()
                        if resto == "" or resto.startswith('-') or resto.startswith('/'):
                            is_match = True
                            
                    if is_match:
                        try:
                            alvo_clique = opcao.find_element(By.TAG_NAME, "td")
                        except:
                            alvo_clique = opcao
                        
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", alvo_clique)
                        time.sleep(0.2)
                        try:
                            alvo_clique.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", alvo_clique)
                            
                        item_clicado = True
                        time.sleep(0.5)
                        break
                if not item_clicado:
                    input_produto.send_keys(Keys.ENTER)
            except Exception:
                input_produto.send_keys(Keys.ENTER)
                
        # 5. Preenche a quantidade
        xpath_inputs_qtd = f"//input[contains(@id, '{id_tabela}') and contains(@id, ':quantidade') and @type='text']"
        inputs_qtd = self.driver.find_elements(By.XPATH, xpath_inputs_qtd)
        if inputs_qtd:
            input_qtd = inputs_qtd[int(-1)]
            
            if item['quantidade']:
                input_qtd.click()
                time.sleep(0.2)
                input_qtd.send_keys(Keys.CONTROL, "a")
                time.sleep(0.1)
                input_qtd.send_keys(Keys.BACK_SPACE)
                time.sleep(0.1)
                
                # --- CORREÇÃO DA MÁSCARA (Sischef empurra números da direita para a esquerda) ---
                # Garante que um "1" enviado seja formatado como "1,0000" para ocupar as casas corretamente.
                qtd_str = str(item['quantidade']).strip().replace(",", ".")
                try:
                    qtd_float = float(qtd_str)
                    qtd_final = f"{qtd_float:.4f}".replace(".", ",")
                except ValueError:
                    qtd_final = str(item['quantidade']).replace(".", ",")
                
                input_qtd.send_keys(qtd_final)
                time.sleep(0.2)
            
            input_qtd.send_keys(Keys.TAB) 
            time.sleep(0.5)

    def _adicionar_item_ficha_tecnica(self, wait, item):
        """Insere um ingrediente especificamente na aba de Composição (Ficha Técnica)."""
        id_campo_busca = "tabSessoesProduto:produtoComposicao_input"
        
        # --- CORREÇÃO: Espera vital para garantir que o AJAX do último 'TAB' (quantidade) terminou ---
        time.sleep(1.5)
        
        # Garante que o campo de busca está presente, interativo e VISÍVEL na tela
        input_produto = wait.until(EC.visibility_of_element_located((By.ID, id_campo_busca)))
        
        # Força o campo para o centro da tela
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_produto)
        time.sleep(0.3)
        
        # --- REMOVIDO ACTIONCHAINS: Foco forçado puramente com JavaScript (evita bug de float coordinates do Selenium 4) ---
        self.driver.execute_script("arguments[0].focus(); arguments[0].click(); arguments[0].value = '';", input_produto)
        time.sleep(0.3)
        
        # Refaz a busca para evitar que o elemento tenha ficado obsoleto (Stale Element) e envia as teclas
        input_produto = self.driver.find_element(By.ID, id_campo_busca)
        input_produto.send_keys(Keys.CONTROL, "a")
        time.sleep(0.1)
        input_produto.send_keys(Keys.BACK_SPACE)
        time.sleep(0.3)
        
        # Digita o ingrediente e aguarda o Sischef carregar a lista suspensa
        input_produto.send_keys(item['nome'])
        time.sleep(2.0) 
        
        # FUNÇÃO PARA LIMPAR ACENTOS E ESPAÇOS ANTES DE COMPARAR
        def limpar_texto(t):
            if not t: return ""
            n = unicodedata.normalize('NFKD', str(t)).encode('ASCII', 'ignore').decode('utf-8')
            return re.sub(r'\s+', ' ', n).replace('/', '-').lower().strip()

        nome_busca_limpo = limpar_texto(item['nome'])
        item_encontrado = False
        
        try:
            opcoes_lista = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'ui-autocomplete-item')]")
            for opcao in opcoes_lista:
                texto_bruto = opcao.get_attribute("data-item-label")
                if not texto_bruto: 
                    texto_bruto = opcao.get_attribute("textContent")
                if not texto_bruto: 
                    texto_bruto = opcao.text
                    
                texto_opcao_limpo = limpar_texto(texto_bruto)
                
                is_match = False
                if texto_opcao_limpo == nome_busca_limpo:
                    is_match = True
                elif texto_opcao_limpo.startswith(nome_busca_limpo):
                    resto = texto_opcao_limpo[len(nome_busca_limpo):].strip()
                    if resto == "" or resto.startswith('-') or resto.startswith('/'):
                        is_match = True
                        
                if is_match:
                    try:
                        alvo_clique = opcao.find_element(By.TAG_NAME, "td")
                    except:
                        alvo_clique = opcao
                        
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", alvo_clique)
                    time.sleep(0.2)
                    try:
                        alvo_clique.click()
                    except:
                        self.driver.execute_script("arguments[0].click();", alvo_clique)
                    
                    item_encontrado = True
                    time.sleep(1.0)
                    break
        except Exception: pass
            
        if not item_encontrado:
            self.log(f"⚠️ Ingrediente '{item['nome']}' não encontrado. Criando em nova aba...")
            
            self._criar_produto_auxiliar(wait, item, tipo="ingrediente")
            
            time.sleep(1.5)
            input_produto = wait.until(EC.visibility_of_element_located((By.ID, id_campo_busca)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_produto)
            time.sleep(0.5)
            
            try:
                self.driver.execute_script("arguments[0].value = ''; arguments[0].focus();", input_produto)
                input_produto.click()
            except:
                self.driver.execute_script("arguments[0].click();", input_produto)
            time.sleep(0.3)
            
            input_produto = self.driver.find_element(By.ID, id_campo_busca)
            input_produto.send_keys(Keys.CONTROL, "a")
            time.sleep(0.1)
            input_produto.send_keys(Keys.BACK_SPACE)
            time.sleep(0.3)
            
            input_produto.send_keys(item['nome'])
            time.sleep(2.0)
            
            try:
                opcoes_lista = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'ui-autocomplete-item')]")
                item_clicado = False
                for opcao in opcoes_lista:
                    texto_bruto = opcao.get_attribute("data-item-label")
                    if not texto_bruto: 
                        texto_bruto = opcao.get_attribute("textContent")
                    if not texto_bruto: 
                        texto_bruto = opcao.text
                        
                    texto_opcao_limpo = limpar_texto(texto_bruto)
                    
                    is_match = False
                    if texto_opcao_limpo == nome_busca_limpo:
                        is_match = True
                    elif texto_opcao_limpo.startswith(nome_busca_limpo):
                        resto = texto_opcao_limpo[len(nome_busca_limpo):].strip()
                        if resto == "" or resto.startswith('-') or resto.startswith('/'):
                            is_match = True
                            
                    if is_match:
                        try:
                            alvo_clique = opcao.find_element(By.TAG_NAME, "td")
                        except:
                            alvo_clique = opcao
                            
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", alvo_clique)
                        time.sleep(0.2)
                        try:
                            alvo_clique.click()
                        except:
                            self.driver.execute_script("arguments[0].click();", alvo_clique)
                            
                        item_clicado = True
                        time.sleep(1.0)
                        break
                if not item_clicado:
                    input_produto.send_keys(Keys.ENTER) 
                    time.sleep(1.0)
            except Exception:
                input_produto.send_keys(Keys.ENTER)
                time.sleep(1.0)
                
        # --- NOVO PASSO: CLICAR NO BOTÃO 'ADICIONAR' DA COMPOSIÇÃO ---
        try:
            xpath_btn_adicionar = "//a[contains(@onclick, 'composicaoProdutoDataTable') and contains(@class, 'ui-commandlink')]"
            btn_adicionar = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_btn_adicionar)))
            
            self.driver.execute_script("arguments[0].click();", btn_adicionar)
            time.sleep(1.5)
        except Exception as e_btn:
            self.log(f"⚠️ Aviso: Não consegui clicar no botão 'Adicionar' da composição. Tentando continuar... ({e_btn})")
                
        # Preenche a quantidade na linha recém-adicionada
        xpath_inputs_qtd = "//input[contains(@id, ':composicaoProdutoQuantidade') and @type='text']"
        inputs_qtd = self.driver.find_elements(By.XPATH, xpath_inputs_qtd)
        if inputs_qtd:
            input_qtd = inputs_qtd[int(-1)]
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_qtd)
            time.sleep(0.3)
            
            if item['quantidade']:
                input_qtd.click()
                time.sleep(0.2)
                input_qtd.send_keys(Keys.CONTROL, "a")
                time.sleep(0.1)
                input_qtd.send_keys(Keys.BACK_SPACE)
                time.sleep(0.1)
                
                # --- CORREÇÃO DA MÁSCARA (Sischef empurra números da direita para a esquerda) ---
                # Garante que um "1" enviado seja formatado como "1,0000" para ocupar as casas corretamente.
                qtd_str = str(item['quantidade']).strip().replace(",", ".")
                try:
                    qtd_float = float(qtd_str)
                    qtd_final = f"{qtd_float:.4f}".replace(".", ",")
                except ValueError:
                    qtd_final = str(item['quantidade']).replace(".", ",")
                
                input_qtd.send_keys(qtd_final)
                time.sleep(0.2)
            
            # O TAB é importante mesmo sem preencher para validar a linha
            input_qtd.send_keys(Keys.TAB) 
            time.sleep(0.5)
        else:
            self.log(f"❌ Não foi possível encontrar o campo de quantidade para '{item['nome']}'.")

    def _criar_produto_auxiliar(self, wait, item, tipo="ingrediente"):
        """Abre nova aba, cadastra um ingrediente/produto usando o _preencher_e_salvar_sischef e fecha a aba."""
        aba_receita = self.driver.current_window_handle
        
        self.driver.execute_script("window.open('/admin/produtos/produto.jsf', '_blank');")
        time.sleep(1.5)
        self.driver.switch_to.window(self.driver.window_handles[int(-1)])
        
        try:
            wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
            self.log(f"➡️ Cadastrando item ausente: {item['nome']}")
            
            grupo_alvo = "Pré Preparo" if tipo == "final" else "INGREDIENTES"
            
            row_falsa = {
                'Descrição': item['nome'],
                'Grupo': grupo_alvo,
                'Unidade de Medida': item.get('unidade', ''),
                'Código de Barras': '',     
                'NCM': '00',            
                'Preço de Compra': item.get('valor_compra', '0,00'),
                'Preço de Venda': '0,00'
            }
            
            mapeamento = {
                'Descrição': 'tabSessoesProduto:descricao',
                'Grupo': 'tabSessoesProduto:grupoProduto_input',
                'Unidade de Medida': 'tabSessoesProduto:unidadeMedida',
                'Código de Barras': 'tabSessoesProduto:codigoBarras',
                'NCM': 'tabSessoesProduto:ncm',
                'Preço de Compra': 'tabSessoesProduto:valorUnitarioCompra',
                'Preço de Venda': 'tabSessoesProduto:valorUnitarioVenda'
            }
            
            self._preencher_e_salvar_sischef(wait, row_falsa, mapeamento)
            time.sleep(2.5)
            
        except Exception as e:
            self.log(f"❌ Erro ao tentar criar o produto na nova aba: {e}")
            
        finally:
            self.driver.close()
            self.driver.switch_to.window(aba_receita)
            time.sleep(1.0)

    # =========================================================================
    # LÓGICA DE CADASTRO DE PRODUTOS (EXISTENTE E INTOCÁVEL)
    # =========================================================================
    def cadastrar_produtos(self, callback_progresso=None, callback_rodando=None):
        if not self.arquivo_csv_cadastro: 
            self.log("❌ Nenhum arquivo CSV de Cadastro selecionado.")
            return

        try:
            dados = pd.read_csv(self.arquivo_csv_cadastro, sep=None, engine='python', dtype=str)
        except Exception as e:
            raise ValueError(f"❌ Erro ao ler o CSV: {e}")

        self.driver.get(self.URL_CADASTRO_PRODUTO)
        wait = WebDriverWait(self.driver, 10)
        try:
            wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
            try:
                botao_novo = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "a.mui-btn.mui-btn-text")))
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
            "Descrição": "tabSessoesProduto:descricao",
            "Grupo": "tabSessoesProduto:grupoProduto_input",
            "Unidade de Medida": "tabSessoesProduto:unidadeMedida", 
            "Código de Barras": "tabSessoesProduto:codigoBarras",
            "NCM": "tabSessoesProduto:ncm",
            "Preço de Compra": "tabSessoesProduto:valorUnitarioCompra",
            "Preço de Venda": "tabSessoesProduto:valorUnitarioVenda"
        }

        def limpar_nome_coluna(nome):
            n = unicodedata.normalize('NFKD', str(nome)).encode('ASCII', 'ignore').decode('utf-8')
            return re.sub(r'[^a-zA-Z0-9]', '', n).lower()

        aliases = {
            'descricao': 'Descrição',
            'grupo': 'Grupo',
            'unidadedemedida': 'Unidade de Medida',
            'unidademedida': 'Unidade de Medida',
            'codigodebarras': 'Código de Barras',
            'codigobarras': 'Código de Barras',
            'ncm': 'NCM',
            'precodecompra': 'Preço de Compra',
            'precocompra': 'Preço de Compra',
            'precodevenda': 'Preço de Venda',
            'precovenda': 'Preço de Venda'
        }
        
        colunas_encontradas = {}
        novas_colunas = []
        
        for col in dados.columns:
            col_limpa = limpar_nome_coluna(col)
            if col_limpa in aliases:
                chave_original = aliases[col_limpa]
                campo_id = mapeamento_campos[chave_original]
                novas_colunas.append(chave_original)
                colunas_encontradas[chave_original] = campo_id
            else:
                novas_colunas.append(col)
                self.log(f"⚠️ Coluna '{col}' não mapeada pelo robô. Será ignorada.")
                
        dados.columns = novas_colunas

        total = len(dados)
        self.log(f"📦 Total de produtos a cadastrar: {total} (Campos mapeados: {list(colunas_encontradas.keys())})")
        is_rodando = callback_rodando if callback_rodando else lambda: True
        produto_index_atual = self.start_index
        
        while produto_index_atual < total:
            if not is_rodando():
                self.log("ℹ️ Cadastro Sischef interrompido pelo usuário.")
                break 
            
            i = produto_index_atual
            row = dados.iloc[i]
            produto_descricao = str(row.get('Descrição', f'ITEM {i+1} SEM DESCRIÇÃO')).strip() 

            if not self._verificar_conexao():
                self.log("🚨 CONEXÃO PERDIDA. PAUSANDO...")
                if callback_progresso: callback_progresso(i, total, None) 
                while not self._verificar_conexao():
                    if not is_rodando():
                        self.log("ℹ️ Cadastro Sischef interrompido (sem conexão).")
                        return
                    time.sleep(10)
                
                self.log("🟢 CONEXÃO RESTABELECIDA. RETOMANDO...")
                self.driver.get(self.URL_CADASTRO_PRODUTO) 
                WebDriverWait(self.driver, 10).until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
                if callback_progresso: callback_progresso(i, total, None)
            
            log_msg_sischef = f"🔹 Cadastrando produto {i+1}/{total}: {produto_descricao}"
            self.log(log_msg_sischef)
            if callback_progresso: callback_progresso(i + 1, total, None)

            try:
                self._preencher_e_salvar_sischef(wait, row, colunas_encontradas)
                time.sleep(1.0) 

                produto_duplicado = False
                try:
                    avisos_regra = self.driver.find_elements(By.XPATH, "//*[contains(text(), 'Regra violada')]")
                    for aviso in avisos_regra:
                        if aviso.is_displayed():
                            produto_duplicado = True
                            msg_dup = f"⛔ PRODUTO DUPLICADO: {produto_descricao}"
                            self.log(msg_dup)
                            try:
                                btn_ok = self.driver.find_element(By.XPATH, "//*[contains(text(), 'Ok, obrigado')]")
                                self.driver.execute_script("arguments[0].click();", btn_ok)
                                time.sleep(1)
                            except:
                                self.log("⚠️ Não foi possível clicar em 'Ok, obrigado', tentando ESC.")
                                self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                            break 
                except Exception: pass 

                if produto_duplicado:
                    produto_index_atual += 1
                    if callback_progresso: callback_progresso(i + 1, total, f"⛔ Duplicado: {produto_descricao}")
                    self.driver.get(self.URL_CADASTRO_PRODUTO)
                    wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
                    continue 

                try:
                    botao_novo = WebDriverWait(self.driver, 1.5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, "a.mui-btn.mui-btn-text"))
                    )
                    botao_novo.click()
                    time.sleep(0.8)
                except (TimeoutException, ElementClickInterceptedException):
                    self.log(f"⚠️ Não foi possível confirmar o salvamento de: {produto_descricao}.")
                    self.driver.get(self.URL_CADASTRO_PRODUTO)
                    wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))

                produto_index_atual += 1 
                if callback_progresso: callback_progresso(i + 1, total, f"✅ Produto {i+1}/{total} processado.")

            except Exception as e:
                self.log(f"❌ Falha crítica no ciclo do produto {i+1}: {e}")
                self.log(f"❌ ITEM PULADO: {produto_descricao} (Índice {i + 1})")
                produto_index_atual += 1 
                try:
                    self.driver.get(self.URL_CADASTRO_PRODUTO)
                    wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao")))
                except Exception: pass

        if produto_index_atual == total and is_rodando():
            self.start_index = 0
            
        return True

    def _preencher_e_salvar_sischef(self, wait, row_data, mapeamento_encontrado):
        """Função base e imbatível que preenche produtos principais e ingredientes de receitas."""
        for col_csv, campo_id in mapeamento_encontrado.items():
            
            valor_original = row_data.get(col_csv)
            if pd.isna(valor_original): valor = ""
            else:
                valor = str(valor_original).strip()
                if valor.lower() in ['nan', 'null', 'none']: valor = ""
            
            if campo_id == "tabSessoesProduto:unidadeMedida" and not valor:
                continue
            
            if col_csv == 'Grupo' and valor.endswith('.0'): valor = valor[:-2]
            
            if campo_id in ["tabSessoesProduto:valorUnitarioCompra", "tabSessoesProduto:valorUnitarioVenda"]:
                if not valor: valor = "0,00"
                else:
                    try:
                        valor_numerico = float(valor.replace(",", "."))
                        valor = f"{valor_numerico:.2f}".replace(".", ",") 
                    except ValueError: valor = "0,00"

            input_elem = wait.until(EC.element_to_be_clickable((By.ID, campo_id)))
            
            if campo_id == "tabSessoesProduto:unidadeMedida":
                if valor:
                    valor_upper = valor.upper() 
                    try: 
                        Select(input_elem).select_by_value(valor_upper)
                    except Exception:
                        try:
                            select_box = Select(input_elem)
                            opcao_encontrada = False
                            for option in select_box.options:
                                opt_text = option.text.upper().strip()
                                if opt_text == valor_upper or opt_text.startswith(f"{valor_upper} -") or opt_text.startswith(f"{valor_upper}-"):
                                    select_box.select_by_visible_text(option.text)
                                    opcao_encontrada = True
                                    break
                            
                            if not opcao_encontrada:
                                self.log(f"⚠️ Não encontrei a unidade '{valor_upper}' na lista.")
                        except Exception as e_select: 
                            self.log(f"⚠️ Falha ao selecionar Unidade '{valor}'. {e_select}")
                    time.sleep(0.5) 
                continue 
            
            elif campo_id == "tabSessoesProduto:codigoBarras":
                input_elem.clear()
                time.sleep(0.3)
                if valor:
                    input_elem.send_keys(valor)
                    time.sleep(0.3)
                else:
                    self.log("⚙️ Sem código de barras. Tentando gerar código sequencial...")
                    try:
                        try:
                            btn_gerar = self.driver.find_element(By.XPATH, "//a[contains(., 'Gerar código sequencial') or contains(@class, 'fa-refresh')]")
                            self.driver.execute_script("arguments[0].click();", btn_gerar)
                            time.sleep(1.5)
                        except: pass
                        
                        input_elem = wait.until(EC.presence_of_element_located((By.ID, campo_id)))
                        
                        if not input_elem.get_attribute('value'):
                            self.log("⚙️ Fallback: Gerando via teclado (TAB + ENTER)...")
                            input_elem.click()
                            time.sleep(0.2)
                            input_elem.send_keys(Keys.TAB)
                            time.sleep(0.3)
                            self.driver.switch_to.active_element.send_keys(Keys.ENTER)
                            time.sleep(1.5)
                    except Exception as e_cb: 
                        self.log(f"⚠️ Falha ao gerar CB: {e_cb}")
                continue
            
            elif campo_id == "tabSessoesProduto:grupoProduto_input":
                input_elem.clear()
                time.sleep(0.5) 
                input_elem.send_keys(valor)
                time.sleep(1.5) 
                
                grupo_encontrado = False
                try:
                    opcoes_lista = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'ui-autocomplete-item')]")
                    for opcao in opcoes_lista:
                        texto_bruto = opcao.get_attribute("data-item-label")
                        if not texto_bruto: 
                            texto_bruto = opcao.get_attribute("textContent")
                        if not texto_bruto: 
                            texto_bruto = opcao.text
                            
                        texto_opcao = texto_bruto.strip().upper()
                        valor_busca = str(valor).strip().upper()
                        
                        if (texto_opcao == valor_busca or 
                            texto_opcao.startswith(f"{valor_busca} -") or 
                            texto_opcao.startswith(f"{valor_busca}-") or 
                            f" - {valor_busca}" in texto_opcao or 
                            f"-{valor_busca}" in texto_opcao):
                            
                            opcao.click()
                            grupo_encontrado = True
                            time.sleep(0.5)
                            break
                except Exception: pass
                
                if not grupo_encontrado:
                    self.log(f"⚠️ Grupo '{valor}' não encontrado. Criando novo...")
                    try:
                        aba_produto = self.driver.current_window_handle
                        
                        btn_novo_grupo = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/admin/produtos/grupoproduto.jsf')]")))
                        self.driver.execute_script("arguments[0].click();", btn_novo_grupo)
                        time.sleep(2) 
                        
                        janelas = self.driver.window_handles
                        if len(janelas) > 1:
                            aba_nova = janelas[-1]
                            
                            self.driver.switch_to.window(aba_nova)
                            time.sleep(1.5) 
                            
                            try:
                                campo_nome_grupo = wait.until(EC.element_to_be_clickable((By.ID, "form:tabview:descricao")))
                                campo_nome_grupo.clear()
                                time.sleep(0.3)
                                campo_nome_grupo.send_keys(valor)
                                time.sleep(0.5)
                                
                                campo_nome_grupo.click()
                                time.sleep(0.3)
                                campo_nome_grupo.send_keys(Keys.ALT, "s")
                                time.sleep(3.5) 
                            except Exception as e_cadastro_grupo:
                                self.log(f"❌ Erro novo grupo na nova aba: {e_cadastro_grupo}")
                            
                            self.driver.close()
                            self.driver.switch_to.window(aba_produto)
                            time.sleep(1)
                            
                            input_elem = wait.until(EC.element_to_be_clickable((By.ID, campo_id)))
                            input_elem.clear()
                            time.sleep(0.5)
                            input_elem.send_keys(valor)
                            time.sleep(1.5)
                            
                            try:
                                opcoes_lista_nova = self.driver.find_elements(By.XPATH, "//*[contains(@class, 'ui-autocomplete-item')]")
                                item_clicado = False
                                for opcao in opcoes_lista_nova:
                                    texto_bruto = opcao.get_attribute("data-item-label")
                                    if not texto_bruto: 
                                        texto_bruto = opcao.get_attribute("textContent")
                                    if not texto_bruto: 
                                        texto_bruto = opcao.text
                                        
                                    texto_opcao = texto_bruto.strip().upper()
                                    valor_busca = str(valor).strip().upper()
                                    
                                    if (texto_opcao == valor_busca or 
                                        texto_opcao.startswith(f"{valor_busca} -") or 
                                        texto_opcao.startswith(f"{valor_busca}-") or 
                                        f" - {valor_busca}" in texto_opcao or 
                                        f"-{valor_busca}" in texto_opcao):
                                        
                                        opcao.click()
                                        item_clicado = True
                                        break
                                if not item_clicado: input_elem.send_keys(Keys.ENTER)
                            except Exception: input_elem.send_keys(Keys.ENTER)
                        else:
                            input_elem.send_keys(Keys.ENTER) 
                            
                    except Exception as e_grupo:
                        self.log(f"❌ Erro automatizar novo grupo: {e_grupo}")
                        input_elem.send_keys(Keys.ENTER)
            else:
                input_elem.clear()
                time.sleep(0.5) 
                if valor: input_elem.send_keys(valor)
                time.sleep(0.3)
        
        self.driver.find_element(By.ID, "tabSessoesProduto:descricao").click()
        time.sleep(0.3)
        self.driver.find_element(By.ID, "tabSessoesProduto:descricao").send_keys(Keys.ALT, "s")

        self.log("Produto cadastrado com sucesso")
        
    def editar_ncm(self, arquivo_csv, callback_progresso):
        if not self.driver: raise Exception("Navegador não iniciado. Execute 'iniciar' primeiro.")
        if not arquivo_csv: raise FileNotFoundError("Caminho do CSV de NCM não definido.")
        self.log(f"Iniciando BotNCMEditor com CSV: {arquivo_csv}")
        ncm_editor = BotNCMEditor(
            driver=self.driver, csv_path=arquivo_csv,
            callback_progresso=callback_progresso, log_callback=self.log, start_index=self.start_index_ncm
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