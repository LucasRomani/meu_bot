import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException # Importar para tratar o timeout
import time

class BotNCMEditor:
    
    URL_LISTAGEM_PRODUTOS = "https://sistema.sischef.com/admin/produtos/produtoList.jsf"
    URL_EDICAO_PRODUTO = "https://sistema.sischef.com/admin/produtos/produto.jsf"
    
    # ID do campo de busca na tela de listagem
    ID_CAMPO_BUSCA = "_input-busca-generica_" 
    # ID do campo NCM na tela de edição
    ID_CAMPO_NCM = "tabSessoesProduto:ncm" 
    
    # Seletor para o botão "Editar" na listagem
    SELECTOR_BOTAO_EDITAR = "//a[contains(text(), 'Editar') and contains(@class, 'btn')]" 
    
    # Seletor XPATH para a barra de notificação de ERRO (geralmente vermelha/amarela)
    SELECTOR_ERRO_GLOBAL = "//div[contains(@class, 'ui-growl-item-container') and contains(@class, 'ui-state-error')]"

    def __init__(self, driver, csv_path, callback_progresso):
        self.driver = driver
        self.csv_path = csv_path
        self.callback_progresso = callback_progresso
        
    def editar_ncm(self):
        # ... (Método editar_ncm mantido inalterado) ...
        """
        Inicia o processo de edição de NCM, lendo o CSV e iterando sobre os produtos.
        """
        try:
            df = pd.read_csv(self.csv_path)
            
            # 1. Preparação do DataFrame
            if df.empty or len(df.columns) < 2:
                 raise ValueError("CSV inválido. O arquivo deve ter pelo menos 2 colunas: ID (1ª) e NCM (2ª).") 
                 
            # Assume que a 1ª coluna é o ID e a 2ª é o novo NCM
            df.columns = ['ID', 'NCM_NOVO'] + list(df.columns[2:])
                 
            total_produtos = len(df)
            produtos_atualizados = 0
            
            # 2. Navegar para a tela de listagem
            self._navegar_para_listagem()
            
            # 3. Iterar sobre os produtos
            for index, row in df.iterrows():
                id_produto = str(row['ID']).strip()
                ncm_novo = str(row['NCM_NOVO']).strip()
                
                print(f"\n⚙️ Processando ID: {id_produto} | Novo NCM: {ncm_novo}")
                
                # a) Buscar o produto
                self._buscar_produto_por_id(id_produto)
                
                # b) Clicar em Editar e navegar para a tela de edição
                self._clicar_em_editar(id_produto)
                
                # c) ATUALIZAR NCM E SALVAR (Com verificação de erro)
                self._atualizar_ncm_e_salvar(id_produto, ncm_novo)
                
                # 4. Confirmação e loop
                produtos_atualizados += 1
                self.callback_progresso(produtos_atualizados, total_produtos, "NCMs Atualizados")
                
                # Pequeno delay antes da próxima iteração
                time.sleep(1) 

            print("✅ Edição de NCM de todos os produtos concluída!")
            return True

        except Exception as e:
            raise Exception(f"Erro no BotNCMEditor: {e}")

    # ... (Métodos _navegar_para_listagem, _buscar_produto_por_id, _clicar_em_editar mantidos inalterados) ...
    
    def _navegar_para_listagem(self):
        """
        Acessa a URL da listagem de produtos e garante que a página carregou.
        """
        print(f"Navegando para: {self.URL_LISTAGEM_PRODUTOS}")
        self.driver.get(self.URL_LISTAGEM_PRODUTOS)
        
        WebDriverWait(self.driver, 1).until(
            EC.url_to_be(self.URL_LISTAGEM_PRODUTOS)
        )
        
        WebDriverWait(self.driver, 1).until(
            EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA))
        )
        print("Página de listagem carregada.")
        
    def _buscar_produto_por_id(self, id_produto):
        """
        Digita o ID do produto e pressiona ENTER no campo de busca.
        """
        print(f"Buscando produto ID: {id_produto}")
        
        campo_busca = WebDriverWait(self.driver, 1).until(
            EC.visibility_of_element_located((By.ID, self.ID_CAMPO_BUSCA))
        )
        
        # Limpeza Robusta do Campo
        campo_busca.send_keys(Keys.CONTROL, 'a') 
        campo_busca.send_keys(Keys.DELETE)      
        time.sleep(0.3) 
        
        # Digitar o ID e pressionar ENTER
        campo_busca.send_keys(str(id_produto))
        time.sleep(0.5)
        campo_busca.send_keys(Keys.ENTER)
        
        # Espera Crítica para a busca terminar
        time.sleep(1) 

    def _clicar_em_editar(self, id_produto):
        """
        Localiza e clica no botão 'Editar' após o resultado da busca.
        """
        print(f"Tentando clicar em 'Editar'...")
        time.sleep(1) 
        
        try:
            botao_editar = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, self.SELECTOR_BOTAO_EDITAR))
            )
            
            botao_editar.click()
            
            # Espera a URL de edição carregar
            WebDriverWait(self.driver, 1).until(
                EC.url_contains(f"produto.jsf?id={id_produto}")
            )
            
            # Espera o campo de NCM para garantir que a tela de edição está pronta
            WebDriverWait(self.driver, 1).until(
                EC.presence_of_element_located((By.ID, self.ID_CAMPO_NCM))
            )
            
            print(f"✅ Navegado para a tela de edição do produto ID {id_produto}.")
            
        except Exception as e:
            raise Exception(f"❌ Falha ao clicar em 'Editar' para o produto {id_produto}. Erro: {e}")

    # =======================================================
    # MÉTODO ATUALIZADO COM VERIFICAÇÃO DE ERRO E PAUSA
    # =======================================================
    def _atualizar_ncm_e_salvar(self, id_produto, ncm_novo):
        """
        Preenche o campo NCM com o novo valor, salva usando Alt + S e retorna para a lista de produtos.
        """
        try:
            print(f"✏️ Atualizando NCM para: {ncm_novo}")
            
            # 1. Localizar e preencher o campo NCM
            campo_ncm = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, self.ID_CAMPO_NCM))
            )
            
            campo_ncm.clear()
            time.sleep(0.5)
            campo_ncm.send_keys(ncm_novo)
            
            # Dispara o evento de 'onchange' (PrimeFaces)
            campo_ncm.send_keys(Keys.TAB) 
            time.sleep(1.5) # Aumenta a espera para processamento JS
            
            # 2. Salvar usando Alt + S
            
            # Coloca o foco no campo de descrição para garantir que o atalho Alt+S funcione
            WebDriverWait(self.driver, 5).until(
                EC.presence_of_element_located((By.ID, "tabSessoesProduto:descricao"))
            ).click()
            
            time.sleep(0.5)
            
            # Envia o atalho ALT + S a partir do corpo da página
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ALT, 's')
            
            # Tempo para a mensagem de erro/sucesso aparecer
            time.sleep(2) 
            
            # =======================================================
            # BLOCO DE VERIFICAÇÃO DE ERRO E PAUSA (CRÍTICO)
            # =======================================================
            try:
                # Espera pelo elemento de erro por até 3 segundos
                erro_container = WebDriverWait(self.driver, 1).until(
                    EC.presence_of_element_located((By.XPATH, self.SELECTOR_ERRO_GLOBAL))
                )
                
                # Se o erro for encontrado:
                erro_msg = ""
                try:
                    erro_msg_elem = erro_container.find_element(By.TAG_NAME, 'p')
                    erro_msg = erro_msg_elem.text
                except:
                    erro_msg = "Mensagem de erro não capturada. Verifique o seletor."
                    
                print(f"🚨 ERRO FATAL DETECTADO na edição do NCM para ID {id_produto}.")
                print(f"Mensagem do SisChef: {erro_msg}")
                
                # Pausa a execução do bot
                raise Exception(f"ERRO DE VALIDAÇÃO NA EDIÇÃO NCM: {erro_msg}. Processo pausado no ID: {id_produto}")
                
            except TimeoutException:
                # Nenhuma mensagem de erro apareceu após 3s -> Sucesso (ou erro silencioso)
                pass 
            # =======================================================
            
            # 3. VERIFICAÇÃO PÓS-SALVAMENTO E NAVEGAÇÃO
            
            # Tenta esperar o redirecionamento automático
            try:
                WebDriverWait(self.driver, 0.5).until(
                    EC.url_to_be(self.URL_LISTAGEM_PRODUTOS)
                )
            except Exception:
                print("⚠️ Redirecionamento automático falhou ou demorou. Navegando manualmente para a lista.")
                # Força a navegação de volta para a lista
                self.driver.get(self.URL_LISTAGEM_PRODUTOS)
                WebDriverWait(self.driver, 10).until(
                    EC.url_to_be(self.URL_LISTAGEM_PRODUTOS)
                )
                
            print(f"✅ NCM do produto ID {id_produto} salvo com sucesso!")

        except Exception as e:
            # Captura o erro e relança-o para o método editar_ncm principal
            raise Exception(f"❌ Falha ao atualizar NCM ou salvar produto ID {id_produto}. Erro: {e}")