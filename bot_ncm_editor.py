import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

class BotNCMEditor:
    
    URL_LISTAGEM_PRODUTOS = "https://sistema.sischef.com/admin/produtos/produtoList.jsf"
    URL_EDICAO_PRODUTO = "https://sistema.sischef.com/admin/produtos/produto.jsf"
    
    ID_CAMPO_BUSCA = "_input-busca-generica_" 
    ID_CAMPO_NCM = "tabSessoesProduto:ncm" 
    
    SELECTOR_BOTAO_EDITAR = "//a[contains(text(), 'Editar') and contains(@class, 'btn')]" 
    SELECTOR_ERRO_GLOBAL = "//div[contains(@class, 'ui-growl-item-container') and contains(@class, 'ui-state-error')]"

    def __init__(self, driver, csv_path, callback_progresso):
        self.driver = driver
        self.csv_path = csv_path
        self.callback_progresso = callback_progresso
        self.wait = WebDriverWait(self.driver, 10) # Wait padrão de 10s
        
        if not self.driver:
            raise ValueError("O BotNCMEditor precisa de um 'driver' do Selenium ativo.")
        if not self.csv_path:
            raise ValueError("O BotNCMEditor precisa de um 'csv_path'.")
 
    def editar_ncm(self):
        """
        Inicia o processo de edição de NCM, lendo o CSV e iterando sobre os produtos.
        """
        try:
            df = pd.read_csv(self.csv_path, dtype=str) # Lê tudo como string
            
            if df.empty or len(df.columns) < 2:
                 raise ValueError("CSV inválido. O arquivo deve ter pelo menos 2 colunas: ID (1ª) e NCM (2ª).") 
                 
            df.columns = ['ID', 'NCM_NOVO'] + list(df.columns[2:])
                 
            total_produtos = len(df)
            produtos_atualizados = 0
            
            self._navegar_para_listagem()
            
            for index, row in df.iterrows():
                id_produto = str(row['ID']).strip()
                ncm_novo = str(row['NCM_NOVO']).strip()
                
                # Pula linhas onde o NCM_NOVO está vazio
                if not ncm_novo:
                    print(f"⚠️ NCM vazio para o ID {id_produto}. Pulando linha {index + 1}.")
                    continue
                
                print(f"\n⚙️ Processando ID: {id_produto} | Novo NCM: {ncm_novo}")
                
                self._buscar_produto_por_id(id_produto)
                self._clicar_em_editar(id_produto)
                self._atualizar_ncm_e_salvar(id_produto, ncm_novo)
                
                produtos_atualizados += 1
                
                log_msg_ncm = f"✅ NCM do ID {id_produto} atualizado para {ncm_novo}."
                print(log_msg_ncm)
                
                if self.callback_progresso:
                    # Passa a mensagem como o terceiro argumento
                    self.callback_progresso(produtos_atualizados, total_produtos, log_msg_ncm)
                
                time.sleep(1) # Delay

            print("✅ Edição de NCM de todos os produtos concluída!")
            return True

        except Exception as e:
            # Envia a mensagem de erro final para o log da GUI
            if self.callback_progresso:
                self.callback_progresso(produtos_atualizados, total_produtos, f"❌ ERRO FATAL: {e}")
            raise Exception(f"Erro no BotNCMEditor: {e}")
    
    def _navegar_para_listagem(self):
        """Acessa a URL da listagem de produtos e garante que a página carregou."""
        print(f"Navegando para: {self.URL_LISTAGEM_PRODUTOS}")
        self.driver.get(self.URL_LISTAGEM_PRODUTOS)
        
        try:
            self.wait.until(EC.url_to_be(self.URL_LISTAGEM_PRODUTOS))
            self.wait.until(EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA)))
            print("Página de listagem carregada.")
        except TimeoutException:
            raise Exception("Não foi possível carregar a página de listagem de produtos.")
        
    def _buscar_produto_por_id(self, id_produto):
        """Digita o ID do produto e pressiona ENTER no campo de busca."""
        print(f"Buscando produto ID: {id_produto}")
        
        campo_busca = self.wait.until(
            EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA))
        )
        
        campo_busca.send_keys(Keys.CONTROL, 'a') 
        campo_busca.send_keys(Keys.DELETE)     
        time.sleep(0.3) 
        
        campo_busca.send_keys(str(id_produto))
        time.sleep(0.5)
        campo_busca.send_keys(Keys.ENTER)
        
        time.sleep(1) # Espera Crítica para a busca terminar

    def _clicar_em_editar(self, id_produto):
        """Localiza e clica no botão 'Editar' após o resultado da busca."""
        print(f"Tentando clicar em 'Editar'...")
        time.sleep(1) 
        
        try:
            botao_editar = self.wait.until(
                EC.element_to_be_clickable((By.XPATH, self.SELECTOR_BOTAO_EDITAR))
            )
            botao_editar.click()
            
            # Espera a URL de edição carregar (pode ou não ter o ID)
            wait_url = WebDriverWait(self.driver, 10)
            wait_url.until(EC.url_contains("produto.jsf?id="))
            
            # Espera o campo de NCM para garantir que a tela de edição está pronta
            self.wait.until(
                EC.presence_of_element_located((By.ID, self.ID_CAMPO_NCM))
            )
            
            print(f"✅ Navegado para a tela de edição do produto ID {id_produto}.")
            
        except Exception as e:
            raise Exception(f"❌ Falha ao clicar em 'Editar' para o produto {id_produto}. Produto existe? Erro: {e}")

    def _atualizar_ncm_e_salvar(self, id_produto, ncm_novo):
        """Preenche o campo NCM, salva usando Alt + S e retorna para a lista."""
        try:
            print(f"✏️ Atualizando NCM para: {ncm_novo}")
            
            # 1. Localizar e preencher o campo NCM
            campo_ncm = self.wait.until(
                EC.presence_of_element_located((By.ID, self.ID_CAMPO_NCM))
            )
            
            campo_ncm.clear()
            time.sleep(0.5)
            campo_ncm.send_keys(ncm_novo)
            
            campo_ncm.send_keys(Keys.TAB) 
            time.sleep(1.5)
            
            # 2. Salvar usando Alt + S
            self.wait.until(
                EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao"))
            ).click()
            
            time.sleep(0.5)
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ALT, 's')
            time.sleep(2) 
            
            # 3. BLOCO DE VERIFICAÇÃO DE ERRO
            try:
                erro_container = WebDriverWait(self.driver, 3).until(
                    EC.presence_of_element_located((By.XPATH, self.SELECTOR_ERRO_GLOBAL))
                )
                
                erro_msg = "Mensagem de erro não capturada."
                try:
                    erro_msg = erro_container.find_element(By.TAG_NAME, 'p').text
                except:
                    pass
                    
                print(f"🚨 ERRO FATAL DETECTADO na edição do NCM para ID {id_produto}.")
                raise Exception(f"ERRO DE VALIDAÇÃO NCM: {erro_msg}. Processo pausado no ID: {id_produto}")
                
            except TimeoutException:
                pass # Sucesso
            
            # 4. VERIFICAÇÃO PÓS-SALVAMENTO E NAVEGAÇÃO
            try:
                WebDriverWait(self.driver, 1).until(
                    EC.url_to_be(self.URL_LISTAGEM_PRODUTOS)
                )
            except Exception:
                print("⚠️ Redirecionamento automático falhou. Navegando manualmente.")
                self.driver.get(self.URL_LISTAGEM_PRODUTOS)
                self.wait.until(EC.url_to_be(self.URL_LISTAGEM_PRODUTOS))

        except Exception as e:
            raise Exception(f"❌ Falha ao atualizar NCM ou salvar produto ID {id_produto}. Erro: {e}")