import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import requests # Adicionado para verificação de conexão

class BotNCMEditor:
    
    URL_LISTAGEM_PRODUTOS = "https://sistema.sischef.com/admin/produtos/produtoList.jsf"
    URL_EDICAO_PRODUTO = "https://sistema.sischef.com/admin/produtos/produto.jsf"
    ID_CAMPO_BUSCA = "_input-busca-generica_" 
    ID_CAMPO_NCM = "tabSessoesProduto:ncm" 
    SELECTOR_BOTAO_EDITAR = "//a[contains(text(), 'Editar') and contains(@class, 'btn')]" 
    SELECTOR_ERRO_GLOBAL = "//div[contains(@class, 'ui-growl-item-container') and contains(@class, 'ui-state-error')]"

    def __init__(self, driver, csv_path, callback_progresso, log_callback=None, start_index=0):
        self.driver = driver
        self.csv_path = csv_path
        self.callback_progresso = callback_progresso
        self.log = log_callback if log_callback else print
        self.start_index = start_index
        
        if not self.driver:
            raise ValueError("O BotNCMEditor precisa de um 'driver' do Selenium ativo.")
        if not self.csv_path:
            raise ValueError("O BotNCMEditor precisa de um 'csv_path'.")
            
        self.wait = WebDriverWait(self.driver, 10)

    def _verificar_conexao(self):
        """Verifica se há conexão ativa com a internet."""
        try:
            requests.get("http://www.google.com", timeout=5)
            return True
        except requests.exceptions.RequestException:
            return False

    def editar_ncm(self):
        self.log("▶️ Iniciando processo de edição de NCM...")
        
        try:
            df = pd.read_csv(self.csv_path, dtype=str).fillna('')
            
            if df.empty or len(df.columns) < 2:
                 raise ValueError("CSV inválido. O arquivo deve ter pelo menos 2 colunas: ID (1ª) e NCM (2ª).") 
                 
            # Renomeia com base na posição
            df.columns = ['ID', 'NCM_NOVO'] + list(df.columns[2:])
                 
            total_produtos = len(df)
            
            # 3. Iterar sobre os produtos (começando do start_index)
            self.log(f"▶️ Retomando edição de NCM do item {self.start_index + 1}...")
            for index in range(self.start_index, total_produtos):
                row = df.iloc[index]
                
                # (Lógica de verificação de conexão)
                if not self._verificar_conexao():
                    self.log("🚨 CONEXÃO PERDIDA. PAUSANDO...")
                    if self.callback_progresso:
                        self.callback_progresso(index, total_produtos, None)
                    while not self._verificar_conexao():
                        time.sleep(10) # Espera 10s
                    self.log("🟢 CONEXÃO RESTABELECIDA. RETOMANDO...")
                
                # 1. Navegar para a tela de listagem (a cada item, para garantir)
                self._navegar_para_listagem()
                
                id_produto = str(row['ID']).strip()
                ncm_novo = str(row['NCM_NOVO']).strip()
                
                log_msg_ncm = f"⚙️ Processando {index + 1}/{total_produtos}: ID {id_produto} | Novo NCM: {ncm_novo}"
                self.log(log_msg_ncm)
                if self.callback_progresso:
                    self.callback_progresso(index + 1, total_produtos, None) # Só contador
                
                try:
                    self._buscar_produto_por_id(id_produto)
                    self._clicar_em_editar(id_produto)
                    self._atualizar_ncm_e_salvar(id_produto, ncm_novo)
                    
                    log_msg_ncm = f"✅ NCM do ID {id_produto} atualizado para {ncm_novo}."
                    if self.callback_progresso:
                        self.callback_progresso(index + 1, total_produtos, log_msg_ncm)
                    
                    time.sleep(1) 

                except Exception as e:
                    # --- MODIFICADO: PULA O ITEM ---
                    log_msg_erro = f"❌ Falha ao processar ID {id_produto}: {e}"
                    self.log(log_msg_erro)
                    self.log(f"❌ ITEM PULADO: ID {id_produto} (Índice {index + 1})")
                    if self.callback_progresso:
                        self.callback_progresso(index + 1, total_produtos, log_msg_erro)
                    # Continua para o próximo item do loop 'for'

            self.log("✅ Edição de NCM de todos os produtos concluída!")
            return True

        except Exception as e:
            self.log(f"Erro fatal no BotNCMEditor: {e}")
            raise e # Lança o erro para a interface

    
    def _navegar_para_listagem(self):
        """Acessa a URL da listagem de produtos e garante que a página carregou."""
        try:
            current_url = self.driver.current_url
            if self.URL_LISTAGEM_PRODUTOS in current_url:
                # Já estamos na listagem, apenas verifica o campo
                self.wait.until(EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA)))
                return
        except Exception:
            pass # Se der erro na verificação de URL, só navega
            
        self.log(f"Navegando para: {self.URL_LISTAGEM_PRODUTOS}")
        self.driver.get(self.URL_LISTAGEM_PRODUTOS)
        
        try:
            self.wait.until(EC.url_to_be(self.URL_LISTAGEM_PRODUTOS))
            self.wait.until(EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA)))
        except Exception as e:
            self.log(f"⚠️ Falha ao carregar a página de listagem: {e}")
            raise Exception("Não foi possível carregar a página de listagem de produtos.")
        
    def _buscar_produto_por_id(self, id_produto):
        """Digita o ID do produto e pressiona ENTER no campo de busca."""
        self.log(f"Buscando produto ID: {id_produto}")
        
        campo_busca = self.wait.until(
            EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA))
        )
        
        campo_busca.send_keys(Keys.CONTROL, 'a') 
        campo_busca.send_keys(Keys.DELETE)      
        time.sleep(0.3) 
        
        campo_busca.send_keys(str(id_produto))
        time.sleep(0.5)
        campo_busca.send_keys(Keys.ENTER)
        
        time.sleep(1) # Espera a busca (AJAX) terminar

    def _clicar_em_editar(self, id_produto):
        """Localiza e clica no botão 'Editar' após o resultado da busca."""
        self.log(f"Tentando clicar em 'Editar'...")
        time.sleep(1) 
        
        try:
            botao_editar = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, self.SELECTOR_BOTAO_EDITAR))
            )
            botao_editar.click()
            
            # Espera a URL de edição carregar (o ID pode ou não estar na URL)
            self.wait.until(EC.url_contains("produto.jsf"))
            
            # Espera o campo de NCM
            self.wait.until(
                EC.presence_of_element_located((By.ID, self.ID_CAMPO_NCM))
            )
            self.log(f"✅ Navegado para a tela de edição do produto ID {id_produto}.")
            
        except Exception as e:
            raise Exception(f"❌ Falha ao clicar em 'Editar' para o produto {id_produto}. O produto existe? Erro: {e}")

    def _atualizar_ncm_e_salvar(self, id_produto, ncm_novo):
        """Preenche o campo NCM, salva (Alt+S) e verifica erros."""
        try:
            self.log(f"✏️ Atualizando NCM para: {ncm_novo}")
            
            campo_ncm = self.wait.until(
                EC.presence_of_element_located((By.ID, self.ID_CAMPO_NCM))
            )
            
            campo_ncm.clear()
            time.sleep(0.5)
            campo_ncm.send_keys(ncm_novo)
            
            campo_ncm.send_keys(Keys.TAB) 
            time.sleep(1.5)
            
            # Foco no campo descrição para Alt+S
            self.wait.until(
                EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao"))
            ).click()
            time.sleep(0.5)
            
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ALT, 's')
            
            time.sleep(2) # Espera mensagem de erro/sucesso
            
            try:
                erro_container = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.XPATH, self.SELECTOR_ERRO_GLOBAL))
                )
                
                erro_msg = ""
                try:
                    erro_msg_elem = erro_container.find_element(By.TAG_NAME, 'p')
                    erro_msg = erro_msg_elem.text
                except:
                    erro_msg = "Mensagem de erro não capturada."
                    
                self.log(f"🚨 ERRO FATAL DETECTADO na edição do NCM para ID {id_produto}.")
                self.log(f"Mensagem do SisChef: {erro_msg}")
                raise Exception(f"ERRO DE VALIDAÇÃO NA EDIÇÃO NCM: {erro_msg}. Processo pausado no ID: {id_produto}")
                
            except TimeoutException:
                pass # Sem erro, sucesso
            
            # Verificação Pós-Salvamento
            try:
                # Espera o redirecionamento
                self.wait.until(
                    EC.url_to_be(self.URL_LISTAGEM_PRODUTOS)
                )
            except Exception:
                self.log("⚠️ Redirecionamento automático falhou. Navegando manualmente para a lista.")
                self.driver.get(self.URL_LISTAGEM_PRODUTOS)
                self.wait.until(
                    EC.url_to_be(self.URL_LISTAGEM_PRODUTOS)
                )
                
            self.log(f"✅ NCM do produto ID {id_produto} salvo com sucesso!")

        except Exception as e:
            raise Exception(f"❌ Falha ao atualizar NCM ou salvar produto ID {id_produto}. Erro: {e}")