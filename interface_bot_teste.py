import tkinter as tk
from tkinter import scrolledtext, filedialog
import threading
import time
from bot_sischef_teste import BotSischef
from selenium.common.exceptions import TimeoutException 

bot = None
csv_file_path_cadastro = None 
csv_file_path_ncm = None      
inicio_tempo = None
rodando = False
produtos_cadastrados = 0
total_produtos = 0
acao_atual = "" 

# --- Funções ---
def log_msg(msg):
    txt_log.configure(state='normal')
    txt_log.insert(tk.END, msg + "\n")
    txt_log.see(tk.END)
    txt_log.configure(state='disabled')

def iniciar_bot_thread():
    threading.Thread(target=iniciar_bot).start()

def iniciar_bot():
    global bot
    usuario = entry_usuario.get().strip()
    senha = entry_senha.get().strip()

    if not usuario or not senha:
        log_msg("❌ Informe usuário e senha.")
        return

    log_msg(f"🔹 Iniciando bot com usuário: {usuario}")
    try:
        bot = BotSischef(usuario, senha) 
        bot.iniciar()
        log_msg("✅ Bot iniciado. Tela de cadastro carregada! Status: PRONTO.") 
    except Exception as e:
        log_msg(f"❌ Erro ao iniciar bot: {e}. Status: ERRO.") 

def escolher_csv_cadastro():
    global csv_file_path_cadastro
    caminho = filedialog.askopenfilename(
        title="Selecione o arquivo CSV para Cadastro",
        filetypes=[("Arquivos CSV", "*.csv")]
    )
    if caminho:
        csv_file_path_cadastro = caminho
        log_msg(f"📄 CSV de Cadastro selecionado: {csv_file_path_cadastro}")
    else:
        log_msg("❌ Nenhum arquivo CSV de Cadastro selecionado.")

def escolher_csv_ncm():
    global csv_file_path_ncm
    caminho = filedialog.askopenfilename(
        title="Selecione o arquivo CSV para Edição de NCM",
        filetypes=[("Arquivos CSV", "*.csv")]
    )
    if caminho:
        csv_file_path_ncm = caminho
        log_msg(f"📄 CSV de NCM selecionado: {csv_file_path_ncm}")
    else:
        log_msg("❌ Nenhum arquivo CSV de NCM selecionado.")


# --- Funções para Cadastro ---
def iniciar_cadastro_thread():
    threading.Thread(target=iniciar_cadastro).start()

def iniciar_cadastro():
    global bot, csv_file_path_cadastro, inicio_tempo, rodando, produtos_cadastrados, acao_atual
    if not bot:
        log_msg("❌ Bot não iniciado. Clique em 'Iniciar Bot'.")
        return
    if not csv_file_path_cadastro: 
        log_msg("❌ Nenhum CSV de Cadastro selecionado. Clique em 'Escolher CSV (Cadastro)'.")
        return

    log_msg("🔹 Iniciando cadastro de produtos...")
    acao_atual = "cadastro"
    produtos_cadastrados = 0
    atualizar_contador(0, 0, "Produtos cadastrados") 
    rodando = True
    inicio_tempo = time.time()
    log_msg("▶️ Status: RODANDO (CADASTRO)")

    threading.Thread(target=atualizar_tempo).start()

    try:
        bot.arquivo_csv_cadastro = csv_file_path_cadastro 
        bot.cadastrar_produtos(callback_progresso=atualizar_contador)
        log_msg("✅ Cadastro concluído!")
    
    except Exception as e:
        if "ERRO DE VALIDAÇÃO" in str(e):
            log_msg(f"🛑 PROCESSO PAUSADO: {e}")
        elif "ERRO DE SINCRONIZAÇÃO" in str(e): # Captura erros de sincronização/elemento
            log_msg(f"🛑 PROCESSO PAUSADO (SINCRONIZAÇÃO): {e}")
        else:
            log_msg(f"❌ Erro fatal durante cadastro: {e}")
    
    finally:
        rodando = False
        log_msg("⏹️ Status: PARADO")


# --- Funções para Edição de NCM ---
def iniciar_edicao_ncm_thread():
    threading.Thread(target=iniciar_edicao_ncm).start()

def iniciar_edicao_ncm():
    global bot, csv_file_path_ncm, inicio_tempo, rodando, produtos_cadastrados, acao_atual
    if not bot:
        log_msg("❌ Bot não iniciado. Clique em 'Iniciar Bot'.")
        return
    if not csv_file_path_ncm: 
        log_msg("❌ Nenhum CSV de NCM selecionado. Clique em 'Escolher CSV (NCM)'.")
        return
    
    log_msg("🔹 Iniciando edição de NCM de produtos...")
    acao_atual = "edicao_ncm"
    produtos_cadastrados = 0
    atualizar_contador(0, 0, "NCMs Atualizados") 
    rodando = True
    inicio_tempo = time.time()
    log_msg("▶️ Status: RODANDO (EDIÇÃO NCM)")

    threading.Thread(target=atualizar_tempo).start()

    try:
        bot.editar_ncm(
            arquivo_csv=csv_file_path_ncm, 
            callback_progresso=atualizar_contador
        ) 
        log_msg("✅ Edição de NCM concluída!")
        
    except Exception as e:
        if "ERRO DE VALIDAÇÃO" in str(e):
            log_msg(f"🛑 PROCESSO PAUSADO: {e}")
        elif "ERRO DE SINCRONIZAÇÃO" in str(e):
            log_msg(f"🛑 PROCESSO PAUSADO (SINCRONIZAÇÃO): {e}")
        else:
            log_msg(f"❌ Erro fatal durante edição de NCM: {e}")
    
    finally:
        rodando = False
        log_msg("⏹️ Status: PARADO")


# --- FUNÇÃO ATUALIZAR CONTADOR (AJUSTADA PARA RECEBER A MENSAGEM) ---
def atualizar_contador(atual=0, total=0, status_message=None):
    global produtos_cadastrados, total_produtos, acao_atual
    
    if status_message and (" " in status_message or status_message.startswith('✅') or status_message.startswith('🔹') or status_message.startswith('🚨') or status_message.startswith('🟢')):
        log_msg(status_message)
            
    produtos_cadastrados = atual
    total_produtos = total
    
    if acao_atual == "edicao_ncm":
        label_prefix = "NCMs Atualizados"
    else:
        label_prefix = "Produtos cadastrados"

    lbl_contador.config(text=f"📦 {label_prefix}: {atual}/{total}")

def atualizar_tempo():
    while rodando:
        tempo = int(time.time() - inicio_tempo)
        minutos, segundos = divmod(tempo, 60)
        root.after(0, lbl_tempo.config, {"text": f"⏱️ Tempo decorrido: {minutos:02d}:{segundos:02d}"})
        time.sleep(1)

def fechar_bot():
    global bot, rodando
    rodando = False
    if bot:
        bot.fechar()
        bot = None
        log_msg("✅ Bot encerrado. Status: INATIVO.")
    else:
        log_msg("✅ Navegador não estava ativo. Status: INATIVO.")

# --- GUI ---
root = tk.Tk()
root.title("Bot Sischef - Cadastro/Edição via CSV")

# Tempo e contador
lbl_tempo = tk.Label(root, text="⏱️ Tempo decorrido: 00:00", font=("Arial", 10, "bold"))
lbl_tempo.grid(row=0, column=0, padx=10, pady=5, sticky="w") 

lbl_contador = tk.Label(root, text="Produtos cadastrados: 0/0", font=("Arial", 10, "bold"))
lbl_contador.grid(row=0, column=2, padx=10, pady=5, sticky="e") 

# Usuário e Senha
tk.Label(root, text="Usuário:").grid(row=1, column=0, padx=5, pady=5, sticky="e")
entry_usuario = tk.Entry(root, width=30)
entry_usuario.grid(row=1, column=1, padx=5, pady=5)

tk.Label(root, text="Senha:").grid(row=2, column=0, padx=5, pady=5, sticky="e")
entry_senha = tk.Entry(root, width=30, show="*")
entry_senha.grid(row=2, column=1, padx=5, pady=5)

# Botões

# Linha 3: Cadastro
tk.Button(root, text="Iniciar Bot", command=iniciar_bot_thread, bg="green", fg="white", width=20).grid(row=3, column=0, padx=5, pady=10)
tk.Button(root, text="Escolher CSV (Cadastro)", command=escolher_csv_cadastro, bg="blue", fg="white", width=20).grid(row=3, column=1, padx=5, pady=10) 
tk.Button(root, text="Iniciar Cadastro", command=iniciar_cadastro_thread, bg="orange", fg="white", width=20).grid(row=3, column=2, padx=5, pady=10)

# Linha 4: Edição NCM
tk.Button(root, text="Fechar Navegador", command=fechar_bot, bg="red", fg="white", width=20).grid(row=4, column=0, padx=5, pady=10) 
tk.Button(root, text="Escolher CSV (NCM)", command=escolher_csv_ncm, bg="#1E90FF", fg="white", width=20).grid(row=4, column=1, padx=5, pady=10) 
tk.Button(root, text="Iniciar Edição NCM", command=iniciar_edicao_ncm_thread, bg="#FFC300", fg="black", width=20).grid(row=4, column=2, padx=5, pady=10) 

# Log
txt_log = scrolledtext.ScrolledText(root, width=100, height=25, state='disabled')
txt_log.grid(row=5, column=0, columnspan=3, padx=10, pady=10)

root.mainloop()