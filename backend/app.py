import gevent.monkey
gevent.monkey.patch_all()

import os
import sys
import time
import datetime
import threading
import re
import unicodedata
import uuid
import datetime
from functools import wraps

import pandas as pd
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room, disconnect

from config import SECRET_KEY, UPLOAD_FOLDER, MAX_CONTENT_LENGTH, CHROME_HEADLESS
from auth import authenticate_user, register_user, verify_token, init_default_admin, change_password
from database import init_db, get_session
from models import User, SavedCredential, Execution, LogEntry
import crypto_utils


# ---------------------------------------------------------------------------
# Flask App Setup
# ---------------------------------------------------------------------------
app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH

CORS(app, supports_credentials=True)
socketio = SocketIO(
    app, 
    cors_allowed_origins="*",
    async_mode='gevent', 
    ping_timeout=60,
    engineio_logger=True,
    logger=True
)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
# ─── Database Initialization ───
with app.app_context():
    init_db()
    init_default_admin()

# ─── Per-User Session Storage  (in-memory for active bot instances) ───
user_sessions = {}   # { user_id: { bot_sischef, bot_qrpedir, rodando, execution_id, ... } }
sid_to_user = {}     # { socket_sid: (user_id, username) }


def _get_session(user_id):
    """Get or create a user's bot session by user_id."""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'bot_sischef': None,
            'bot_qrpedir': None,
            'rodando': False,
            'cadastro_qr_rodando': False,
            'pausado': False,
            'inicio_tempo': None,
            'execution_id': None,  # Current database Execution ID
            'csv_sischef': None,
            'csv_qrpedir': None,
            'csv_receitas': None,
            'indices': {
                'sischef': 0, 'ncm': 0, 'tributacao': 0,
                'codbarras': 0, 'precovenda': 0, 'qrpedir': 0,
                'receitas': 0, 'ficha_tecnica': 0,
            }
        }
    return user_sessions[user_id]


def _make_log_callback(user_id, username):
    """Create a log callback that emits to the user's SocketIO room AND saves to DB."""
    def log_cb(msg):
        # Emit to UI
        socketio.emit('log', {
            'time': time.strftime('%H:%M:%S'),
            'message': msg
        }, room=username)
        socketio.sleep(0.01)
        # Save to DB if there's an active execution
        session_data = _get_session(user_id)
        exec_id = session_data.get('execution_id')
        if exec_id:
            db = get_session()
            try:
                log_entry = LogEntry(execution_id=exec_id, message=msg)
                db.add(log_entry)
                db.commit()
            except Exception as e:
                print(f"Error saving log to DB: {e}")
                db.rollback()
            finally:
                db.close()

    return log_cb


def _make_progress_callback(user_id, username, bot_type):
    """Create a progress callback that emits to UI and updates DB Execution."""
    session = _get_session(user_id)

    def progress_cb(atual, total, msg=None):
        session['indices'][bot_type] = atual

        # Emit to UI
        socketio.emit('progress', {
            'atual': atual,
            'total': total,
            'bot_type': bot_type,
            'message': msg
        }, room=username)
        socketio.sleep(0.01)
        # Update DB Execution
        exec_id = session.get('execution_id')
        if exec_id:
            db = get_session()
            try:
                execution = db.get(Execution, exec_id)
                if execution:
                    execution.items_done = atual
                    execution.items_total = total
                    db.commit()
            except Exception as e:
                print(f"Error updating progress in DB: {e}")
                db.rollback()
            finally:
                db.close()

    return progress_cb


# ─── Auth Decorator for Socket Events ───
def socket_auth_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        sid = request.sid
        user_info = sid_to_user.get(sid)
        if not user_info:
            emit('error', {'message': 'Não autenticado. Reconecte-se.'})
            return
        user_id, username = user_info
        return f(user_id, username, *args, **kwargs)
    return wrapper


# ---------------------------------------------------------------------------
# HTTP Routes — Auth
# ---------------------------------------------------------------------------
@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    success, message = register_user(data.get('username'), data.get('password'))
    return jsonify({'success': success, 'message': message})


@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    success, token_or_message = authenticate_user(data.get('username'), data.get('password'))
    if success:
        return jsonify({'success': True, 'token': token_or_message, 'username': data.get('username')})
    return jsonify({'success': False, 'message': token_or_message})


@app.route('/api/change-password', methods=['POST'])
def handle_change_password():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'success': False, 'message': 'Token ausente.'}), 401
    
    token = auth_header.split(' ')[1]
    user_id, username = verify_token(token)
    if not user_id:
        return jsonify({'success': False, 'message': 'Token inválido ou expirado.'}), 401
    
    data = request.json
    success, message = change_password(user_id, data.get('old_password'), data.get('new_password'))
    return jsonify({'success': success, 'message': message})


@app.route('/api/history', methods=['GET'])
def get_history():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Não autorizado'}), 401
    
    token = auth_header.split(' ')[1]
    user_id, username = verify_token(token)
    if not user_id:
        return jsonify({'error': 'Token inválido'}), 401

    db = get_session()
    try:
        executions = db.query(Execution).filter_by(user_id=user_id).order_by(Execution.started_at.desc()).limit(50).all()
        result = []
        for e in executions:
            result.append({
                'id': e.id,
                'task_name': e.task_name,
                'status': e.status,
                'csv_filename': e.csv_filename,
                'items_total': e.items_total,
                'items_done': e.items_done,
                'started_at': e.started_at.isoformat() if e.started_at else None,
                'finished_at': e.finished_at.isoformat() if e.finished_at else None
            })
        return jsonify({'history': result})
    finally:
        db.close()


@app.route('/api/history/<int:exec_id>/logs', methods=['GET'])
def get_execution_logs(exec_id):
    auth_header = request.headers.get('Authorization')
    if not auth_header: return jsonify({'error': 'Não autorizado'}), 401
    
    user_id, _ = verify_token(auth_header.split(' ')[1])
    if not user_id: return jsonify({'error': 'Token inválido'}), 401

    db = get_session()
    try:
        execution = db.query(Execution).filter_by(id=exec_id, user_id=user_id).first()
        if not execution:
            return jsonify({'error': 'Execução não encontrada'}), 404
        
        logs = [{
            'timestamp': l.timestamp.isoformat(),
            'message': l.message
        } for l in execution.logs]
        return jsonify({'logs': logs})
    finally:
        db.close()


@app.route('/api/credentials', methods=['GET', 'POST', 'DELETE'])
def manage_credentials():
    auth_header = request.headers.get('Authorization')
    if not auth_header: return jsonify({'error': 'Não autorizado'}), 401
    token = auth_header.split(' ')[1]
    user_id, _ = verify_token(token)
    if not user_id: return jsonify({'error': 'Token inválido'}), 401

    db = get_session()
    try:
        if request.method == 'GET':
            creds = db.query(SavedCredential).filter_by(user_id=user_id).all()
            return jsonify([{
                'id': c.id,
                'system': c.system,
                'label': c.label,
                'username': crypto_utils.decrypt(c.username_enc)
            } for c in creds])

        elif request.method == 'POST':
            data = request.json
            c = SavedCredential(
                user_id=user_id,
                system=data['system'],
                label=data.get('label', ''),
                username_enc=crypto_utils.encrypt(data['username']),
                password_enc=crypto_utils.encrypt(data['password'])
            )
            db.add(c)
            db.commit()
            return jsonify({'success': True, 'id': c.id})

        elif request.method == 'DELETE':
            cred_id = request.args.get('id')
            cred = db.query(SavedCredential).filter_by(id=cred_id, user_id=user_id).first()
            if cred:
                db.delete(cred)
                db.commit()
            return jsonify({'success': True})
    finally:
        db.close()


# ---------------------------------------------------------------------------
# HTTP Routes — File Upload
# ---------------------------------------------------------------------------
@app.route('/api/upload-csv', methods=['POST'])
def upload_csv():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id, username = verify_token(token)
    if not user_id:
        return jsonify({'success': False, 'message': 'Token inválido.'}), 401

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'Nenhum arquivo enviado.'}), 400

    file = request.files['file']
    csv_type = request.form.get('type', 'sischef')  # sischef, qrpedir, receitas

    if file.filename == '':
        return jsonify({'success': False, 'message': 'Nenhum arquivo selecionado.'}), 400

    # Save to user's upload folder
    user_upload_dir = os.path.join(UPLOAD_FOLDER, str(user_id)) # Use user_id for folder
    os.makedirs(user_upload_dir, exist_ok=True)

    filename = f"{csv_type}_{file.filename}"
    filepath = os.path.join(user_upload_dir, filename)
    file.save(filepath)

    # Update session
    session = _get_session(user_id)
    key = f'csv_{csv_type}'
    session[key] = filepath

    # Reset indices for this CSV type
    if csv_type == 'sischef':
        for k in ['sischef', 'ncm', 'tributacao', 'codbarras', 'precovenda']:
            session['indices'][k] = 0
    elif csv_type == 'receitas':
        session['indices']['receitas'] = 0
        session['indices']['ficha_tecnica'] = 0
    elif csv_type == 'qrpedir':
        session['indices']['qrpedir'] = 0

    return jsonify({
        'success': True,
        'message': f'CSV "{file.filename}" salvo para {csv_type}.',
        'filename': file.filename
    })


@app.route('/api/status', methods=['GET'])
def get_status():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    user_id, username = verify_token(token)
    if not user_id:
        return jsonify({'success': False}), 401

    session = _get_session(user_id)
    return jsonify({
        'success': True,
        'rodando': session['rodando'],
        'cadastro_qr_rodando': session['cadastro_qr_rodando'],
        'pausado': session['pausado'],
        'csv_sischef': os.path.basename(session['csv_sischef']) if session['csv_sischef'] else None,
        'csv_qrpedir': os.path.basename(session['csv_qrpedir']) if session['csv_qrpedir'] else None,
        'csv_receitas': os.path.basename(session['csv_receitas']) if session['csv_receitas'] else None,
        'bot_sischef_active': session['bot_sischef'] is not None,
        'bot_qrpedir_active': session['bot_qrpedir'] is not None,
        'indices': session['indices'],
    })


# ---------------------------------------------------------------------------
# SocketIO Events
# ---------------------------------------------------------------------------
@socketio.on('connect')
def on_connect():
    token = request.args.get('token', '')
    user_id, username = verify_token(token)
    if not user_id:
        disconnect()
        return

    sid_to_user[request.sid] = (user_id, username)
    join_room(username)
    _get_session(user_id)  # Ensure session exists
    emit('connected', {'username': username})
    print(f"✅ Socket conectado: {username} (sid={request.sid})")


@socketio.on('disconnect')
def on_disconnect():
    sid = request.sid
    user_info = sid_to_user.pop(sid, None)
    if user_info:
        user_id, username = user_info
        print(f"❌ Socket desconectado: {username}")


# --- Bot Start/Stop ---
@socketio.on('start_bot')
@socket_auth_required
def handle_start_bot(user_id, username, data):
    bot_type = data.get('bot_type')
    usuario = data.get('usuario')
    senha = data.get('senha')
    session = _get_session(user_id)

    if bot_type == 'sischef':
        if session['bot_sischef'] is not None:
            emit('log', {'time': time.strftime('%H:%M:%S'), 'message': '⚠️ Bot Sischef já está aberto.'}, room=username)
            return
        try:
            from bot_sischef import BotSischef
            bot = BotSischef(usuario, senha, log_callback=_make_log_callback(user_id, username), headless=CHROME_HEADLESS)
            bot.iniciar()
            session['bot_sischef'] = bot
            emit('bot_status', {'bot_type': 'sischef', 'active': True}, room=username)
        except Exception as e:
            emit('log', {'time': time.strftime('%H:%M:%S'), 'message': f'❌ Erro ao abrir Sischef: {str(e)}'}, room=username)

    elif bot_type == 'qrpedir':
        if session['bot_qrpedir'] is not None:
            emit('log', {'time': time.strftime('%H:%M:%S'), 'message': '⚠️ Bot QRPedir já está aberto.'}, room=username)
            return
        try:
            from bot_qrpedir import BotQRPedir
            bot = BotQRPedir(usuario, senha, log_callback=_make_log_callback(user_id, username), headless=CHROME_HEADLESS)
            bot.iniciar()
            session['bot_qrpedir'] = bot
            emit('bot_status', {'bot_type': 'qrpedir', 'active': True}, room=username)
        except Exception as e:
            emit('log', {'time': time.strftime('%H:%M:%S'), 'message': f'❌ Erro ao abrir QRPedir: {str(e)}'}, room=username)


@socketio.on('start_task')
@socket_auth_required
def handle_start_task(user_id, username, data):
    task_name = data.get('task')
    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)

    if session['rodando'] or session['cadastro_qr_rodando']:
        log_cb('⚠️ Já existe uma tarefa em execução.')
        return

    # Create Execution in DB
    db = get_session()
    try:
        csv_name = ""
        if task_name == 'cadastro_qrpedir': csv_name = session['csv_qrpedir']
        elif task_name in ['receitas', 'ficha_tecnica']: csv_name = session['csv_receitas']
        else: csv_name = session['csv_sischef']

        execution = Execution(
            user_id=user_id,
            task_name=task_name,
            csv_filename=os.path.basename(csv_name) if csv_name else "Desconhecido",
            status='running'
        )
        db.add(execution)
        db.commit()
        session['execution_id'] = execution.id
    except Exception as e:
        log_cb(f'❌ Erro ao iniciar histórico: {str(e)}')
        db.rollback()
        return
    finally:
        db.close()

    session['rodando'] = True
    session['cadastro_qr_rodando'] = (task_name == 'cadastro_qrpedir')
    session['pausado'] = False
    session['inicio_tempo'] = time.time()
    socketio.emit('task_started', {'task': task_name}, room=username)

    # Start Timer Thread
    threading.Thread(target=_timer_thread, args=(user_id, username), daemon=True).start()

    # Start Task Thread
    task_map = {
        'cadastro_produtos': _run_cadastro_produtos,
        'edicao_ncm': _run_edicao_ncm,
        'tributacao': _run_tributacao,
        'codbarras': _run_codbarras,
        'precovenda': _run_precovenda,
        'receitas': _run_receitas,
        'ficha_tecnica': _run_ficha_tecnica,
        'cadastro_qrpedir': _run_cadastro_qrpedir,
    }
    runner = task_map.get(task_name)
    if runner:
        threading.Thread(target=runner, args=(user_id, username), daemon=True).start()
    else:
        log_cb(f"❌ Tarefa desconhecida: {task_name}")
        _finish_execution(user_id, 'failed')
        session['rodando'] = False
        session['cadastro_qr_rodando'] = False
        socketio.emit('task_stopped', {}, room=username)


@socketio.on('stop_task')
@socket_auth_required
def handle_stop_task(user_id, username):
    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)

    if not session['rodando'] and not session['cadastro_qr_rodando']:
        log_cb("ℹ️ Nenhum processo em execução.")
        return

    log_cb("⏹️ Parando processos...")
    session['rodando'] = False
    session['cadastro_qr_rodando'] = False
    session['pausado'] = False
    
    # Update DB
    _finish_execution(user_id, 'stopped')
    socketio.emit('task_stopped', {}, room=username)


@socketio.on('pause_resume')
@socket_auth_required
def handle_pause_resume(user_id, username):
    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)

    if not session['rodando'] and not session['cadastro_qr_rodando']:
        return

    session['pausado'] = not session['pausado']
    if session['pausado']:
        log_cb("⏸️ Processo PAUSADO.")
    else:
        log_cb("▶️ Processo RETOMADO.")

    socketio.emit('pause_status', {'pausado': session['pausado']}, room=username)


@socketio.on('close_bots')
@socket_auth_required
def handle_close_bots(user_id, username):
    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)

    session['rodando'] = False
    session['cadastro_qr_rodando'] = False
    session['pausado'] = False

    def _close():
        if session['bot_sischef']:
            session['bot_sischef'].fechar()
            session['bot_sischef'] = None
        if session['bot_qrpedir']:
            session['bot_qrpedir'].fechar()
            session['bot_qrpedir'] = None
        log_cb("ℹ️ Navegadores fechados.")
        socketio.emit('bot_status', {'bot_type': 'sischef', 'active': False}, room=username)
        socketio.emit('bot_status', {'bot_type': 'qrpedir', 'active': False}, room=username)

    threading.Thread(target=_close, daemon=True).start()


# ---------------------------------------------------------------------------
# Helper: pause checker
# ---------------------------------------------------------------------------
def _check_pause(session):
    """Block while paused."""
    while session['pausado']:
        if not session['rodando'] and not session['cadastro_qr_rodando']:
            break
        time.sleep(0.5)


def _get_rodando(session):
    """Check if still running (used as callback_rodando)."""
    _check_pause(session)
    return session['rodando']


def _finish_execution(user_id, status):
    """Mark the current execution as finished in the database."""
    session_data = _get_session(user_id)
    exec_id = session_data.get('execution_id')
    if exec_id:
        db = get_session()
        try:
            execution = db.get(Execution, exec_id)
            if execution:
                execution.status = status
                execution.finished_at = datetime.datetime.now(datetime.timezone.utc)
                db.commit()
        except Exception as e:
            print(f"Error finishing execution in DB: {e}")
            db.rollback()
        finally:
            db.close()
            session_data['execution_id'] = None


def _timer_thread(user_id, username):
    session = _get_session(user_id)
    while session['rodando'] or session['cadastro_qr_rodando']:
        if not session['pausado']:
            elapsed = int(time.time() - session['inicio_tempo'])
            mins, secs = divmod(elapsed, 60)
            socketio.emit('timer', {'time': f'{mins:02d}:{secs:02d}'}, room=username)
            socketio.sleep(0)
        time.sleep(0.8)
    socketio.emit('timer', {'time': '00:00'}, room=username)


# ---------------------------------------------------------------------------
# Helper: monetary value cleaner
# ---------------------------------------------------------------------------
def _limpar_valor_monetario(valor):
    if not valor:
        return ""
    return str(valor).replace("R$", "").replace("$", "").strip()


# ---------------------------------------------------------------------------
# Task Runners (one per automation type)
# ---------------------------------------------------------------------------
def _run_cadastro_produtos(user_id, username):
    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)
    progress_cb = _make_progress_callback(user_id, username, 'sischef')

    if not session['bot_sischef']:
        log_cb("❌ Bot Sischef não iniciado.")
        _finish_execution(user_id, 'failed')
        return
    if not session['csv_sischef']:
        log_cb("❌ CSV Geral Sischef não selecionado.")
        _finish_execution(user_id, 'failed')
        return

    session['rodando'] = True
    socketio.emit('task_started', {'task': 'cadastro_produtos'}, room=username)

    arquivo_para_bot = session['csv_sischef']
    try:
        df = pd.read_csv(session['csv_sischef'], dtype=str).fillna('')
        colunas_preco = [col for col in df.columns if any(x in col.lower() for x in ['preco', 'preço', 'custo', 'valor'])]
        if colunas_preco:
            for col in colunas_preco:
                df[col] = df[col].apply(_limpar_valor_monetario)
            pasta = os.path.dirname(session['csv_sischef'])
            arquivo_limpo = os.path.join(pasta, "temp_cadastro_sischef_limpo.csv")
            df.to_csv(arquivo_limpo, index=False)
            arquivo_para_bot = arquivo_limpo
            log_cb("ℹ️ CSV pré-processado (Cifras removidas).")
    except Exception as e:
        log_cb(f"⚠️ Falha pré-processamento: {e}")

    idx = session['indices']['sischef']
    log_cb(f"🔹 Iniciando cadastro a partir do item {idx + 1}...")
    session['inicio_tempo'] = time.time() # Reset timer for this specific task
    try:
        bot = session['bot_sischef']
        bot.arquivo_csv_cadastro = arquivo_para_bot
        bot.start_index = idx
        bot.cadastrar_produtos(
            callback_progresso=progress_cb,
            callback_rodando=lambda: _get_rodando(session)
        )
        if session['rodando']:
            log_cb("✅ Cadastro Sischef concluído!")
            session['indices']['sischef'] = 0
            _finish_execution(user_id, 'completed')
        else:
            _finish_execution(user_id, 'stopped')
    except Exception as e:
        log_cb(f"❌ Erro durante cadastro Sischef: {e}")
        _finish_execution(user_id, 'failed')
    finally:
        session['rodando'] = False
        socketio.emit('task_stopped', {}, room=username)

def _run_edicao_ncm(user_id, username):
    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)
    progress_cb = _make_progress_callback(user_id, username, 'ncm')

    if not session['bot_sischef']:
        log_cb("❌ Bot Sischef não iniciado."); _finish_execution(user_id, 'failed'); return
    if not session['csv_sischef']:
        log_cb("❌ CSV Geral Sischef não selecionado."); _finish_execution(user_id, 'failed'); return

    session['rodando'] = True
    socketio.emit('task_started', {'task': 'edicao_ncm'}, room=username)
    idx = session['indices']['ncm']
    log_cb(f"🔹 Iniciando edição de NCM a partir do item {idx + 1}...")
    session['inicio_tempo'] = time.time() # Reset timer for this specific task

    try:
        bot = session['bot_sischef']
        bot.start_index_ncm = idx
        bot.editar_ncm(
            arquivo_csv=session['csv_sischef'],
            callback_progresso=progress_cb,
            callback_rodando=lambda: _get_rodando(session)
        )
        if session['rodando']:
            log_cb("✅ Edição de NCM concluída!")
            session['indices']['ncm'] = 0
            _finish_execution(user_id, 'completed')
        else:
            _finish_execution(user_id, 'stopped')
    except Exception as e:
        log_cb(f"❌ Erro fatal NCM: {e}")
        _finish_execution(user_id, 'failed')
    finally:
        session['rodando'] = False
        socketio.emit('task_stopped', {}, room=username)


def _run_tributacao(user_id, username):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains

    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)
    progress_cb = _make_progress_callback(user_id, username, 'tributacao')

    if not session['bot_sischef'] or not session['bot_sischef'].driver:
        log_cb("❌ Bot Sischef não iniciado."); _finish_execution(user_id, 'failed'); return
    if not session['csv_sischef']:
        log_cb("❌ CSV Geral Sischef não selecionado."); _finish_execution(user_id, 'failed'); return

    session['rodando'] = True
    socketio.emit('task_started', {'task': 'tributacao'}, room=username)

    produtos_nao_encontrados = []
    try:
        df = pd.read_csv(session['csv_sischef'], dtype=str).fillna('')
        total = len(df)
        log_cb(f"🔹 Iniciando Ajuste de Tributação. Total: {total} itens.")
        session['inicio_tempo'] = time.time() # Reset timer for this specific task
        wait = WebDriverWait(session['bot_sischef'].driver, 10)
        idx = session['indices']['tributacao']

        for i in range(idx, total):
            _check_pause(session)
            if not session['rodando']:
                _finish_execution(user_id, 'stopped'); break

            row = df.iloc[i]
            vals = list(row.values)
            termo = str(vals[0]).strip()
            id_trib = str(vals[1]).strip() if len(vals) > 1 else ""

            progress_cb(i + 1, total, f"🔍 Trib: {termo}")
            try:
                campo_busca = wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                campo_busca.clear(); campo_busca.send_keys(termo); time.sleep(0.5); campo_busca.send_keys(Keys.ENTER)
                time.sleep(1)

                try:
                    session['bot_sischef'].driver.find_element(By.XPATH, "//td[contains(text(), 'Nada encontrado')]")
                    log_cb(f"⚠️ '{termo}' não encontrado.")
                    produtos_nao_encontrados.append(termo)
                except:
                    btn_edit = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn') and contains(., 'Editar')]")))
                    session['bot_sischef'].driver.execute_script("arguments[0].click();", btn_edit)
                    time.sleep(1)
                    try:
                        tab = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(text(), 'Tributações (fiscais)')]")))
                        session['bot_sischef'].driver.execute_script("arguments[0].click();", tab)
                        time.sleep(1)
                        if id_trib:
                            cp_gp = wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:grupoTributario_input")))
                            cp_gp.click(); time.sleep(0.2); cp_gp.send_keys(Keys.CONTROL, "a"); cp_gp.send_keys(Keys.BACK_SPACE)
                            cp_gp.send_keys(id_trib); time.sleep(0.5); cp_gp.send_keys(Keys.ENTER)
                            time.sleep(1)
                            session['bot_sischef'].driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                            ActionChains(session['bot_sischef'].driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                            time.sleep(1.5)
                            try:
                                session['bot_sischef'].driver.execute_script("window.scrollTo(0, 0);")
                                time.sleep(0.5)
                                btn_list = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'produtoList.jsf') and contains(., 'Listagem')]")))
                                session['bot_sischef'].driver.execute_script("arguments[0].click();", btn_list)
                                wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                                time.sleep(1)
                            except Exception:
                                session['bot_sischef'].driver.back(); time.sleep(1)
                        else:
                            session['bot_sischef'].driver.back()
                    except Exception as e_in:
                        log_cb(f"❌ Erro interno Trib: {e_in}")
                        session['bot_sischef'].driver.back()
            except Exception as e:
                log_cb(f"❌ Erro Trib '{termo}': {e}")
            session['indices']['tributacao'] = i + 1

        if produtos_nao_encontrados:
            log_cb("⚠️ ITENS NÃO ENCONTRADOS (TRIBUTAÇÃO):")
            for item in produtos_nao_encontrados:
                log_cb(f" • {item}")

        if session['indices']['tributacao'] == total:
            log_cb("✅ Tributação finalizada!")
            session['indices']['tributacao'] = 0
            _finish_execution(user_id, 'completed')

    except Exception as e:
        log_cb(f"❌ Erro crítico: {e}")
        _finish_execution(user_id, 'failed')
    finally:
        session['rodando'] = False
        socketio.emit('task_stopped', {}, room=username)


def _run_codbarras(user_id, username):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains

    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)
    progress_cb = _make_progress_callback(user_id, username, 'codbarras')

    if not session['bot_sischef'] or not session['bot_sischef'].driver:
        log_cb("❌ Bot Sischef não iniciado."); _finish_execution(user_id, 'failed'); return
    if not session['csv_sischef']:
        log_cb("❌ CSV Geral Sischef não selecionado."); _finish_execution(user_id, 'failed'); return

    session['rodando'] = True
    socketio.emit('task_started', {'task': 'codbarras'}, room=username)

    produtos_nao_encontrados = []
    produtos_duplicados = []
    try:
        df = pd.read_csv(session['csv_sischef'], dtype=str).fillna('')
        total = len(df)
        log_cb(f"🔹 Iniciando Ajuste Cód. Barras. Total: {total} itens.")
        session['inicio_tempo'] = time.time() # Reset timer for this specific task
        wait = WebDriverWait(session['bot_sischef'].driver, 10)
        idx = session['indices']['codbarras']

        for i in range(idx, total):
            _check_pause(session)
            if not session['rodando']:
                _finish_execution(user_id, 'stopped'); break

            row = df.iloc[i]
            vals = list(row.values)
            termo = str(vals[0]).strip()
            novo_cod_barras = str(vals[1]).strip() if len(vals) > 1 else ""

            progress_cb(i + 1, total, f"🔍 CB: {termo}")
            try:
                campo_busca = wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                campo_busca.clear(); campo_busca.send_keys(termo); time.sleep(0.5); campo_busca.send_keys(Keys.ENTER)
                time.sleep(1)

                try:
                    session['bot_sischef'].driver.find_element(By.XPATH, "//td[contains(text(), 'Nada encontrado')]")
                    log_cb(f"⚠️ '{termo}' não encontrado.")
                    produtos_nao_encontrados.append(termo)
                except:
                    btn_edit = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn') and contains(., 'Editar')]")))
                    session['bot_sischef'].driver.execute_script("arguments[0].click();", btn_edit)
                    time.sleep(1)
                    try:
                        campo_cb = wait.until(EC.presence_of_element_located((By.ID, "tabSessoesProduto:codigoBarras")))
                        campo_cb.click(); time.sleep(0.2)
                        campo_cb.send_keys(Keys.CONTROL, "a"); time.sleep(0.1)
                        campo_cb.send_keys(Keys.BACK_SPACE); time.sleep(0.1)
                        campo_cb.send_keys(novo_cod_barras); time.sleep(0.5)
                        session['bot_sischef'].driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                        ActionChains(session['bot_sischef'].driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                        time.sleep(1.5)

                        duplicado = False
                        try:
                            elementos_erro = session['bot_sischef'].driver.find_elements(By.XPATH, "//*[contains(text(), 'Regra violada')]")
                            for elem in elementos_erro:
                                if elem.is_displayed():
                                    duplicado = True; break
                            if duplicado:
                                log_cb(f"⛔ DUPLICADO: '{termo}' -> CB: {novo_cod_barras}")
                                produtos_duplicados.append(f"{termo} - {novo_cod_barras}")
                                botoes_ok = session['bot_sischef'].driver.find_elements(By.XPATH, "//*[contains(text(), 'Ok, obrigado')]")
                                for btn in botoes_ok:
                                    if btn.is_displayed():
                                        session['bot_sischef'].driver.execute_script("arguments[0].click();", btn)
                                        time.sleep(1); break
                        except: pass

                        if not duplicado:
                            log_cb(f"✅ CodBarras alterado: '{novo_cod_barras}'")
                            time.sleep(1)

                        try:
                            session['bot_sischef'].driver.execute_script("window.scrollTo(0, 0);")
                            time.sleep(0.5)
                            btn_list = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'produtoList.jsf') and contains(., 'Listagem')]")))
                            session['bot_sischef'].driver.execute_script("arguments[0].click();", btn_list)
                            wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                            time.sleep(1)
                        except:
                            session['bot_sischef'].driver.back(); time.sleep(1)
                    except Exception as e_field:
                        log_cb(f"❌ Erro edição '{termo}': {e_field}")
                        session['bot_sischef'].driver.back()
            except Exception as e:
                log_cb(f"❌ Erro geral '{termo}': {e}")
            session['indices']['codbarras'] = i + 1

        if produtos_nao_encontrados:
            log_cb("⚠️ ITENS NÃO ENCONTRADOS (COD BARRAS):")
            for item in produtos_nao_encontrados: log_cb(f" • {item}")

        if session['indices']['codbarras'] == total:
            log_cb("✅ Ajuste Cód. Barras finalizado!")
            session['indices']['codbarras'] = 0
            _finish_execution(user_id, 'completed')

    except Exception as e:
        log_cb(f"❌ Erro crítico CB: {e}")
        _finish_execution(user_id, 'failed')
    finally:
        session['rodando'] = False
        socketio.emit('task_stopped', {}, room=username)


def _run_precovenda(user_id, username):
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.action_chains import ActionChains

    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)
    progress_cb = _make_progress_callback(user_id, username, 'precovenda')

    if not session['bot_sischef'] or not session['bot_sischef'].driver:
        log_cb("❌ Bot Sischef não iniciado."); _finish_execution(user_id, 'failed'); return
    if not session['csv_sischef']:
        log_cb("❌ CSV Geral Sischef não selecionado."); _finish_execution(user_id, 'failed'); return

    session['rodando'] = True
    socketio.emit('task_started', {'task': 'precovenda'}, room=username)

    produtos_nao_encontrados = []
    try:
        df = pd.read_csv(session['csv_sischef'], dtype=str).fillna('')
        total = len(df)

        def limpar_coluna(nome):
            n = unicodedata.normalize('NFKD', str(nome)).encode('ASCII', 'ignore').decode('utf-8')
            return re.sub(r'[^a-zA-Z0-9]', '', n).lower()

        col_nome = col_compra = col_venda = None
        for col in df.columns:
            c_limpo = limpar_coluna(col)
            if c_limpo in ['nome', 'produto', 'descricao', 'item', 'codigo']:
                if not col_nome: col_nome = col
            elif c_limpo in ['precodecompra', 'precocompra', 'custo', 'valorcompra', 'compra', 'valorcusto']:
                col_compra = col
            elif c_limpo in ['precodevenda', 'precovenda', 'venda', 'valorvenda', 'preco']:
                col_venda = col

        todas_colunas = list(df.columns)
        if not col_nome and len(todas_colunas) > 0: col_nome = todas_colunas[0]
        if not col_compra and len(todas_colunas) > 1: col_compra = todas_colunas[1]
        if not col_venda and len(todas_colunas) > 2: col_venda = todas_colunas[2]

        log_cb(f"🔹 Ajuste de Preços ({total} itens).")
        log_cb(f"📌 Identificado: Produto='{col_nome}' | Compra='{col_compra}' | Venda='{col_venda}'")
        session['inicio_tempo'] = time.time() # Reset timer for this specific task
        wait = WebDriverWait(session['bot_sischef'].driver, 10)
        idx = session['indices']['precovenda']

        for i in range(idx, total):
            _check_pause(session)
            if not session['rodando']:
                _finish_execution(user_id, 'stopped'); break

            row = df.iloc[i]
            termo = str(row[col_nome]).strip() if col_nome and col_nome in row else ""
            novo_preco_compra = str(row[col_compra]).strip() if col_compra and col_compra in row else ""
            novo_preco_venda = str(row[col_venda]).strip() if col_venda and col_venda in row else ""
            if novo_preco_compra.lower() in ['nan', 'null']: novo_preco_compra = ""
            if novo_preco_venda.lower() in ['nan', 'null']: novo_preco_venda = ""
            novo_preco_compra = _limpar_valor_monetario(novo_preco_compra)
            novo_preco_venda = _limpar_valor_monetario(novo_preco_venda)

            progress_cb(i + 1, total, f"🔍 Produto: {termo}")
            try:
                campo_busca = wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                campo_busca.clear(); campo_busca.send_keys(termo); time.sleep(0.5); campo_busca.send_keys(Keys.ENTER)
                time.sleep(2)

                try:
                    session['bot_sischef'].driver.find_element(By.XPATH, "//td[contains(text(), 'Nada encontrado')]")
                    log_cb(f"⚠️ '{termo}' não encontrado.")
                    produtos_nao_encontrados.append(termo)
                except:
                    btn_edit = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@class, 'btn') and contains(., 'Editar')]")))
                    session['bot_sischef'].driver.execute_script("arguments[0].click();", btn_edit)
                    time.sleep(2)
                    try:
                        if novo_preco_compra:
                            campo_compra = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id, 'tabSessoesProduto:valorUnitarioCompra') or contains(@id, 'precoCompra')]")))
                            campo_compra.click(); time.sleep(0.2)
                            campo_compra.send_keys(Keys.CONTROL, "a"); time.sleep(0.1)
                            campo_compra.send_keys(Keys.BACK_SPACE); time.sleep(0.1)
                            campo_compra.send_keys(novo_preco_compra); time.sleep(0.5)
                        if novo_preco_venda:
                            campo_venda = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(@id, 'tabSessoesProduto:valorUnitarioVenda') or contains(@id, 'precoVenda')]")))
                            campo_venda.click(); time.sleep(0.2)
                            campo_venda.send_keys(Keys.CONTROL, "a"); time.sleep(0.1)
                            campo_venda.send_keys(Keys.BACK_SPACE); time.sleep(0.1)
                            campo_venda.send_keys(novo_preco_venda); time.sleep(0.5)
                        session['bot_sischef'].driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                        time.sleep(0.5)
                        ActionChains(session['bot_sischef'].driver).key_down(Keys.ALT).send_keys('s').key_up(Keys.ALT).perform()
                        time.sleep(2.0)
                        log_cb(f"✅ Preços salvos | Compra: {novo_preco_compra or 'N/A'} | Venda: {novo_preco_venda or 'N/A'}")
                        try:
                            session['bot_sischef'].driver.execute_script("window.scrollTo(0, 0);")
                            time.sleep(0.5)
                            btn_list = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, 'produtoList.jsf') and contains(., 'Listagem')]")))
                            session['bot_sischef'].driver.execute_script("arguments[0].click();", btn_list)
                            wait.until(EC.presence_of_element_located((By.ID, "_input-busca-generica_")))
                            time.sleep(1)
                        except:
                            session['bot_sischef'].driver.back(); time.sleep(1)
                    except Exception as e_field:
                        log_cb(f"❌ Erro ao editar preço '{termo}': {e_field}")
                        session['bot_sischef'].driver.back()
            except Exception as e:
                log_cb(f"❌ Erro geral '{termo}': {e}")
            session['indices']['precovenda'] = i + 1

        if produtos_nao_encontrados:
            log_cb("⚠️ ITENS NÃO ENCONTRADOS (PREÇO):")
            for item in produtos_nao_encontrados: log_cb(f" • {item}")

        if session['indices']['precovenda'] == total:
            log_cb("✅ Ajuste de Preços finalizado!")
            session['indices']['precovenda'] = 0
            _finish_execution(user_id, 'completed')

    except Exception as e:
        log_cb(f"❌ Erro crítico Preço: {e}")
        _finish_execution(user_id, 'failed')
    finally:
        session['rodando'] = False
        socketio.emit('task_stopped', {}, room=username)


def _run_receitas(user_id, username):
    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)
    progress_cb = _make_progress_callback(user_id, username, 'receitas')

    if not session['bot_sischef']:
        log_cb("❌ Bot Sischef não iniciado."); _finish_execution(user_id, 'failed'); return
    if not session['csv_receitas']:
        log_cb("❌ CSV de Receitas não selecionado."); _finish_execution(user_id, 'failed'); return

    session['rodando'] = True
    socketio.emit('task_started', {'task': 'receitas'}, room=username)
    idx = session['indices']['receitas']
    log_cb(f"🔹 Iniciando cadastro de Receitas (a partir de {idx + 1}).")
    session['inicio_tempo'] = time.time() # Reset timer for this specific task

    try:
        bot = session['bot_sischef']
        bot.arquivo_csv_receitas = session['csv_receitas']
        bot.start_index = idx
        bot.cadastrar_receitas(
            callback_progresso=progress_cb,
            callback_rodando=lambda: _get_rodando(session)
        )
        if session['rodando']:
            log_cb("✅ Cadastro de Receitas concluído!")
            session['indices']['receitas'] = 0
            _finish_execution(user_id, 'completed')
        else:
            _finish_execution(user_id, 'stopped')
    except Exception as e:
        log_cb(f"❌ Erro fatal Receitas: {e}")
        _finish_execution(user_id, 'failed')
    finally:
        session['rodando'] = False
        socketio.emit('task_stopped', {}, room=username)

def _run_ficha_tecnica(user_id, username):
    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)
    progress_cb = _make_progress_callback(user_id, username, 'ficha_tecnica')

    if not session['bot_sischef']:
        log_cb("❌ Bot Sischef não iniciado."); _finish_execution(user_id, 'failed'); return
    if not session['csv_receitas']:
        log_cb("❌ CSV de Receitas não selecionado."); _finish_execution(user_id, 'failed'); return

    session['rodando'] = True
    socketio.emit('task_started', {'task': 'ficha_tecnica'}, room=username)
    idx = session['indices']['ficha_tecnica']
    log_cb(f"🔹 Iniciando cadastro de Fichas Técnicas (a partir de {idx + 1}).")
    session['inicio_tempo'] = time.time()

    try:
        bot = session['bot_sischef']
        bot.arquivo_csv_receitas = session['csv_receitas']
        bot.start_index = idx
        bot.cadastrar_fichas_tecnicas(
            callback_progresso=progress_cb,
            callback_rodando=lambda: _get_rodando(session)
        )
        if session['rodando']:
            log_cb("✅ Cadastro de Fichas Técnicas concluído!")
            session['indices']['ficha_tecnica'] = 0
            _finish_execution(user_id, 'completed')
        else:
            _finish_execution(user_id, 'stopped')
    except Exception as e:
        log_cb(f"❌ Erro fatal Fichas: {e}")
        _finish_execution(user_id, 'failed')
    finally:
        session['rodando'] = False
        socketio.emit('task_stopped', {}, room=username)

def _run_cadastro_qrpedir(user_id, username):
    session = _get_session(user_id)
    log_cb = _make_log_callback(user_id, username)
    progress_cb = _make_progress_callback(user_id, username, 'qrpedir')

    if not session['bot_qrpedir']:
        log_cb("❌ Bot QRPedir não iniciado."); _finish_execution(user_id, 'failed'); return
    if not session['csv_qrpedir']:
        log_cb("❌ CSV QRPedir não selecionado."); _finish_execution(user_id, 'failed'); return

    session['cadastro_qr_rodando'] = True
    socketio.emit('task_started', {'task': 'cadastro_qrpedir'}, room=username)
    try:
        dados = pd.read_csv(session['csv_qrpedir'], dtype=str).fillna('')
        log_cb(f"Iniciando cadastro no QRPedir. Total de LINHAS lidas: {len(dados)}")

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
            if col_csv in chaves_bot:
                novo_map[col_csv] = chaves_bot[col_csv]
        df = df.rename(columns=novo_map)

        log_cb("... Analisando e agrupando dados...")
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
                produto_atual = row.to_dict(); produto_atual["grupos_complemento"] = []
                grupo_complemento_atual = None; last_nome_prod = nome_prod; last_nome_grupo = ""

            if nome_grup_comp and nome_grup_comp != last_nome_grupo:
                if produto_atual:
                    grupo_complemento_atual = row.to_dict(); grupo_complemento_atual["itens"] = []
                    if 'min' in row: grupo_complemento_atual['min'] = row['min']
                    if 'max' in row: grupo_complemento_atual['max'] = row['max']
                    if 'ordem' in row: grupo_complemento_atual['ordem'] = row['ordem']
                    produto_atual["grupos_complemento"].append(grupo_complemento_atual)
                    last_nome_grupo = nome_grup_comp

            if nome_item_comp:
                if grupo_complemento_atual:
                    grupo_complemento_atual["itens"].append(row.to_dict())
                elif produto_atual and produto_atual["grupos_complemento"]:
                    grupo_complemento_atual = produto_atual["grupos_complemento"][-1]
                    grupo_complemento_atual["itens"].append(row.to_dict())

            if produto_atual:
                if "Preco" in produto_atual and produto_atual["Preco"]:
                    produto_atual["Preco"] = _limpar_valor_monetario(produto_atual["Preco"])
                if grupo_complemento_atual and "itens" in grupo_complemento_atual:
                    for it in grupo_complemento_atual["itens"]:
                        if "item_valor" in it and it["item_valor"]:
                            it["item_valor"] = _limpar_valor_monetario(it["item_valor"])

        if produto_atual: itens_para_cadastrar.append(produto_atual)

        total = len(itens_para_cadastrar)
        log_cb(f"✅ Dados agrupados. Total: {total}")
        idx = session['indices']['qrpedir']

        for i in range(idx, total):
            _check_pause(session)
            if not session['cadastro_qr_rodando']:
                log_cb("ℹ️ Interrompido."); break

            item_agrupado = itens_para_cadastrar[i]
            progress_cb(i, total, f"--- Processando {i + 1}/{total}: {item_agrupado['Nome']} ---")
            try:
                session['bot_qrpedir'].processar_item_cardapio(item_agrupado)
                socketio.sleep(0.01) # Yield to keep heartbeat alive
                session['indices']['qrpedir'] = i + 1
                progress_cb(i + 1, total, f"✅ Produto {item_agrupado['Nome']} salvo.")
            except Exception as e:
                log_cb(f"❌ ERRO no produto {item_agrupado['Nome']}: {e}")
                log_cb("❌ ITEM PULADO.")
                session['indices']['qrpedir'] = i + 1

        if session['indices']['qrpedir'] == total and session['cadastro_qr_rodando']:
            log_cb("✅ Cadastro QRPedir concluído!")
            session['indices']['qrpedir'] = 0

    except Exception as e:
        log_cb(f"❌ Erro fatal QR: {e}")
    finally:
        session['cadastro_qr_rodando'] = False
        socketio.emit('task_stopped', {}, room=username)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == '__main__':
    init_default_admin()
    print("🚀 Servidor iniciando em http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
