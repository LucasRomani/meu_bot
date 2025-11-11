import tkinter as tk
from tkinter import scrolledtext, filedialog
import threading
import time
import pandas as pd
# --- IMPORTAÇÕES ATUALIZADAS ---
from bot_sischef import BotSischef
from bot_qrpedir import BotQRPedir
# (O bot_ncm_editor é importado pelo bot_sischef)
# --- FIM DAS ATUALIZAÇÕES ---

# --- Variáveis Globais (Corrigidas) ---
bot_sischef = None 
bot_qrpedir = None
csv_path_sischef = None # 1. Para cadastro Sischef
csv_path_qrpedir = None # 2. Para cadastro QRPedir
csv_path_ncm = None     # 3. Para edição NCM
inicio_tempo = None
rodando = False # Lock para o Sischef
cadastro_qr_rodando = False # Lock para o QRPedir
produtos_cadastrados = 0
total_produtos = 0

# --- Funções ---
def log_msg(msg):
    """Adiciona uma mensagem ao 'log' da interface."""
    try:
        txt_log.configure(state='normal')
        txt_log.insert(tk.END, msg + "\n")
        txt_log.see(tk.END)
        txt_log.configure(state='disabled')
    except tk.TclError:
        pass # Janela pode ter sido fechada

# --- Funções do Sischef ---

def iniciar_bot_thread():
    threading.Thread(target=iniciar_bot, daemon=True).start()

def iniciar_bot():
    global bot_sischef
    usuario = entry_usuario.get().strip()
    senha = entry_senha.get().strip()
    if not usuario or not senha:
        log_msg("❌ Informe usuário e senha.")
        return
    log_msg(f"🔹 Iniciando bot SISCHEF com usuário: {usuario}")
    try:
        if bot_sischef:
            bot_sischef.fechar()
        bot_sischef = BotSischef(usuario, senha)
        bot_sischef.iniciar()
        log_msg("✅ Bot SISCHEF iniciado. Tela de cadastro carregada!")
    except Exception as e:
        log_msg(f"❌ Erro ao iniciar bot SISCHEF: {e}")

def iniciar_cadastro_thread():
    threading.Thread(target=iniciar_cadastro, daemon=True).start()

def iniciar_cadastro():
    global bot_sischef, csv_path_sischef, inicio_tempo, rodando, produtos_cadastrados
    if not bot_sischef:
        log_msg("❌ Bot Sischef não iniciado.")
        return
    if not csv_path_sischef:
        log_msg("❌ CSV de Cadastro Sischef não selecionado.")
        return

    log_msg("🔹 Iniciando cadastro de produtos (Sischef)...")
    produtos_cadastrados = 0
    atualizar_contador(0, 0, "Itens Sischef") # Define o label do contador
    rodando = True
    inicio_tempo = time.time()
    threading.Thread(target=atualizar_tempo, daemon=True).start()

    try:
        # Define o atributo correto no bot
        bot_sischef.arquivo_csv_cadastro = csv_path_sischef 
        
        bot_sischef.cadastrar_produtos(
            callback_progresso=lambda a, t, m: atualizar_contador(a, t, m), # Passa a msg
            callback_rodando=get_status_rodando
        )
        if get_status_rodando():
            log_msg("✅ Cadastro Sischef concluído!")
    except Exception as e:
        log_msg(f"❌ Erro durante cadastro Sischef: {e}")
    finally:
        rodando = False

def iniciar_edicao_ncm_thread():
    threading.Thread(target=iniciar_edicao_ncm, daemon=True).start()

def iniciar_edicao_ncm():
    global bot_sischef, csv_path_ncm, inicio_tempo, rodando, produtos_cadastrados
    if not bot_sischef:
        log_msg("❌ Bot Sischef não iniciado.")
        return
    if not csv_path_ncm: 
        log_msg("❌ Nenhum CSV de NCM selecionado.")
        return
    
    log_msg("🔹 Iniciando edição de NCM de produtos...")
    produtos_cadastrados = 0
    atualizar_contador(0, 0, "Itens NCM") # Define o label
    rodando = True
    inicio_tempo = time.time()
    log_msg("▶️ Status: RODANDO (EDIÇÃO NCM)")
    threading.Thread(target=atualizar_tempo, daemon=True).start()

    try:
        bot_sischef.editar_ncm(
            arquivo_csv=csv_path_ncm,
            callback_progresso=lambda a, t, m: atualizar_contador(a, t, m) # Passa a msg
        ) 
        log_msg("✅ Edição de NCM concluída!")
    except Exception as e:
        log_msg(f"❌ Erro fatal durante edição de NCM: {e}")
    finally:
        rodando = False
        log_msg("⏹️ Status: PARADO")

# --- Funções do QRPedir ---

def iniciar_bot_qrpedir_thread():
    threading.Thread(target=iniciar_bot_qrpedir, daemon=True).start()

def iniciar_bot_qrpedir():
    global bot_qrpedir
    usuario = entry_usuario.get().strip()
    senha = entry_senha.get().strip()
    if not usuario or not senha:
        log_msg("❌ Informe usuário e senha.")
        return
    log_msg(f"🔹 Iniciando bot QRPEDIR com usuário: {usuario}")
    try:
        if bot_qrpedir:
            bot_qrpedir.fechar()
        bot_qrpedir = BotQRPedir(usuario, senha)
        bot_qrpedir.iniciar()
        log_msg("✅ Bot QRPEDIR iniciado e logado!")
    except Exception as e:
        log_msg(f"❌ Erro ao iniciar bot QRPEDIR: {e}")

def iniciar_cadastro_qrpedir_thread():
    """ Inicia o cadastro QRPedir com lock (trava)."""
    global cadastro_qr_rodando, inicio_tempo
    if cadastro_qr_rodando:
        log_msg("⚠️ O cadastro QRPedir já está em andamento.")
        return
    
    cadastro_qr_rodando = True
    atualizar_contador(0, 0, "Itens QRPedir") # Define o label
    inicio_tempo = time.time()
    try:
        btn_iniciar_cadastro_qr.config(state='disabled', text="Cadastrando...")
    except (tk.TclError, NameError):
        log_msg("Erro: Não foi possível desabilitar o botão de cadastro.")
        cadastro_qr_rodando = False
        return
    threading.Thread(target=atualizar_tempo, daemon=True).start()
    threading.Thread(target=iniciar_cadastro_qrpedir, daemon=True).start()

def iniciar_cadastro_qrpedir():
    """Lê o CSV, agrupa (Nível 3) e chama o bot."""
    global bot_qrpedir, csv_path_qrpedir, cadastro_qr_rodando 
    
    if not bot_qrpedir:
        log_msg("❌ Bot QRPEDIR não iniciado.")
        cadastro_qr_rodando = False
        btn_iniciar_cadastro_qr.config(state='normal', text="Iniciar Cadastro QRPedir")
        return
    if not csv_path_qrpedir:
        log_msg("❌ CSV de Cadastro QRPedir não selecionado.")
        cadastro_qr_rodando = False
        btn_iniciar_cadastro_qr.config(state='normal', text="Iniciar Cadastro QRPedir")
        return
        
    try:
        dados = pd.read_csv(csv_path_qrpedir, dtype=str).fillna('') 
        log_msg(f"Iniciando cadastro no QRPedir. Total de LINHAS lidas: {len(dados)}")
        
        mapeamento = {
            "ColunaDoGrupo": "Grupo",
            "ColunaDoNomeDoProduto": "Nome",
            "ColunaDoCodigo": "CodigoExterno",
            "ColunaDoPreco": "Preco",
            "ColunaDaDescricaoOpcional": "Descricao",
            "ColunaComplemento_S_N": "PossuiComplemento",
            "descricao_complemento": "descricao_complemento", 
            "item_descricao": "item_descricao",
            "item_desc_comp": "item_desc_comp",
            "item_codigo": "item_codigo",
            "item_valor": "item_valor"
        }
        
        # Renomeia colunas, tratando minúsculas
        col_map = {col: nome for col, nome in mapeamento.items() if col in dados.columns}
        col_map_lower = {col.lower(): nome for col, nome in mapeamento.items() if col.lower() in dados.columns}
        col_map.update(col_map_lower) # Prioriza maiúsculas, aceita minúsculas
        dados_renomeados = dados.rename(columns=col_map)
        
        itens_para_cadastrar = []
        produto_atual = None
        grupo_complemento_atual = None

        for index, row in dados_renomeados.iterrows():
            nome_prod = str(row.get("Nome", "")).strip()
            nome_grup_comp = str(row.get("descricao_complemento", "")).strip()
            nome_item_comp = str(row.get("item_descricao", "")).strip()

            if nome_prod:
                if produto_atual:
                    itens_para_cadastrar.append(produto_atual)
                produto_atual = row.to_dict()
                produto_atual["grupos_complemento"] = []
                grupo_complemento_atual = None
            elif produto_atual and nome_grup_comp:
                grupo_complemento_atual = row.to_dict()
                grupo_complemento_atual["itens"] = []
                produto_atual["grupos_complemento"].append(grupo_complemento_atual)
            elif grupo_complemento_atual and nome_item_comp:
                item_atual = row.to_dict()
                grupo_complemento_atual["itens"].append(item_atual)
        if produto_atual:
            itens_para_cadastrar.append(produto_atual)
        
        log_msg(f"✅ Dados agrupados. Total de PRODUTOS a cadastrar: {len(itens_para_cadastrar)}")

        total = len(itens_para_cadastrar)
        for i, item_agrupado in enumerate(itens_para_cadastrar):
            if not cadastro_qr_rodando:
                log_msg("ℹ️ Cadastro QRPedir interrompido pelo usuário.")
                break
                
            log_msg_processando = f"🔹 Processando QRPedir {i+1}/{total}: {item_agrupado['Nome']}"
            log_msg(log_msg_processando)
            atualizar_contador(i, total, log_msg_processando) # Log antes
            
            bot_qrpedir.processar_item_cardapio(item_agrupado)
            
            log_msg_qr = f"✅ Produto QRPedir {i+1}/{total} ({item_agrupado['Nome']}) concluído."
            atualizar_contador(i + 1, total, log_msg_qr) # Log depois
            
        log_msg("✅ Cadastro no QRPedir concluído!")
        
    except Exception as e:
        log_msg(f"❌ Erro fatal durante o cadastro QRPedir: {e}")
    finally:
        cadastro_qr_rodando = False
        try:
            btn_iniciar_cadastro_qr.config(state='normal', text="Iniciar Cadastro QRPedir")
        except tk.TclError:
            pass

# --- Funções Gerais ---

def escolher_csv_sischef():
    global csv_path_sischef
    caminho = filedialog.askopenfilename(
        title="Selecione o CSV de CADASTRO (Sischef)",
        filetypes=[("Arquivos CSV", "*.csv")]
    )
    if caminho:
        csv_path_sischef = caminho
        log_msg(f"📄 CSV Sischef (Cadastro) selecionado: {caminho}")
    else:
        log_msg("❌ Nenhum arquivo selecionado.")

def escolher_csv_qrpedir():
    global csv_path_qrpedir
    caminho = filedialog.askopenfilename(
        title="Selecione o CSV de CADASTRO (QRPedir)",
        filetypes=[("Arquivos CSV", "*.csv")]
    )
    if caminho:
        csv_path_qrpedir = caminho
        log_msg(f"📄 CSV QRPedir (Cadastro) selecionado: {caminho}")
    else:
        log_msg("❌ Nenhum arquivo selecionado.")

def escolher_csv_ncm():
    global csv_path_ncm
    caminho = filedialog.askopenfilename(
        title="Selecione o arquivo CSV para Edição de NCM",
        filetypes=[("Arquivos CSV", "*.csv")]
    )
    if caminho:
        csv_path_ncm = caminho
        log_msg(f"📄 CSV de NCM selecionado: {caminho}")
    else:
        log_msg("❌ Nenhum arquivo CSV de NCM selecionado.")

def get_status_rodando():
    global rodando
    return rodando

def atualizar_contador(atual=0, total=0, label="Itens"):
    """Função de callback genérica para o contador E O LOG."""
    global produtos_cadastrados, total_produtos
    produtos_cadastrados = atual
    total_produtos = total
    
    label_texto = label if label != "Itens" else "Itens"
    if label_texto.startswith("🔹") or label_texto.startswith("✅"):
        # Se for uma mensagem de log, não mostra no contador
        label_texto = "Itens"
    
    try:
        lbl_contador.config(text=f"📦 {label_texto}: {atual}/{total}")
        
        # Adiciona a mensagem ao Log, se não for a mensagem padrão
        if label != "Itens":
            log_msg(label) # Envia a mensagem para o log
            
    except tk.TclError:
        pass

def atualizar_tempo():
    while rodando or cadastro_qr_rodando:
        try:
            tempo = int(time.time() - inicio_tempo)
            minutos, segundos = divmod(tempo, 60)
            lbl_tempo.config(text=f"⏱️ Tempo: {minutos:02d}:{segundos:02d}")
            time.sleep(1)
        except tk.TclError:
             break
    try:
        lbl_tempo.config(text="⏱️ Tempo: 00:00")
    except tk.TclError:
        pass

def fechar_bots():
    global bot_sischef, bot_qrpedir, rodando, cadastro_qr_rodando
    log_msg("ℹ️ Solicitando fechamento...")
    rodando = False
    cadastro_qr_rodando = False
    
    def fechar_em_thread():
        if bot_sischef:
            bot_sischef.fechar()
            log_msg("✅ Bot SISCHEF encerrado.")
        if bot_qrpedir:
            bot_qrpedir.fechar()
            log_msg("✅ Bot QRPEDIR encerrado.")
        if not bot_sischef and not bot_qrpedir:
            log_msg("ℹ️ Nenhum bot estava aberto.")
        
        globals()["bot_sischef"] = None
        globals()["bot_qrpedir"] = None
        
        try:
            btn_iniciar_cadastro_qr.config(state='normal', text="Iniciar Cadastro QRPedir")
            # (Adicione 'locks' para os outros botões)
        except Exception:
            pass

    threading.Thread(target=fechar_em_thread, daemon=True).start()

def ao_fechar_janela():
    fechar_bots()
    root.destroy()

# --- GUI (Layout Novo e Limpo) ---
root = tk.Tk()
root.title("Bot Sischef & QRPedir - Cadastro via CSV")
root.protocol("WM_DELETE_WINDOW", ao_fechar_janela)

# --- Frame de Status (Linha 0) ---
frame_status = tk.Frame(root)
frame_status.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
lbl_tempo = tk.Label(frame_status, text="⏱️ Tempo: 00:00", font=("Arial", 10, "bold"))
lbl_tempo.pack(side=tk.LEFT, padx=5)
lbl_contador = tk.Label(frame_status, text="📦 Itens: 0/0", font=("Arial", 10, "bold"))
lbl_contador.pack(side=tk.RIGHT, padx=5)

# --- Frame de Login (Linha 1) ---
frame_login = tk.LabelFrame(root, text="Login", padx=10, pady=10)
frame_login.grid(row=1, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
tk.Label(frame_login, text="Usuário:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entry_usuario = tk.Entry(frame_login, width=30)
entry_usuario.grid(row=0, column=1, padx=5, pady=5)
tk.Label(frame_login, text="Senha:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entry_senha = tk.Entry(frame_login, width=30, show="*")
entry_senha.grid(row=1, column=1, padx=5, pady=5)

# --- Frame de Ações (Linha 2) ---
frame_acoes = tk.Frame(root)
frame_acoes.grid(row=2, column=0, columnspan=3, padx=10, pady=5)

# Coluna 0: Sischef
frame_sischef = tk.LabelFrame(frame_acoes, text="Sischef", padx=10, pady=10)
frame_sischef.grid(row=0, column=0, padx=5, pady=5, sticky="ns")
tk.Button(frame_sischef, text="1. Iniciar Bot Sischef", command=iniciar_bot_thread, bg="green", fg="white", width=25).pack(pady=5)
tk.Button(frame_sischef, text="2. Escolher CSV (Cadastro)", command=escolher_csv_sischef, bg="blue", fg="white", width=25).pack(pady=5)
tk.Button(frame_sischef, text="3. Iniciar Cadastro Sischef", command=iniciar_cadastro_thread, bg="orange", fg="white", width=25).pack(pady=5)
tk.Button(frame_sischef, text="4. Escolher CSV (NCM)", command=escolher_csv_ncm, bg="gray", fg="white", width=25).pack(pady=(15, 5))
tk.Button(frame_sischef, text="5. Iniciar Edição NCM", command=iniciar_edicao_ncm_thread, bg="orange", fg="white", width=25).pack(pady=5)

# Coluna 1: QRPedir
frame_qrpedir = tk.LabelFrame(frame_acoes, text="QRPedir", padx=10, pady=10)
frame_qrpedir.grid(row=0, column=1, padx=5, pady=5, sticky="ns")
tk.Button(frame_qrpedir, text="1. Iniciar Bot QRPedir", command=iniciar_bot_qrpedir_thread, bg="#00AEEF", fg="white", width=25).pack(pady=5)
tk.Button(frame_qrpedir, text="2. Escolher CSV (Cadastro)", command=escolher_csv_qrpedir, bg="blue", fg="white", width=25).pack(pady=5)
btn_iniciar_cadastro_qr = tk.Button(frame_qrpedir, text="3. Iniciar Cadastro QRPedir", command=iniciar_cadastro_qrpedir_thread, bg="#00AEEF", fg="black", width=25)
btn_iniciar_cadastro_qr.pack(pady=5)

# Coluna 2: Global
frame_global = tk.LabelFrame(frame_acoes, text="Geral", padx=10, pady=10)
frame_global.grid(row=0, column=2, padx=5, pady=5, sticky="ns")
tk.Button(frame_global, text="Fechar Navegadores", command=fechar_bots, bg="red", fg="white", width=25).pack(pady=5)

# --- Frame de Log (Linha 3) ---
frame_log = tk.LabelFrame(root, text="Log de Atividades", padx=10, pady=10)
frame_log.grid(row=3, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
txt_log = scrolledtext.ScrolledText(frame_log, width=100, height=15, state='disabled', wrap=tk.WORD)
txt_log.pack(fill="both", expand=True)

root.grid_columnconfigure(0, weight=1)
frame_log.grid_columnconfigure(0, weight=1)

root.mainloop()