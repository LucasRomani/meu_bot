import tkinter as tk
from tkinter import scrolledtext, filedialog
import threading
import time
import pandas as pd
from bot_sischef import BotSischef
from bot_qrpedir import BotQRPedir
# (O bot_ncm_editor é importado pelo bot_sischef)

# --- Variáveis Globais (com progresso) ---
bot_sischef = None 
bot_qrpedir = None
csv_path_sischef = None
csv_path_qrpedir = None
csv_path_ncm = None
inicio_tempo = None
rodando = False # Lock para o Sischef (Cadastro ou NCM)
cadastro_qr_rodando = False # Lock para o QRPedir

# --- Variáveis de Progresso ---
ultimo_indice_sischef = 0
ultimo_indice_ncm = 0
ultimo_indice_qrpedir = 0
# --- FIM ---

# --- Funções ---
def log_msg(msg):
    """Adiciona uma mensagem ao 'log' da interface."""
    try:
        txt_log.configure(state='normal')
        txt_log.insert(tk.END, f"{time.strftime('%H:%M:%S')} - {msg}\n")
        txt_log.see(tk.END)
        txt_log.configure(state='disabled')
    except tk.TclError:
        pass 

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
    log_msg(f"🔹 Iniciando bot SISCHEF...")
    try:
        if bot_sischef:
            bot_sischef.fechar()
        bot_sischef = BotSischef(usuario, senha, log_callback=log_msg) 
        bot_sischef.iniciar()
        log_msg("✅ Bot SISCHEF iniciado. Tela de cadastro carregada!")
    except Exception as e:
        log_msg(f"❌ Erro ao iniciar bot SISCHEF: {e}")

def iniciar_cadastro_thread():
    """Modificado para desabilitar o botão"""
    global rodando
    if rodando:
        log_msg("⚠️ Um processo Sischef (NCM ou Cadastro) já está em andamento.")
        return
        
    rodando = True
    btn_iniciar_cadastro_sischef.config(state='disabled', text="Cadastrando...")
    btn_iniciar_ncm.config(state='disabled') # Desabilita o outro botão
    threading.Thread(target=iniciar_cadastro, daemon=True).start()

def iniciar_cadastro():
    global bot_sischef, csv_path_sischef, inicio_tempo, rodando, ultimo_indice_sischef
    if not bot_sischef:
        log_msg("❌ Bot Sischef não iniciado.")
        rodando = False
        btn_iniciar_cadastro_sischef.config(state='normal', text="3. Iniciar Cadastro Sischef")
        btn_iniciar_ncm.config(state='normal')
        return
    if not csv_path_sischef:
        log_msg("❌ CSV de Cadastro Sischef não selecionado.")
        rodando = False
        btn_iniciar_cadastro_sischef.config(state='normal', text="3. Iniciar Cadastro Sischef")
        btn_iniciar_ncm.config(state='normal')
        return

    log_msg(f"🔹 Iniciando cadastro (Sischef) a partir do item {ultimo_indice_sischef + 1}...")
    atualizar_contador(ultimo_indice_sischef, 0, 'sischef')
    inicio_tempo = time.time()
    threading.Thread(target=atualizar_tempo, daemon=True).start()

    try:
        bot_sischef.arquivo_csv_cadastro = csv_path_sischef 
        bot_sischef.start_index = ultimo_indice_sischef # Passa o índice inicial
        
        bot_sischef.cadastrar_produtos(
            callback_progresso=lambda a, t, msg: atualizar_contador(a, t, 'sischef', msg),
            callback_rodando=get_status_rodando
        )
        if get_status_rodando(): # Se 'rodando' ainda for True, ele completou
            log_msg("✅ Cadastro Sischef concluído!")
            log_msg(f"⏱️ Tempo total: {obter_tempo_decorrido_str()}")
            ultimo_indice_sischef = 0 # Reseta o índice se completou
    except Exception as e:
        log_msg(f"❌ Erro durante cadastro Sischef: {e}")
        log_msg(f"ℹ️ Processo pausado. Para retomar, clique em 'Iniciar Cadastro' novamente.")
    finally:
        rodando = False
        btn_iniciar_cadastro_sischef.config(state='normal', text="3. Iniciar Cadastro Sischef")
        btn_iniciar_ncm.config(state='normal')

def iniciar_edicao_ncm_thread():
    global rodando
    if rodando:
        log_msg("⚠️ Um processo Sischef (NCM ou Cadastro) já está em andamento.")
        return
        
    rodando = True
    btn_iniciar_ncm.config(state='disabled', text="Editando NCM...")
    btn_iniciar_cadastro_sischef.config(state='disabled') # Desabilita o outro
    threading.Thread(target=iniciar_edicao_ncm, daemon=True).start()

def iniciar_edicao_ncm():
    global bot_sischef, csv_path_ncm, inicio_tempo, rodando, ultimo_indice_ncm
    if not bot_sischef:
        log_msg("❌ Bot Sischef não iniciado.")
        rodando = False
        btn_iniciar_ncm.config(state='normal', text="5. Iniciar Edição NCM")
        btn_iniciar_cadastro_sischef.config(state='normal')
        return
    if not csv_path_ncm: 
        log_msg("❌ Nenhum CSV de NCM selecionado.")
        rodando = False
        btn_iniciar_ncm.config(state='normal', text="5. Iniciar Edição NCM")
        btn_iniciar_cadastro_sischef.config(state='normal')
        return
    
    log_msg(f"🔹 Iniciando edição de NCM a partir do item {ultimo_indice_ncm + 1}...")
    atualizar_contador(ultimo_indice_ncm, 0, 'ncm')
    inicio_tempo = time.time()
    log_msg("▶️ Status: RODANDO (EDIÇÃO NCM)")
    threading.Thread(target=atualizar_tempo, daemon=True).start()

    try:
        bot_sischef.start_index_ncm = ultimo_indice_ncm # Passa o índice inicial
        
        bot_sischef.editar_ncm(
            arquivo_csv=csv_path_ncm,
            callback_progresso=lambda a, t, msg: atualizar_contador(a, t, 'ncm', msg)
        ) 
        if get_status_rodando():
            log_msg("✅ Edição de NCM concluída!")
            log_msg(f"⏱️ Tempo total: {obter_tempo_decorrido_str()}")
            ultimo_indice_ncm = 0 # Reseta
    except Exception as e:
        log_msg(f"❌ Erro fatal durante edição de NCM: {e}")
        log_msg(f"ℹ️ Processo pausado. Para retomar, clique em 'Iniciar Edição NCM' novamente.")
    finally:
        rodando = False
        log_msg("⏹️ Status: PARADO")
        btn_iniciar_ncm.config(state='normal', text="5. Iniciar Edição NCM")
        btn_iniciar_cadastro_sischef.config(state='normal')

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
    log_msg(f"🔹 Iniciando bot QRPEDIR...")
    try:
        if bot_qrpedir:
            bot_qrpedir.fechar()
        bot_qrpedir = BotQRPedir(usuario, senha, log_callback=log_msg)
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
    atualizar_contador(ultimo_indice_qrpedir, 0, 'qrpedir')
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
    global bot_qrpedir, csv_path_qrpedir, cadastro_qr_rodando, ultimo_indice_qrpedir
    
    if not bot_qrpedir:
        log_msg("❌ Bot QRPEDIR não iniciado.")
        cadastro_qr_rodando = False
        btn_iniciar_cadastro_qr.config(state='normal', text="3. Iniciar Cadastro QRPedir")
        return
    if not csv_path_qrpedir:
        log_msg("❌ CSV de Cadastro QRPedir não selecionado.")
        cadastro_qr_rodando = False
        btn_iniciar_cadastro_qr.config(state='normal', text="3. Iniciar Cadastro QRPedir")
        return
        
    try:
        dados = pd.read_csv(csv_path_qrpedir, dtype=str).fillna('') 
        log_msg(f"Iniciando cadastro no QRPedir. Total de LINHAS lidas: {len(dados)}")
        
        # (Mapeamento e Agrupamento - sem alterações)
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
        # Corrigido para insensibilidade de caixa
        dados.columns = [col.lower() for col in dados.columns]
        mapeamento_lower = {k.lower(): v for k, v in mapeamento.items()}
        dados_renomeados = dados.rename(columns=mapeamento_lower)
        
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
        
        total = len(itens_para_cadastrar)
        log_msg(f"✅ Dados agrupados. Total de PRODUTOS a cadastrar: {total}")

        log_msg(f"▶️ Retomando do item {ultimo_indice_qrpedir + 1}...")
        for i in range(ultimo_indice_qrpedir, total):
            item_agrupado = itens_para_cadastrar[i]
            
            if not cadastro_qr_rodando:
                log_msg("ℹ️ Cadastro QRPedir interrompido pelo usuário.")
                break
                
            log_msg_qr = f"--- Processando Produto {i + 1}/{total}: {item_agrupado['Nome']} ---"
            log_msg(log_msg_qr)
            atualizar_contador(i, total, 'qrpedir', log_msg_qr)
            
            try:
                bot_qrpedir.processar_item_cardapio(item_agrupado)
                # --- SALVA O PROGRESSO ---
                ultimo_indice_qrpedir = i + 1
                atualizar_contador(i + 1, total, 'qrpedir', f"✅ Produto {item_agrupado['Nome']} salvo.")
            except Exception as e:
                log_msg(f"❌ ERRO no produto {item_agrupado['Nome']}: {e}")
                log_msg(f"❌ ITEM PULADO: {item_agrupado['Nome']} (Índice {i + 1})")
                # Salva o progresso para pular este item na próxima vez
                ultimo_indice_qrpedir = i + 1 
                # Continua para o próximo item
                
        if ultimo_indice_qrpedir == total and cadastro_qr_rodando:
            log_msg("✅ Cadastro no QRPedir concluído!")
            log_msg(f"⏱️ Tempo total: {obter_tempo_decorrido_str()}")
            ultimo_indice_qrpedir = 0
        
    except Exception as e:
        log_msg(f"❌ Erro fatal durante o cadastro QRPedir: {e}")
        log_msg(f"ℹ️ Processo pausado no item {ultimo_indice_qrpedir + 1}. Para retomar, clique em 'Iniciar' novamente.")
    finally:
        cadastro_qr_rodando = False
        try:
            btn_iniciar_cadastro_qr.config(state='normal', text="3. Iniciar Cadastro QRPedir")
        except tk.TclError:
            pass

# --- Funções Gerais ---

def escolher_csv_sischef():
    global csv_path_sischef, ultimo_indice_sischef
    caminho = filedialog.askopenfilename(title="Selecione o CSV de CADASTRO (Sischef)", filetypes=[("Arquivos CSV", "*.csv")])
    if caminho:
        if caminho != csv_path_sischef:
            log_msg("ℹ️ Novo CSV Sischef selecionado. Progresso de retomada foi zerado.")
            ultimo_indice_sischef = 0
        csv_path_sischef = caminho
        log_msg(f"📄 CSV Sischef (Cadastro) selecionado.")
    else:
        log_msg("❌ Nenhum arquivo selecionado.")

def escolher_csv_qrpedir():
    global csv_path_qrpedir, ultimo_indice_qrpedir
    caminho = filedialog.askopenfilename(title="Selecione o CSV de CADASTRO (QRPedir)", filetypes=[("Arquivos CSV", "*.csv")])
    if caminho:
        if caminho != csv_path_qrpedir:
            log_msg("ℹ️ Novo CSV QRPedir selecionado. Progresso de retomada foi zerado.")
            ultimo_indice_qrpedir = 0
        csv_path_qrpedir = caminho
        log_msg(f"📄 CSV QRPedir (Cadastro) selecionado.")
    else:
        log_msg("❌ Nenhum arquivo selecionado.")

def escolher_csv_ncm():
    global csv_path_ncm, ultimo_indice_ncm
    caminho = filedialog.askopenfilename(title="Selecione o arquivo CSV para Edição de NCM", filetypes=[("Arquivos CSV", "*.csv")])
    if caminho:
        if caminho != csv_path_ncm:
            log_msg("ℹ️ Novo CSV NCM selecionado. Progresso de retomada foi zerado.")
            ultimo_indice_ncm = 0
        csv_path_ncm = caminho
        log_msg(f"📄 CSV de NCM selecionado.")
    else:
        log_msg("❌ Nenhum arquivo selecionado.")

def get_status_rodando():
    global rodando
    return rodando

def obter_tempo_decorrido_str():
    """Retorna o tempo decorrido formatado."""
    if not inicio_tempo:
        return "00:00"
    tempo = int(time.time() - inicio_tempo)
    minutos, segundos = divmod(tempo, 60)
    return f"{minutos:02d}:{segundos:02d}"

def atualizar_contador(atual=0, total=0, bot_type=None, log_msg_override=None):
    """Callback genérica para contador E SALVAR PROGRESSO."""
    global ultimo_indice_sischef, ultimo_indice_ncm
    
    if bot_type == 'sischef':
        ultimo_indice_sischef = atual
    elif bot_type == 'ncm':
        ultimo_indice_ncm = atual
    elif bot_type == 'qrpedir':
        pass # QRPedir é salvo no loop principal
        
    try:
        lbl_contador.config(text=f"📦 Itens: {atual}/{total}")
        if log_msg_override:
            log_msg(log_msg_override)
    except tk.TclError:
        pass

def atualizar_tempo():
    while rodando or cadastro_qr_rodando:
        try:
            lbl_tempo.config(text=f"⏱️ Tempo: {obter_tempo_decorrido_str()}")
            time.sleep(1)
        except tk.TclError:
             break
    try:
        lbl_tempo.config(text="⏱️ Tempo: 00:00")
    except tk.TclError:
        pass

def pausar_processos():
    """Para os loops dos bots e registra o tempo."""
    global rodando, cadastro_qr_rodando
    log_msg("⏸️ Solicitação de PAUSA recebida...")
    rodando = False
    cadastro_qr_rodando = False
    log_msg(f"⏱️ Processo pausado em: {obter_tempo_decorrido_str()}")
    
    try:
        btn_iniciar_cadastro_sischef.config(state='normal', text="3. Iniciar Cadastro Sischef")
        btn_iniciar_ncm.config(state='normal', text="5. Iniciar Edição NCM")
        btn_iniciar_cadastro_qr.config(state='normal', text="3. Iniciar Cadastro QRPedir")
    except tk.TclError:
        pass

def fechar_bots():
    global bot_sischef, bot_qrpedir, rodando, cadastro_qr_rodando
    log_msg("ℹ️ Solicitando fechamento...")
    pausar_processos() # Pausa os loops
    
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

    threading.Thread(target=fechar_em_thread, daemon=True).start()

def ao_fechar_janela():
    fechar_bots()
    root.destroy()

# --- GUI (Layout Novo e Limpo) ---
root = tk.Tk()
root.title("Bot Sischef & QRPedir - Cadastro via CSV")
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
entry_usuario = tk.Entry(frame_login, width=30)
entry_usuario.grid(row=0, column=1, padx=5, pady=5)
tk.Label(frame_login, text="Senha:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entry_senha = tk.Entry(frame_login, width=30, show="*")
entry_senha.grid(row=1, column=1, padx=5, pady=5)

frame_acoes = tk.Frame(root)
frame_acoes.grid(row=2, column=0, columnspan=3, padx=10, pady=5)

frame_sischef = tk.LabelFrame(frame_acoes, text="Sischef", padx=10, pady=10)
frame_sischef.grid(row=0, column=0, padx=5, pady=5, sticky="ns")
tk.Button(frame_sischef, text="1. Iniciar Bot Sischef", command=iniciar_bot_thread, bg="green", fg="white", width=25).pack(pady=5)
tk.Button(frame_sischef, text="2. Escolher CSV (Cadastro)", command=escolher_csv_sischef, bg="blue", fg="white", width=25).pack(pady=5)
btn_iniciar_cadastro_sischef = tk.Button(frame_sischef, text="3. Iniciar Cadastro Sischef", command=iniciar_cadastro_thread, bg="orange", fg="white", width=25)
btn_iniciar_cadastro_sischef.pack(pady=5)
tk.Button(frame_sischef, text="4. Escolher CSV (NCM)", command=escolher_csv_ncm, bg="gray", fg="white", width=25).pack(pady=(15, 5))
btn_iniciar_ncm = tk.Button(frame_sischef, text="5. Iniciar Edição NCM", command=iniciar_edicao_ncm_thread, bg="orange", fg="white", width=25)
btn_iniciar_ncm.pack(pady=5)

frame_qrpedir = tk.LabelFrame(frame_acoes, text="QRPedir", padx=10, pady=10)
frame_qrpedir.grid(row=0, column=1, padx=5, pady=5, sticky="ns")
tk.Button(frame_qrpedir, text="1. Iniciar Bot QRPedir", command=iniciar_bot_qrpedir_thread, bg="#00AEEF", fg="white", width=25).pack(pady=5)
tk.Button(frame_qrpedir, text="2. Escolher CSV (Cadastro)", command=escolher_csv_qrpedir, bg="blue", fg="white", width=25).pack(pady=5)
btn_iniciar_cadastro_qr = tk.Button(frame_qrpedir, text="3. Iniciar Cadastro QRPedir", command=iniciar_cadastro_qrpedir_thread, bg="#00AEEF", fg="black", width=25)
btn_iniciar_cadastro_qr.pack(pady=5)

frame_global = tk.LabelFrame(frame_acoes, text="Geral", padx=10, pady=10)
frame_global.grid(row=0, column=2, padx=5, pady=5, sticky="ns")
tk.Button(frame_global, text="Pausar Processos", command=pausar_processos, bg="yellow", fg="black", width=25).pack(pady=5)
tk.Button(frame_global, text="Fechar Navegadores", command=fechar_bots, bg="red", fg="white", width=25).pack(pady=(15, 5))

frame_log = tk.LabelFrame(root, text="Log de Atividades", padx=10, pady=10)
frame_log.grid(row=3, column=0, columnspan=3, padx=10, pady=10, sticky="ew")
txt_log = scrolledtext.ScrolledText(frame_log, width=100, height=15, state='disabled', wrap=tk.WORD)
txt_log.pack(fill="both", expand=True)

root.grid_columnconfigure(0, weight=1)
frame_log.grid_columnconfigure(0, weight=1)

root.mainloop()