import time
import pandas as pd
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

class BotNCMEditor:
    def __init__(self, driver, csv_path, callback_progresso=None, log_callback=None, start_index=0):
        self.driver = driver
        self.csv_path = csv_path
        self.callback_progresso = callback_progresso
        self.log = log_callback if log_callback else print
        self.start_index = start_index

    def editar_ncm(self):
        try:
            df = pd.read_csv(self.csv_path, dtype=str).fillna('')
            total = len(df)
            wait = WebDriverWait(self.driver, 10)
            
            for i in range(self.start_index, total):
                row = df.iloc[i]
                vals = list(row.values)
                if len(vals) < 2:
                    continue
                    
                termo = str(vals[0]).strip()
                novo_ncm = str(vals[1]).strip()
                
                if self.callback_progresso:
                    self.callback_progresso(i + 1, total, f"🔍 Editando NCM: {termo}")
                
                try:
                    campo_busca = wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                    campo_busca.clear()
                    campo_busca.send_keys(termo)
                    time.sleep(0.5)
                    campo_busca.send_keys(Keys.ENTER)
                    time.sleep(2)
                    
                    try:
                        self.driver.find_element(By.XPATH, "//td[contains(text(), 'Nada encontrado')]")
                        self.log(f"⚠️ Produto '{termo}' não encontrado.")
                    except:
                        btn_edit = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn') and contains(., 'Editar')]")))
                        self.driver.execute_script("arguments[0].click();", btn_edit)
                        time.sleep(2)
                        
                        campo_ncm = wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:ncm")))
                        campo_ncm.click()
                        time.sleep(0.2)
                        campo_ncm.send_keys(Keys.CONTROL, "a")
                        time.sleep(0.1)
                        campo_ncm.send_keys(Keys.BACK_SPACE)
                        time.sleep(0.1)
                        campo_ncm.send_keys(novo_ncm)
                        time.sleep(0.5)
                        
                        self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                        ActionChains(self.driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                        time.sleep(2.0)
                        
                        self.log(f"✅ NCM do '{termo}' alterado para '{novo_ncm}'")
                        
                        try:
                            self.driver.execute_script("window.scrollTo(0, 0);")
                            time.sleep(0.5)
                            btn_list = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'produtoList.jsf') and contains(., 'Listagem')]")))
                            self.driver.execute_script("arguments[0].click();", btn_list)
                            wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                            time.sleep(1)
                        except Exception:
                            self.driver.back()
                            time.sleep(1)
                except Exception as e:
                    self.log(f"❌ Erro no item '{termo}': {e}")
                    
        except Exception as e:
            self.log(f"❌ Erro fatal na edição de NCM: {e}")