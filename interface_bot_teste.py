import tkinter as tk
from tkinter import scrolledtext, filedialog
import threading
import time
import pandas as pd
from bot_sischef_teste import BotSischef, BotQRPedir

# --- Variáveis Globais ---
bot_sischef = None 
bot_qrpedir = None
csv_file_path = None
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
            log_msg("... Fechando instância anterior do Sischef.")
            bot_sischef.fechar()
            
        bot_sischef = BotSischef(usuario, senha)
        bot_sischef.iniciar()
        log_msg("✅ Bot SISCHEF iniciado. Tela de cadastro carregada!")
    except Exception as e:
        log_msg(f"❌ Erro ao iniciar bot SISCHEF: {e}")

def iniciar_cadastro_thread():
    threading.Thread(target=iniciar_cadastro, daemon=True).start()

def iniciar_cadastro():
    global bot_sischef, csv_file_path, inicio_tempo, rodando, produtos_cadastrados
    if not bot_sischef:
        log_msg("❌ Bot Sischef não iniciado. Clique em 'Iniciar Bot'.")
        return
    if not csv_file_path:
        log_msg("❌ Nenhum CSV selecionado. Clique em 'Escolher CSV'.")
        return

    log_msg("🔹 Iniciando cadastro de produtos (Sischef)...")
    produtos_cadastrados = 0
    atualizar_contador(0, 0)
    rodando = True
    inicio_tempo = time.time()

    threading.Thread(target=atualizar_tempo, daemon=True).start()

    try:
        bot_sischef.arquivo_csv = csv_file_path
        bot_sischef.cadastrar_produtos(
            callback_progresso=atualizar_contador,
            callback_rodando=get_status_rodando
        )
        if get_status_rodando():
            log_msg("✅ Cadastro Sischef concluído!")
        else:
            log_msg("ℹ️ Cadastro Sischef interrompido.")
            
    except Exception as e:
        log_msg(f"❌ Erro durante cadastro Sischef: {e}")
    finally:
        rodando = False

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
            log_msg("... Fechando instância anterior do QRPedir.")
            bot_qrpedir.fechar()
            
        bot_qrpedir = BotQRPedir(usuario, senha)
        bot_qrpedir.iniciar()
        log_msg("✅ Bot QRPEDIR iniciado e logado!")
    except Exception as e:
        log_msg(f"❌ Erro ao iniciar bot QRPEDIR: {e}")

def iniciar_cadastro_qrpedir_thread():
    """ Inicia o cadastro QRPedir com lock (trava)."""
    global cadastro_qr_rodando
    if cadastro_qr_rodando:
        log_msg("⚠️ O cadastro QRPedir já está em andamento.")
        return
    
    cadastro_qr_rodando = True
    atualizar_contador(0, 0) # <--- ADICIONE ESTA LINHA (Reseta o contador)
    inicio_tempo = time.time() # <--- ADICIONE ESTA LINHA (Marca o início)
    try:
        btn_iniciar_cadastro_qr.config(state='disabled', text="Cadastrando...")
    except (tk.TclError, NameError):
        log_msg("Erro: Não foi possível desabilitar o botão de cadastro.")
    threading.Thread(target=atualizar_tempo, daemon=True).start()    
    threading.Thread(target=iniciar_cadastro_qrpedir, daemon=True).start()

def iniciar_cadastro_qrpedir():
    """Lê o CSV, agrupa (Nível 3) e chama o bot."""
    global bot_qrpedir, csv_file_path, cadastro_qr_rodando 
    
    if not bot_qrpedir:
        log_msg("❌ Bot QRPEDIR não iniciado.")
        cadastro_qr_rodando = False
        btn_iniciar_cadastro_qr.config(state='normal', text="Iniciar Cadastro QRPedir")
        return
    if not csv_file_path:
        log_msg("❌ Nenhum CSV selecionado.")
        cadastro_qr_rodando = False
        btn_iniciar_cadastro_qr.config(state='normal', text="Iniciar Cadastro QRPedir")
        return
        
    try:
        dados = pd.read_csv(csv_file_path).fillna('')
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
        
        dados_renomeados = dados.rename(columns=mapeamento)

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

        # === ESTE LOOP RODA SOZINHO E NÃO PRECISA DE MAIS CLIQUES ===
        total = len(itens_para_cadastrar)
        for i, item_agrupado in enumerate(itens_para_cadastrar):
            
            if not cadastro_qr_rodando:
                log_msg("ℹ️ Cadastro QRPedir interrompido pelo usuário.")
                break
                
            log_msg(f"--- Processando Produto {i+1}/{total}: {item_agrupado['Nome']} ---")

            atualizar_contador(i + 1, total)
            # 1. Bot faz o Produto 1
            bot_qrpedir.processar_item_cardapio(item_agrupado)
            # 2. Loop continua para o Produto 2, 3, etc...
            
        log_msg("✅ Cadastro no QRPedir concluído!")
        
    except Exception as e:
        log_msg(f"❌ Erro fatal durante o cadastro QRPedir: {e}")
    finally:
        # Libera o lock e reabilita o botão
        cadastro_qr_rodando = False
        try:
            btn_iniciar_cadastro_qr.config(state='normal', text="Iniciar Cadastro QRPedir")
        except tk.TclError:
            pass # Janela pode ter sido fechada

# --- Funções Gerais ---

def escolher_csv():
    global csv_file_path
    caminho = filedialog.askopenfilename(
        title="Selecione o arquivo CSV",
        filetypes=[("Arquivos CSV", "*.csv")]
    )
    if caminho:
        csv_file_path = caminho
        log_msg(f"📄 CSV selecionado: {csv_file_path}")
    else:
        log_msg("❌ Nenhum arquivo CSV selecionado.")

def get_status_rodando():
    global rodando
    return rodando

def atualizar_contador(atual=0, total=0):
    global produtos_cadastrados, total_produtos
    produtos_cadastrados = atual
    total_produtos = total
    try:
        lbl_contador.config(text=f"📦 Produtos cadastrados: {atual}/{total}")
    except tk.TclError:
        pass

def atualizar_tempo():
    while rodando or cadastro_qr_rodando:
        try:
            tempo = int(time.time() - inicio_tempo)
            minutos, segundos = divmod(tempo, 60)
            lbl_tempo.config(text=f"⏱️ Tempo decorrido: {minutos:02d}:{segundos:02d}")
            time.sleep(1)
        except tk.TclError:
             break
    try:
        lbl_tempo.config(text="⏱️ Tempo decorrido: 00:00")
    except tk.TclError:
        pass

def fechar_bots():
    global bot_sischef, bot_qrpedir, rodando, cadastro_qr_rodando
    log_msg("ℹ️ Solicitando fechamento...")
    rodando = False
    cadastro_qr_rodando = False # Interrompe o loop do QRPedir
    
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
        except Exception:
            pass

    threading.Thread(target=fechar_em_thread, daemon=True).start()

def ao_fechar_janela():
    fechar_bots()
    root.destroy()

# --- GUI ---
root = tk.Tk()
root.title("Bot Sischef & QRPedir - Cadastro via CSV")
root.protocol("WM_DELETE_WINDOW", ao_fechar_janela)

frame_status = tk.Frame(root)
frame_status.grid(row=0, column=0, columnspan=3, padx=10, pady=5, sticky="ew")
lbl_tempo = tk.Label(frame_status, text="⏱️ Tempo decorrido: 00:00", font=("Arial", 10, "bold"))
lbl_tempo.pack(side=tk.LEFT)
lbl_contador = tk.Label(frame_status, text="📦 Produtos cadastrados: 0/0", font=("Arial", 10, "bold"))
lbl_contador.pack(side=tk.RIGHT)

frame_login = tk.Frame(root)
frame_login.grid(row=1, column=0, columnspan=3, padx=10, pady=5)
tk.Label(frame_login, text="Usuário:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
entry_usuario = tk.Entry(frame_login, width=30)
entry_usuario.grid(row=0, column=1, padx=5, pady=5)
tk.Label(frame_login, text="Senha:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entry_senha = tk.Entry(frame_login, width=30, show="*")
entry_senha.grid(row=1, column=1, padx=5, pady=5)

frame_botoes = tk.Frame(root)
frame_botoes.grid(row=2, column=0, columnspan=3, padx=10, pady=10)

tk.Button(frame_botoes, text="Iniciar Bot Sischef", command=iniciar_bot_thread, bg="green", fg="white", width=20).grid(row=0, column=0, padx=5, pady=5)
tk.Button(frame_botoes, text="Escolher CSV", command=escolher_csv, bg="blue", fg="white", width=20).grid(row=0, column=1, padx=5, pady=5)
tk.Button(frame_botoes, text="Iniciar Cadastro Sischef", command=iniciar_cadastro_thread, bg="orange", fg="white", width=20).grid(row=0, column=2, padx=5, pady=5)

tk.Button(frame_botoes, text="Iniciar Bot QRPedir", command=iniciar_bot_qrpedir_thread, bg="#00AEEF", fg="white", width=20).grid(row=1, column=0, padx=5, pady=5)

# Salva a referência do botão para podermos desabilitá-lo
btn_iniciar_cadastro_qr = tk.Button(frame_botoes, text="Iniciar Cadastro QRPedir", command=iniciar_cadastro_qrpedir_thread, bg="#00AEEF", fg="black", width=20)
btn_iniciar_cadastro_qr.grid(row=1, column=1, padx=5, pady=5)

tk.Button(frame_botoes, text="Fechar Navegadores", command=fechar_bots, bg="red", fg="white", width=20).grid(row=1, column=2, padx=5, pady=5)

txt_log = scrolledtext.ScrolledText(root, width=100, height=25, state='disabled', wrap=tk.WORD)
txt_log.grid(row=3, column=0, columnspan=3, padx=10, pady=10)

root.mainloop()