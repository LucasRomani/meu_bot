import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import threading
import time
import pandas as pd
import os
import re
import unicodedata
from bot_sischef import BotSischef
from bot_qrpedir import BotQRPedir
# Importações do Selenium
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains 

# --- Variáveis Globais ---
bot_sischef = None 
bot_qrpedir = None

# Variáveis de Arquivo
csv_path_sischef = None 
csv_path_qrpedir = None
csv_path_receitas = None

inicio_tempo = None
rodando = False 
cadastro_qr_rodando = False
pausado = False 

# --- Variáveis de Progresso ---
ultimo_indice_sischef = 0
ultimo_indice_ncm = 0
ultimo_indice_tributacao = 0 
ultimo_indice_codbarras = 0
ultimo_indice_precovenda = 0 
ultimo_indice_qrpedir = 0
ultimo_indice_receitas = 0
ultimo_indice_ficha_tecnica = 0

# --- Funções de Log ---
def log_msg(msg):
    try:
        txt_log.configure(state='normal')
        txt_log.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {msg}\n")
        txt_log.see(tk.END)
        txt_log.configure(state='disabled')
    except tk.TclError:
        pass 

def limpar_valor_monetario(valor):
    if not valor:
        return ""
    valor_limpo = str(valor).replace("R$", "").replace("$", "").strip()
    return valor_limpo

def toggle_pausa():
    global pausado
    if not rodando and not cadastro_qr_rodando:
        return
    
    pausado = not pausado
    if pausado:
        btn_pausar_retomar.config(text="▶️ Retomar", bg="green", fg="white")
        log_msg("⏸️ Processo PAUSADO. Clique em Retomar para continuar.")
    else:
        btn_pausar_retomar.config(text="⏸️ Pausar", bg="yellow", fg="black")
        log_msg("▶️ Processo RETOMADO.")

def verificar_pausa():
    global pausado, rodando, cadastro_qr_rodando
    while pausado:
        if not rodando and not cadastro_qr_rodando:
            break
        time.sleep(0.5)

# --- Funções do Sischef (Login/Iniciar) ---
def iniciar_bot_thread():
    threading.Thread(target=iniciar_bot, daemon=True).start()

def iniciar_bot():
    global bot_sischef
    usuario = entry_usuario.get().strip()
    senha = entry_senha.get().strip()
    if not usuario or not senha:
        log_msg("❌ Informe usuário e senha.")
        return
    log_msg(f"🔹 Iniciando bot SISCHEF...")
    try:
        if bot_sischef:
            bot_sischef.fechar()
        bot_sischef = BotSischef(usuario, senha, log_callback=log_msg) 
        bot_sischef.iniciar()
        log_msg("✅ Bot SISCHEF iniciado. Tela de cadastro carregada!")
    except Exception as e:
        log_msg(f"❌ Erro ao iniciar bot SISCHEF: {e}")

# --- 1. CADASTRO DE PRODUTOS ---
def iniciar_cadastro_thread():
    global rodando
    if rodando:
        log_msg("⚠️ Um processo Sischef já está em andamento.")
        return
    rodando = True
    bloquear_botoes_sischef()
    threading.Thread(target=iniciar_cadastro, daemon=True).start()

def iniciar_cadastro():
    global bot_sischef, csv_path_sischef, inicio_tempo, rodando, ultimo_indice_sischef
    if not bot_sischef:
        log_msg("❌ Bot Sischef não iniciado.")
        rodando = False; restaurar_botoes_sischef(); return
    if not csv_path_sischef:
        log_msg("❌ CSV Geral Sischef não selecionado.")
        rodando = False; restaurar_botoes_sischef(); return

    arquivo_para_bot = csv_path_sischef
    try:
        df = pd.read_csv(csv_path_sischef, dtype=str).fillna('')
        colunas_preco = [col for col in df.columns if any(x in col.lower() for x in ['preco', 'preço', 'custo', 'valor'])]
        if colunas_preco:
            for col in colunas_preco:
                df[col] = df[col].apply(limpar_valor_monetario)
            pasta_origem = os.path.dirname(csv_path_sischef)
            arquivo_limpo = os.path.join(pasta_origem, "temp_cadastro_sischef_limpo.csv")
            df.to_csv(arquivo_limpo, index=False)
            arquivo_para_bot = arquivo_limpo
            log_msg("ℹ️ CSV pré-processado (Cifras removidas).")
    except Exception as e:
        log_msg(f"⚠️ Falha pré-processamento: {e}")

    log_msg(f"🔹 Iniciando cadastro (Sischef) a partir do item {ultimo_indice_sischef + 1}...")
    atualizar_contador(ultimo_indice_sischef, 0, 'sischef')
    inicio_tempo = time.time()
    threading.Thread(target=atualizar_tempo, daemon=True).start()

    try:
        bot_sischef.arquivo_csv_cadastro = arquivo_para_bot 
        bot_sischef.start_index = ultimo_indice_sischef
        
        bot_sischef.cadastrar_produtos(
            callback_progresso=lambda a, t, msg: atualizar_contador(a, t, 'sischef', msg),
            callback_rodando=get_status_rodando 
        )
        if get_status_rodando():
            log_msg("✅ Cadastro Sischef concluído!")
            ultimo_indice_sischef = 0
    except Exception as e:
        log_msg(f"❌ Erro durante cadastro Sischef: {e}")
    finally:
        rodando = False
        restaurar_botoes_sischef()

# --- 2. EDIÇÃO DE NCM ---
def iniciar_edicao_ncm_thread():
    global rodando
    if rodando:
        log_msg("⚠️ Um processo Sischef já está em andamento.")
        return
    rodando = True
    bloquear_botoes_sischef()
    threading.Thread(target=iniciar_edicao_ncm, daemon=True).start()

def iniciar_edicao_ncm():
    global bot_sischef, csv_path_sischef, inicio_tempo, rodando, ultimo_indice_ncm
    if not bot_sischef:
        log_msg("❌ Bot Sischef não iniciado.")
        rodando = False; restaurar_botoes_sischef(); return
    if not csv_path_sischef: 
        log_msg("❌ CSV Geral Sischef não selecionado.")
        rodando = False; restaurar_botoes_sischef(); return
    
    log_msg(f"🔹 Iniciando edição de NCM a partir do item {ultimo_indice_ncm + 1}...")
    atualizar_contador(ultimo_indice_ncm, 0, 'ncm')
    inicio_tempo = time.time()
    threading.Thread(target=atualizar_tempo, daemon=True).start()

    try:
        bot_sischef.start_index_ncm = ultimo_indice_ncm
        bot_sischef.editar_ncm(
            arquivo_csv=csv_path_sischef,
            callback_progresso=lambda a, t, msg: atualizar_contador(a, t, 'ncm', msg)
        ) 
        if get_status_rodando():
            log_msg("✅ Edição de NCM concluída!")
            ultimo_indice_ncm = 0
    except Exception as e:
        log_msg(f"❌ Erro fatal durante edição de NCM: {e}")
    finally:
        rodando = False
        restaurar_botoes_sischef()

# --- 3. AJUSTE DE TRIBUTAÇÃO ---
def iniciar_tributacao_thread():
    global rodando
    if rodando:
        log_msg("⚠️ Um processo Sischef já está em andamento.")
        return
    rodando = True
    bloquear_botoes_sischef()
    threading.Thread(target=iniciar_tributacao, daemon=True).start()

def iniciar_tributacao():
    global bot_sischef, csv_path_sischef, inicio_tempo, rodando, ultimo_indice_tributacao
    if not bot_sischef or not bot_sischef.driver:
        log_msg("❌ Bot Sischef não iniciado."); rodando = False; restaurar_botoes_sischef(); return
    if not csv_path_sischef:
        log_msg("❌ CSV Geral Sischef não selecionado."); rodando = False; restaurar_botoes_sischef(); return

    produtos_nao_encontrados = []
    try:
        df = pd.read_csv(csv_path_sischef, dtype=str).fillna('')
        total = len(df)
        log_msg(f"🔹 Iniciando Ajuste de Tributação. Total: {total} itens.")
        inicio_tempo = time.time()
        threading.Thread(target=atualizar_tempo, daemon=True).start()
        wait = WebDriverWait(bot_sischef.driver, 10)

        for i in range(ultimo_indice_tributacao, total):
            verificar_pausa()
            if not rodando: log_msg("⏸️ Processo interrompido."); break
            row = df.iloc[i]
            try:
                vals = list(row.values)
                termo = str(vals[0]).strip()
                id_trib = str(vals[1]).strip() if len(vals) > 1 else ""
            except IndexError: log_msg("❌ Erro no CSV."); break
            
            atualizar_contador(i + 1, total, 'tributacao', f"🔍 Trib: {termo}")
            try:
                campo_busca = wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                campo_busca.clear(); campo_busca.send_keys(termo); time.sleep(0.5); campo_busca.send_keys(Keys.ENTER)
                time.sleep(2) 
                
                try:
                    bot_sischef.driver.find_element(By.XPATH, "//td[contains(text(), 'Nada encontrado')]")
                    log_msg(f"⚠️ '{termo}' não encontrado."); produtos_nao_encontrados.append(termo)
                except:
                    btn_edit = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn') and contains(., 'Editar')]")))
                    bot_sischef.driver.execute_script("arguments[0].click();", btn_edit)
                    time.sleep(2) 
                    
                    try:
                        tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Tributações (fiscais)')]")))
                        bot_sischef.driver.execute_script("arguments[0].click();", tab)
                        time.sleep(1.5)
                        
                        if id_trib:
                            cp_gp = wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:grupoTributario_input")))
                            cp_gp.click(); time.sleep(0.2); cp_gp.send_keys(Keys.CONTROL, "a"); cp_gp.send_keys(Keys.BACK_SPACE)
                            cp_gp.send_keys(id_trib); time.sleep(0.5); cp_gp.send_keys(Keys.ENTER)
                            time.sleep(1)
                            
                            bot_sischef.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            ActionChains(bot_sischef.driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                            time.sleep(2.5)
                            
                            try:
                                bot_sischef.driver.execute_script("window.scrollTo(0, 0);") 
                                time.sleep(0.5)
                                btn_list = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'produtoList.jsf') and contains(., 'Listagem')]")))
                                bot_sischef.driver.execute_script("arguments[0].click();", btn_list)
                                wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                                time.sleep(1)
                            except Exception as e_voltar:
                                log_msg(f"⚠️ Aviso: Botão Listagem falhou, forçando 'Back'. ({e_voltar})")
                                bot_sischef.driver.back()
                                time.sleep(1)
                        else:
                            bot_sischef.driver.back()
                    except Exception as e_in:
                        log_msg(f"❌ Erro interno Trib: {e_in}"); bot_sischef.driver.back()
            except Exception as e: log_msg(f"❌ Erro Trib '{termo}': {e}")
            ultimo_indice_tributacao = i + 1

        if produtos_nao_encontrados:
            p_csv = os.path.dirname(csv_path_sischef)
            c_log = os.path.join(p_csv, "nao_encontrados_tributacao.txt")
            with open(c_log, "w", encoding="utf-8") as f:
                for x in produtos_nao_encontrados: f.write(f"{x}\n")
            log_msg(f"📄 Log salvo: {c_log}")
            log_msg("⚠️ ITENS NÃO ENCONTRADOS (TRIBUTAÇÃO):")
            for item in produtos_nao_encontrados: log_msg(f" • {item}")

        if ultimo_indice_tributacao == total:
            tempo_final = obter_tempo_decorrido_str()
            log_msg(f"✅ Tributação finalizada! Tempo total: {tempo_final}")
            ultimo_indice_tributacao = 0

    except Exception as e: log_msg(f"❌ Erro crítico: {e}")
    finally: rodando = False; restaurar_botoes_sischef()

# --- 4. AJUSTE DE CÓDIGO DE BARRAS ---
def iniciar_codbarras_thread():
    global rodando
    if rodando:
        log_msg("⚠️ Um processo Sischef já está em andamento.")
        return
    rodando = True
    bloquear_botoes_sischef()
    threading.Thread(target=iniciar_ajuste_codbarras, daemon=True).start()

def iniciar_ajuste_codbarras():
    global bot_sischef, csv_path_sischef, inicio_tempo, rodando, ultimo_indice_codbarras
    if not bot_sischef or not bot_sischef.driver:
        log_msg("❌ Bot Sischef não iniciado."); rodando = False; restaurar_botoes_sischef(); return
    if not csv_path_sischef:
        log_msg("❌ CSV Geral Sischef não selecionado."); rodando = False; restaurar_botoes_sischef(); return

    produtos_nao_encontrados = []
    produtos_duplicados = []

    try:
        df = pd.read_csv(csv_path_sischef, dtype=str).fillna('')
        total = len(df)
        log_msg(f"🔹 Iniciando Ajuste Cód. Barras. Total: {total} itens.")
        inicio_tempo = time.time()
        threading.Thread(target=atualizar_tempo, daemon=True).start()
        wait = WebDriverWait(bot_sischef.driver, 10)

        for i in range(ultimo_indice_codbarras, total):
            verificar_pausa() 
            if not rodando: log_msg("⏸️ Interrompido."); break
            row = df.iloc[i]
            try:
                vals = list(row.values)
                termo = str(vals[0]).strip() 
                novo_cod_barras = str(vals[1]).strip() if len(vals) > 1 else ""
            except IndexError: log_msg("❌ Erro estrutura CSV."); break
            
            atualizar_contador(i + 1, total, 'codbarras', f"🔍 CB: {termo}")
            try:
                campo_busca = wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                campo_busca.clear(); campo_busca.send_keys(termo); time.sleep(0.5); campo_busca.send_keys(Keys.ENTER)
                time.sleep(2)
                
                try:
                    bot_sischef.driver.find_element(By.XPATH, "//td[contains(text(), 'Nada encontrado')]")
                    log_msg(f"⚠️ '{termo}' não encontrado."); produtos_nao_encontrados.append(termo)
                except:
                    btn_edit = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn') and contains(., 'Editar')]")))
                    bot_sischef.driver.execute_script("arguments[0].click();", btn_edit)
                    time.sleep(2)
                    
                    try:
                        campo_cb = wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:codigoBarras")))
                        campo_cb.click(); time.sleep(0.2)
                        campo_cb.send_keys(Keys.CONTROL, "a"); time.sleep(0.1)
                        campo_cb.send_keys(Keys.BACK_SPACE); time.sleep(0.1)
                        campo_cb.send_keys(novo_cod_barras)
                        time.sleep(0.5)
                        
                        bot_sischef.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                        ActionChains(bot_sischef.driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                        time.sleep(1.5)
                        
                        duplicado = False
                        try:
                            elementos_erro = bot_sischef.driver.find_elements(By.XPATH, "//*[contains(text(), 'Regra violada')]")
                            for elem in elementos_erro:
                                if elem.is_displayed():
                                    duplicado = True
                                    break
                            
                            if duplicado:
                                log_msg(f"⛔ DUPLICADO: '{termo}' -> CB: {novo_cod_barras}")
                                produtos_duplicados.append(f"{termo} - {novo_cod_barras}")
                                try:
                                    botoes_ok = bot_sischef.driver.find_elements(By.XPATH, "//*[contains(text(), 'Ok, obrigado')]")
                                    for btn in botoes_ok:
                                        if btn.is_displayed():
                                            bot_sischef.driver.execute_script("arguments[0].click();", btn)
                                            time.sleep(1)
                                            break
                                except: pass 
                        except Exception: pass 

                        if not duplicado:
                            log_msg(f"✅ CodBarras alterado: '{novo_cod_barras}'")
                            time.sleep(1) 
                        
                        try:
                            bot_sischef.driver.execute_script("window.scrollTo(0, 0);")
                            time.sleep(0.5)
                            btn_list = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'produtoList.jsf') and contains(., 'Listagem')]")))
                            bot_sischef.driver.execute_script("arguments[0].click();", btn_list)
                            wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                            time.sleep(1)
                        except Exception:
                            bot_sischef.driver.back()
                            time.sleep(1)
                        
                    except Exception as e_field:
                        log_msg(f"❌ Erro edição '{termo}': {e_field}")
                        bot_sischef.driver.back()
            except Exception as e: log_msg(f"❌ Erro geral '{termo}': {e}")
            ultimo_indice_codbarras = i + 1

        p_csv = os.path.dirname(csv_path_sischef)
        if produtos_nao_encontrados:
            c_log = os.path.join(p_csv, "nao_encontrados_codbarras.txt")
            with open(c_log, "w", encoding="utf-8") as f:
                for x in produtos_nao_encontrados: f.write(f"{x}\n")
            log_msg(f"📄 Log Não Encontrados salvo: {c_log}")
            log_msg("⚠️ ITENS NÃO ENCONTRADOS (COD BARRAS):")
            for item in produtos_nao_encontrados: log_msg(f" • {item}")

        if produtos_duplicados:
            c_log_dup = os.path.join(p_csv, "produtos_duplicados.txt")
            with open(c_log_dup, "w", encoding="utf-8") as f:
                for x in produtos_duplicados: f.write(f"{x}\n")
            log_msg(f"📄 Log Duplicados salvo: {c_log_dup}")

        if ultimo_indice_codbarras == total:
            tempo_final = obter_tempo_decorrido_str()
            log_msg(f"✅ Ajuste Cód. Barras finalizado! Tempo total: {tempo_final}"); ultimo_indice_codbarras = 0

    except Exception as e: log_msg(f"❌ Erro crítico CB: {e}")
    finally: rodando = False; restaurar_botoes_sischef()
# --- 5. AJUSTE DE PREÇO DE VENDA ---
def iniciar_precovenda_thread():
    global rodando
    if rodando:
        log_msg("⚠️ Um processo Sischef já está em andamento.")
        return
    rodando = True
    bloquear_botoes_sischef()
    threading.Thread(target=iniciar_ajuste_precovenda, daemon=True).start()

def iniciar_ajuste_precovenda():
    global bot_sischef, csv_path_sischef, inicio_tempo, rodando, ultimo_indice_precovenda
    if not bot_sischef or not bot_sischef.driver:
        log_msg("❌ Bot Sischef não iniciado."); rodando = False; restaurar_botoes_sischef(); return
    if not csv_path_sischef:
        log_msg("❌ CSV Geral Sischef não selecionado."); rodando = False; restaurar_botoes_sischef(); return

    produtos_nao_encontrados = []
    try:
        df = pd.read_csv(csv_path_sischef, dtype=str).fillna('')
        total = len(df)
        
        # --- LEITURA INTELIGENTE DE COLUNAS ---
        def limpar_coluna(nome):
            n = unicodedata.normalize('NFKD', str(nome)).encode('ASCII', 'ignore').decode('utf-8')
            return re.sub(r'[^a-zA-Z0-9]', '', n).lower()
            
        col_nome = None
        col_compra = None
        col_venda = None
        
        for col in df.columns:
            c_limpo = limpar_coluna(col)
            if c_limpo in ['nome', 'produto', 'descricao', 'item', 'codigo']:
                if not col_nome: col_nome = col
            elif c_limpo in ['precodecompra', 'precocompra', 'custo', 'valorcompra', 'compra', 'valorcusto']:
                col_compra = col
            elif c_limpo in ['precodevenda', 'precovenda', 'venda', 'valorvenda', 'preco']:
                col_venda = col
                
        # Fallback para as colunas 1, 2 e 3 caso não encontre pelos nomes reconhecidos
        todas_colunas = list(df.columns)
        if not col_nome and len(todas_colunas) > 0: col_nome = todas_colunas[0]
        if not col_compra and len(todas_colunas) > 1: col_compra = todas_colunas[1]
        if not col_venda and len(todas_colunas) > 2: col_venda = todas_colunas[2]
        
        log_msg(f"🔹 Ajuste de Preços ({total} itens).")
        log_msg(f"📌 Identificado: Produto='{col_nome}' | Compra='{col_compra}' | Venda='{col_venda}'")
        
        inicio_tempo = time.time()
        threading.Thread(target=atualizar_tempo, daemon=True).start()
        wait = WebDriverWait(bot_sischef.driver, 10)

        for i in range(ultimo_indice_precovenda, total):
            verificar_pausa() 
            if not rodando: log_msg("⏸️ Interrompido."); break
            row = df.iloc[i]
            try:
                # Agora o robô puxa com base no nome exato da coluna identificada
                termo = str(row[col_nome]).strip() if col_nome and col_nome in row else ""
                novo_preco_compra = str(row[col_compra]).strip() if col_compra and col_compra in row else ""
                novo_preco_venda = str(row[col_venda]).strip() if col_venda and col_venda in row else ""
                
                if novo_preco_compra.lower() in ['nan', 'null']: novo_preco_compra = ""
                if novo_preco_venda.lower() in ['nan', 'null']: novo_preco_venda = ""
                
                novo_preco_compra = limpar_valor_monetario(novo_preco_compra) 
                novo_preco_venda = limpar_valor_monetario(novo_preco_venda) 
            except Exception as e_csv: 
                log_msg(f"❌ Erro na leitura da linha CSV: {e_csv}"); break
            
            atualizar_contador(i + 1, total, 'precovenda', f"🔍 Produto: {termo}")
            try:
                campo_busca = wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                campo_busca.clear(); campo_busca.send_keys(termo); time.sleep(0.5); campo_busca.send_keys(Keys.ENTER)
                time.sleep(2)
                
                try:
                    bot_sischef.driver.find_element(By.XPATH, "//td[contains(text(), 'Nada encontrado')]")
                    log_msg(f"⚠️ '{termo}' não encontrado."); produtos_nao_encontrados.append(termo)
                except:
                    btn_edit = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn') and contains(., 'Editar')]")))
                    bot_sischef.driver.execute_script("arguments[0].click();", btn_edit)
                    time.sleep(2)
                    try:
                        # --- Ajuste Preço de COMPRA ---
                        if novo_preco_compra:
                            campo_compra = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id, 'tabSessoesProduto:valorUnitarioCompra') or contains(@id, 'precoCompra')]")))
                            campo_compra.click(); time.sleep(0.2)
                            campo_compra.send_keys(Keys.CONTROL, "a"); time.sleep(0.1)
                            campo_compra.send_keys(Keys.BACK_SPACE); time.sleep(0.1)
                            campo_compra.send_keys(novo_preco_compra)
                            time.sleep(0.5)

                        # --- Ajuste Preço de VENDA ---
                        if novo_preco_venda:
                            campo_venda = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id, 'tabSessoesProduto:valorUnitarioVenda') or contains(@id, 'precoVenda')]")))
                            campo_venda.click(); time.sleep(0.2)
                            campo_venda.send_keys(Keys.CONTROL, "a"); time.sleep(0.1)
                            campo_venda.send_keys(Keys.BACK_SPACE); time.sleep(0.1)
                            campo_venda.send_keys(novo_preco_venda)
                            time.sleep(0.5)
                        
                        bot_sischef.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                        ActionChains(bot_sischef.driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                        time.sleep(2.0)
                        
                        log_msg(f"✅ Preços salvos | Compra: {novo_preco_compra or 'N/A'} | Venda: {novo_preco_venda or 'N/A'}")
                        
                        try:
                            bot_sischef.driver.execute_script("window.scrollTo(0, 0);")
                            time.sleep(0.5)
                            btn_list = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'produtoList.jsf') and contains(., 'Listagem')]")))
                            bot_sischef.driver.execute_script("arguments[0].click();", btn_list)
                            wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                            time.sleep(1)
                        except Exception:
                            bot_sischef.driver.back(); time.sleep(1)
                    except Exception as e_field:
                        log_msg(f"❌ Erro ao editar preço '{termo}': {e_field}")
                        bot_sischef.driver.back()
            except Exception as e: log_msg(f"❌ Erro geral '{termo}': {e}")
            ultimo_indice_precovenda = i + 1

        p_csv = os.path.dirname(csv_path_sischef)
        if produtos_nao_encontrados:
            c_log = os.path.join(p_csv, "nao_encontrados_precovenda.txt")
            with open(c_log, "w", encoding="utf-8") as f:
                for x in produtos_nao_encontrados: f.write(f"{x}\n")
            log_msg(f"📄 Log Não Encontrados salvo: {c_log}")

        if ultimo_indice_precovenda == total:
            tempo_final = obter_tempo_decorrido_str()
            log_msg(f"✅ Ajuste de Preços finalizado! Tempo total: {tempo_final}"); ultimo_indice_precovenda = 0

    except Exception as e: log_msg(f"❌ Erro crítico Preço: {e}")
    finally: rodando = False; restaurar_botoes_sischef()

# --- 6. INICIAR RECEITAS (PRODUÇÃO) ---
def iniciar_cadastro_receitas_thread():
    global rodando
    if rodando:
        log_msg("⚠️ Um processo Sischef já está em andamento.")
        return
    rodando = True
    bloquear_botoes_sischef()
    threading.Thread(target=iniciar_cadastro_receitas, daemon=True).start()

def iniciar_cadastro_receitas():
    global bot_sischef, csv_path_receitas, inicio_tempo, rodando, ultimo_indice_receitas
    if not bot_sischef:
        log_msg("❌ Bot Sischef não iniciado.")
        rodando = False; restaurar_botoes_sischef(); return
    if not csv_path_receitas:
        log_msg("⚠️ Selecione um arquivo CSV de Receitas/Fichas primeiro!")
        rodando = False; restaurar_botoes_sischef(); return
        
    try:
        log_msg(f"🔹 Iniciando cadastro de Receitas a partir do item {ultimo_indice_receitas + 1}...")
        atualizar_contador(ultimo_indice_receitas, 0, 'receitas')
        inicio_tempo = time.time()
        threading.Thread(target=atualizar_tempo, daemon=True).start()
        
        bot_sischef.arquivo_csv_receitas = csv_path_receitas
        bot_sischef.start_index = ultimo_indice_receitas
        
        bot_sischef.cadastrar_receitas(
            callback_progresso=lambda a, t, msg: atualizar_contador(a, t, 'receitas', msg),
            callback_rodando=get_status_rodando
        )
        
        if get_status_rodando():
            tempo_final = obter_tempo_decorrido_str()
            log_msg(f"✅ Cadastro de Receitas concluído! Tempo total: {tempo_final}")
            ultimo_indice_receitas = 0
    except Exception as e:
        log_msg(f"❌ Erro Crítico nas Receitas: {str(e)}")
    finally:
        rodando = False; restaurar_botoes_sischef()

# --- 7. INICIAR FICHA TÉCNICA (PDV) ---
def iniciar_ficha_tecnica_thread():
    global rodando
    if rodando:
        log_msg("⚠️ Um processo Sischef já está em andamento.")
        return
    rodando = True
    bloquear_botoes_sischef()
    threading.Thread(target=iniciar_ficha_tecnica, daemon=True).start()

def iniciar_ficha_tecnica():
    global bot_sischef, csv_path_receitas, inicio_tempo, rodando, ultimo_indice_ficha_tecnica
    if not bot_sischef:
        log_msg("❌ Bot Sischef não iniciado.")
        rodando = False; restaurar_botoes_sischef(); return
    if not csv_path_receitas:
        log_msg("⚠️ Selecione um arquivo CSV de Receitas/Fichas primeiro!")
        rodando = False; restaurar_botoes_sischef(); return
        
    try:
        log_msg(f"🔹 Iniciando Ficha Técnica a partir do item {ultimo_indice_ficha_tecnica + 1}...")
        atualizar_contador(ultimo_indice_ficha_tecnica, 0, 'ficha_tecnica')
        inicio_tempo = time.time()
        threading.Thread(target=atualizar_tempo, daemon=True).start()
        
        bot_sischef.arquivo_csv_receitas = csv_path_receitas
        bot_sischef.start_index = ultimo_indice_ficha_tecnica
        
        bot_sischef.cadastrar_fichas_tecnicas(
            callback_progresso=lambda a, t, msg: atualizar_contador(a, t, 'ficha_tecnica', msg),
            callback_rodando=get_status_rodando
        )
        
        if get_status_rodando():
            tempo_final = obter_tempo_decorrido_str()
            log_msg(f"✅ Cadastro de Fichas Técnicas concluído! Tempo total: {tempo_final}")
            ultimo_indice_ficha_tecnica = 0
    except Exception as e:
        log_msg(f"❌ Erro Crítico nas Fichas: {str(e)}")
    finally:
        rodando = False; restaurar_botoes_sischef()

# --- Funções do QRPedir (Mantidas) ---
def iniciar_bot_qrpedir_thread():
    threading.Thread(target=iniciar_bot_qrpedir, daemon=True).start()

def iniciar_bot_qrpedir():
    global bot_qrpedir
    usuario = entry_usuario.get().strip()
    senha = entry_senha.get().strip()
    if not usuario or not senha:
        log_msg("❌ Informe usuário e senha.")
        return
    log_msg(f"🔹 Iniciando bot QRPEDIR...")
    try:
        if bot_qrpedir: bot_qrpedir.fechar()
        bot_qrpedir = BotQRPedir(usuario, senha, log_callback=log_msg)
        bot_qrpedir.iniciar()
        log_msg("✅ Bot QRPEDIR iniciado e logado!")
    except Exception as e:
        log_msg(f"❌ Erro ao iniciar bot QRPEDIR: {e}")

def iniciar_cadastro_qrpedir_thread():
    global cadastro_qr_rodando, inicio_tempo
    if cadastro_qr_rodando:
        log_msg("⚠️ O cadastro QRPedir já está em andamento.")
        return
    cadastro_qr_rodando = True
    atualizar_contador(ultimo_indice_qrpedir, 0, 'qrpedir')
    inicio_tempo = time.time()
    try: btn_iniciar_cadastro_qr.config(state='disabled', text="Cadastrando...")
    except: pass
    threading.Thread(target=atualizar_tempo, daemon=True).start()
    threading.Thread(target=iniciar_cadastro_qrpedir, daemon=True).start()

def iniciar_cadastro_qrpedir():
    global bot_qrpedir, csv_path_qrpedir, cadastro_qr_rodando, ultimo_indice_qrpedir
    if not bot_qrpedir: log_msg("❌ Bot QRPEDIR não iniciado."); cadastro_qr_rodando = False; btn_iniciar_cadastro_qr.config(state='normal', text="3. Iniciar Cadastro QRPedir"); return
    if not csv_path_qrpedir: log_msg("❌ CSV de Cadastro QRPedir não selecionado."); cadastro_qr_rodando = False; btn_iniciar_cadastro_qr.config(state='normal', text="3. Iniciar Cadastro QRPedir"); return
        
    try:
        dados = pd.read_csv(csv_path_qrpedir, dtype=str).fillna('') 
        log_msg(f"Iniciando cadastro no QRPedir. Total de LINHAS lidas: {len(dados)}")
        
        chaves_bot = {
            "colunadogrupo": "Grupo", "colunadonomedoproduto": "Nome", "colunadocodigo": "CodigoExterno",
            "colunadopreco": "Preco", "colunadadescricaoopcional": "Descricao", "colunacomplementosn": "PossuiComplemento",
            "descricaocomplemento": "descricao_complemento", "itemdescricao": "item_descricao", "itemdesccomp": "item_desc_comp",
            "itemcodigo": "item_codigo", "itemvalor": "item_valor", "itemunidade": "item_unidade", "itemminmax": "item_min_max",
            "min": "min", "max": "max", "ordem": "ordem"
        }
        
        df = dados.copy()
        df.columns = [c.lower().replace("_", "").replace(" ", "") for c in df.columns]
        novo_map = {}
        for col_csv in df.columns:
            if col_csv in chaves_bot: novo_map[col_csv] = chaves_bot[col_csv]
        df = df.rename(columns=novo_map)
        
        log_msg("... Analisando e agrupando dados (Lógica Flexível)...")
        itens_para_cadastrar = []
        produto_atual = None
        grupo_complemento_atual = None
        last_nome_prod = ""; last_nome_grupo = ""

        for index, row in df.iterrows():
            nome_prod = str(row.get("Nome", "")).strip()
            nome_grup_comp = str(row.get("descricao_complemento", "")).strip()
            nome_item_comp = str(row.get("item_descricao", "")).strip()

            if nome_prod and nome_prod != last_nome_prod:
                if produto_atual: itens_para_cadastrar.append(produto_atual)
                produto_atual = row.to_dict(); produto_atual["grupos_complemento"] = []; grupo_complemento_atual = None; last_nome_prod = nome_prod; last_nome_grupo = ""
            
            if nome_grup_comp and nome_grup_comp != last_nome_grupo:
                if produto_atual:
                    grupo_complemento_atual = row.to_dict(); grupo_complemento_atual["itens"] = []
                    if 'min' in row: grupo_complemento_atual['min'] = row['min']
                    if 'max' in row: grupo_complemento_atual['max'] = row['max']
                    if 'ordem' in row: grupo_complemento_atual['ordem'] = row['ordem']
                    produto_atual["grupos_complemento"].append(grupo_complemento_atual); last_nome_grupo = nome_grup_comp

            if nome_item_comp:
                if grupo_complemento_atual:
                    item_atual = row.to_dict(); grupo_complemento_atual["itens"].append(item_atual)
                elif produto_atual:
                     if produto_atual["grupos_complemento"]:
                         grupo_complemento_atual = produto_atual["grupos_complemento"][-1]; item_atual = row.to_dict(); grupo_complemento_atual["itens"].append(item_atual)
            
            if produto_atual:
                if "Preco" in produto_atual and produto_atual["Preco"]:
                    produto_atual["Preco"] = limpar_valor_monetario(produto_atual["Preco"])
                if grupo_complemento_atual and "itens" in grupo_complemento_atual:
                    for it in grupo_complemento_atual["itens"]:
                        if "item_valor" in it and it["item_valor"]:
                            it["item_valor"] = limpar_valor_monetario(it["item_valor"])

        if produto_atual: itens_para_cadastrar.append(produto_atual)
        
        total = len(itens_para_cadastrar)
        log_msg(f"✅ Dados agrupados. Total: {total}")
        
        for i in range(ultimo_indice_qrpedir, total):
            verificar_pausa()
            item_agrupado = itens_para_cadastrar[i]
            if not cadastro_qr_rodando: log_msg("ℹ️ Interrompido."); break
            log_msg_qr = f"--- Processando {i + 1}/{total}: {item_agrupado['Nome']} ---"
            atualizar_contador(i, total, 'qrpedir', log_msg_qr)
            try:
                bot_qrpedir.processar_item_cardapio(item_agrupado)
                ultimo_indice_qrpedir = i + 1 
                atualizar_contador(i + 1, total, 'qrpedir', f"✅ Produto {item_agrupado['Nome']} salvo.")
            except Exception as e:
                log_msg(f"❌ ERRO no produto {item_agrupado['Nome']}: {e}"); log_msg(f"❌ ITEM PULADO.")
                ultimo_indice_qrpedir = i + 1 
                
        if ultimo_indice_qrpedir == total and cadastro_qr_rodando: log_msg("✅ Cadastro concluído!"); ultimo_indice_qrpedir = 0 
        
    except Exception as e: log_msg(f"❌ Erro fatal QR: {e}")
    finally: cadastro_qr_rodando = False; btn_iniciar_cadastro_qr.config(state='normal', text="3. Iniciar Cadastro QRPedir")

# --- Funções Gerais de Seleção de Arquivo ---
def escolher_csv_sischef_unificado():
    global csv_path_sischef, ultimo_indice_sischef, ultimo_indice_ncm, ultimo_indice_tributacao, ultimo_indice_codbarras, ultimo_indice_precovenda
    caminho = filedialog.askopenfilename(title="CSV Geral Sischef", filetypes=[("CSV", "*.csv")])
    if caminho:
        csv_path_sischef = caminho
        ultimo_indice_sischef = 0
        ultimo_indice_ncm = 0
        ultimo_indice_tributacao = 0
        ultimo_indice_codbarras = 0
        ultimo_indice_precovenda = 0
        log_msg(f"📄 CSV Sischef Selecionado: {caminho}")

def escolher_csv_receitas():
    global csv_path_receitas, ultimo_indice_receitas, ultimo_indice_ficha_tecnica
    caminho = filedialog.askopenfilename(title="Selecione o CSV de Receitas/Fichas", filetypes=[("Arquivos CSV", "*.csv")])
    if caminho:
        csv_path_receitas = caminho
        ultimo_indice_receitas = 0
        ultimo_indice_ficha_tecnica = 0
        log_msg(f"📁 CSV de Receitas/Fichas selecionado: {caminho}")

def escolher_csv_qrpedir():
    global csv_path_qrpedir, ultimo_indice_qrpedir
    caminho = filedialog.askopenfilename(title="CSV Cadastro QRPedir", filetypes=[("CSV", "*.csv")])
    if caminho: csv_path_qrpedir = caminho; ultimo_indice_qrpedir = 0; log_msg(f"📄 CSV QRPedir: {caminho}")

def get_status_rodando():
    global rodando
    verificar_pausa() 
    return rodando

def obter_tempo_decorrido_str():
    if not inicio_tempo: return "00:00"
    tempo = int(time.time() - inicio_tempo)
    minutos, segundos = divmod(tempo, 60)
    return f"{minutos:02d}:{segundos:02d}"

def atualizar_contador(atual=0, total=0, bot_type=None, log_msg_override=None):
    global ultimo_indice_sischef, ultimo_indice_ncm, ultimo_indice_tributacao, ultimo_indice_codbarras, ultimo_indice_precovenda, ultimo_indice_receitas, ultimo_indice_ficha_tecnica
    if bot_type == 'sischef': ultimo_indice_sischef = atual
    elif bot_type == 'ncm': ultimo_indice_ncm = atual
    elif bot_type == 'tributacao': ultimo_indice_tributacao = atual
    elif bot_type == 'codbarras': ultimo_indice_codbarras = atual
    elif bot_type == 'precovenda': ultimo_indice_precovenda = atual
    elif bot_type == 'receitas': ultimo_indice_receitas = atual
    elif bot_type == 'ficha_tecnica': ultimo_indice_ficha_tecnica = atual
        
    try:
        lbl_contador.config(text=f"📦 Itens: {atual}/{total}")
        if log_msg_override: log_msg(log_msg_override)
    except: pass

def atualizar_tempo():
    while rodando or cadastro_qr_rodando:
        try: lbl_tempo.config(text=f"⏱️ Tempo: {obter_tempo_decorrido_str()}"); time.sleep(1)
        except: break
    try: lbl_tempo.config(text="⏱️ Tempo: 00:00")
    except: pass

def bloquear_botoes_sischef():
    btn_iniciar_cadastro_sischef.config(state='disabled')
    btn_iniciar_ncm.config(state='disabled')
    btn_iniciar_tributacao.config(state='disabled')
    btn_iniciar_codbarras.config(state='disabled')
    btn_iniciar_precovenda.config(state='disabled')
    btn_iniciar_receitas.config(state='disabled')
    btn_iniciar_ficha_tecnica.config(state='disabled')
    btn_pausar_retomar.config(state='normal', text="⏸️ Pausar", bg="yellow", fg="black")

def restaurar_botoes_sischef():
    global pausado
    pausado = False
    try:
        btn_iniciar_cadastro_sischef.config(state='normal')
        btn_iniciar_ncm.config(state='normal')
        btn_iniciar_tributacao.config(state='normal')
        btn_iniciar_codbarras.config(state='normal')
        btn_iniciar_precovenda.config(state='normal')
        btn_iniciar_receitas.config(state='normal')
        btn_iniciar_ficha_tecnica.config(state='normal')
        btn_pausar_retomar.config(state='disabled', text="⏸️ Pausar", bg="gray", fg="white")
    except: pass

def parar_processos():
    global rodando, cadastro_qr_rodando, pausado
    if not rodando and not cadastro_qr_rodando: log_msg("ℹ️ Nenhum processo em execução."); return
    log_msg("⏹️ Parando processos..."); rodando = False; cadastro_qr_rodando = False; pausado = False

def fechar_bots():
    global bot_sischef, bot_qrpedir, rodando, cadastro_qr_rodando
    parar_processos()
    def fechar_em_thread():
        if bot_sischef: bot_sischef.fechar()
        if bot_qrpedir: bot_qrpedir.fechar()
        globals()["bot_sischef"] = None; globals()["bot_qrpedir"] = None; log_msg("ℹ️ Bots fechados.")
    threading.Thread(target=fechar_em_thread, daemon=True).start()

def ao_fechar_janela(): fechar_bots(); root.destroy()

# --- GUI ---
root = tk.Tk()
root.title("Bot Sischef & QRPedir")
root.protocol("WM_DELETE_WINDOW", ao_fechar_janela)

frame_status = tk.Frame(root)
frame_status.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
lbl_tempo = tk.Label(frame_status, text="⏱️ Tempo: 00:00", font=("Arial", 10, "bold"))
lbl_tempo.pack(side=tk.LEFT, padx=5)
lbl_contador = tk.Label(frame_status, text="📦 Itens: 0/0", font=("Arial", 10, "bold"))
lbl_contador.pack(side=tk.RIGHT, padx=5)

frame_login = tk.LabelFrame(root, text="Login", padx=10, pady=10)
frame_login.grid(row=1, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
tk.Label(frame_login, text="Usuário:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entry_usuario = tk.Entry(frame_login, width=30); entry_usuario.grid(row=0, column=1, padx=5, pady=5)
tk.Label(frame_login, text="Senha:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entry_senha = tk.Entry(frame_login, width=30, show="*"); entry_senha.grid(row=1, column=1, padx=5, pady=5)

frame_acoes = tk.Frame(root)
frame_acoes.grid(row=2, column=0, columnspan=3, padx=10, pady=5)

# Sischef
frame_sischef = tk.LabelFrame(frame_acoes, text="Sischef", padx=10, pady=10)
frame_sischef.grid(row=0, column=0, padx=5, pady=5, sticky="ns")
tk.Button(frame_sischef, text="1. Iniciar Bot Sischef", command=iniciar_bot_thread, bg="green", fg="white", width=25).pack(pady=2)
tk.Button(frame_sischef, text="2. Escolher CSV (Geral)", command=escolher_csv_sischef_unificado, bg="blue", fg="white", width=25).pack(pady=2)

btn_iniciar_cadastro_sischef = tk.Button(frame_sischef, text="3. Iniciar Cadastro", command=iniciar_cadastro_thread, bg="orange", fg="white", width=25); btn_iniciar_cadastro_sischef.pack(pady=2)
btn_iniciar_ncm = tk.Button(frame_sischef, text="4. Iniciar Edição NCM", command=iniciar_edicao_ncm_thread, bg="orange", fg="white", width=25); btn_iniciar_ncm.pack(pady=2)
btn_iniciar_tributacao = tk.Button(frame_sischef, text="5. Iniciar Tributação", command=iniciar_tributacao_thread, bg="orange", fg="white", width=25); btn_iniciar_tributacao.pack(pady=2)
btn_iniciar_codbarras = tk.Button(frame_sischef, text="6. Iniciar Cód. Barras", command=iniciar_codbarras_thread, bg="orange", fg="white", width=25); btn_iniciar_codbarras.pack(pady=2)
btn_iniciar_precovenda = tk.Button(frame_sischef, text="7. Iniciar Preço Venda", command=iniciar_precovenda_thread, bg="orange", fg="white", width=25); btn_iniciar_precovenda.pack(pady=2)

# Sub-seção de Receitas/Fichas
tk.Button(frame_sischef, text="8. Escolher CSV (Receitas/Fichas)", command=escolher_csv_receitas, bg="purple", fg="white", width=25).pack(pady=2)
btn_iniciar_receitas = tk.Button(frame_sischef, text="9. Iniciar Receitas (Produção)", command=iniciar_cadastro_receitas_thread, bg="purple", fg="white", width=25)
btn_iniciar_receitas.pack(pady=2)
btn_iniciar_ficha_tecnica = tk.Button(frame_sischef, text="10. Iniciar Ficha Técnica (PDV)", command=iniciar_ficha_tecnica_thread, bg="purple", fg="white", width=25)
btn_iniciar_ficha_tecnica.pack(pady=2)

# QRPedir
frame_qrpedir = tk.LabelFrame(frame_acoes, text="QRPedir", padx=10, pady=10)
frame_qrpedir.grid(row=0, column=1, padx=5, pady=5, sticky="ns")
tk.Button(frame_qrpedir, text="1. Iniciar Bot QRPedir", command=iniciar_bot_qrpedir_thread, bg="#00AEEF", fg="white", width=25).pack(pady=5)
tk.Button(frame_qrpedir, text="2. Escolher CSV (Cadastro)", command=escolher_csv_qrpedir, bg="blue", fg="white", width=25).pack(pady=5)
btn_iniciar_cadastro_qr = tk.Button(frame_qrpedir, text="3. Iniciar Cadastro QRPedir", command=iniciar_cadastro_qrpedir_thread, bg="#00AEEF", fg="black", width=25); btn_iniciar_cadastro_qr.pack(pady=5)

# Geral
frame_global = tk.LabelFrame(frame_acoes, text="Geral", padx=10, pady=10)
frame_global.grid(row=0, column=2, padx=5, pady=5, sticky="ns")
tk.Button(frame_global, text="Parar Todos", command=parar_processos, bg="red", fg="white", width=25).pack(pady=5)
btn_pausar_retomar = tk.Button(frame_global, text="⏸️ Pausar", command=toggle_pausa, bg="gray", fg="white", width=25, state='disabled')
btn_pausar_retomar.pack(pady=5)
tk.Button(frame_global, text="Fechar Navegadores", command=fechar_bots, bg="black", fg="white", width=25).pack(pady=5)

frame_log = tk.LabelFrame(root, text="Log de Atividades", padx=10, pady=10)
frame_log.grid(row=3, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
txt_log = scrolledtext.ScrolledText(frame_log, width=100, height=15, state='disabled', wrap=tk.WORD); txt_log.pack(fill="both", expand=True)

root.grid_columnconfigure(0, weight=1)
frame_log.grid_columnconfigure(0, weight=1)

root.mainloop()