import bcrypt
import jwt
import datetime
from config import SECRET_KEY
from database import get_session
from models import User


def register_user(username, password):
    """Register a new user in the database. Returns (success, message)."""
    session = get_session()
    try:
        # Check if username already exists
        existing_user = session.query(User).filter(User.username.ilike(username)).first()
        if existing_user:
            return False, 'Usuário já existe.'

        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        new_user = User(
            username=username,
            password_hash=password_hash
        )
        session.add(new_user)
        session.commit()
        return True, 'Usuário registrado com sucesso.'
    except Exception as e:
        session.rollback()
        return False, f'Erro ao registrar usuário: {str(e)}'
    finally:
        session.close()


def authenticate_user(username, password):
    """Authenticate a user using the database. Returns (success, token_or_message)."""
    session = get_session()
    try:
        user = session.query(User).filter(User.username.ilike(username)).first()
        if user:
            if bcrypt.checkpw(password.encode('utf-8'), user.password_hash.encode('utf-8')):
                token = jwt.encode({
                    'user_id': user.id,
                    'username': user.username,
                    'exp': datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=24)
                }, SECRET_KEY, algorithm='HS256')
                return True, token
            else:
                return False, 'Senha incorreta.'
        return False, 'Usuário não encontrado.'
    except Exception as e:
        return False, f'Erro na autenticação: {str(e)}'
    finally:
        session.close()


def verify_token(token):
    """Verify a JWT token. Returns (user_id, username) or (None, None)."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload.get('user_id'), payload.get('username')
    except jwt.ExpiredSignatureError:
        return None, None
    except jwt.InvalidTokenError:
        return None, None


def init_default_admin():
    """Create a default admin user if no users exist in the database."""
    session = get_session()
    try:
        user_count = session.query(User).count()
        if user_count == 0:
            register_user('admin', 'admin123')
            print("✅ Usuário padrão criado no banco: admin / admin123")
    finally:
        session.close()
def change_password(user_id, old_password, new_password):
    """Change a user's password. Returns (success, message)."""
    session = get_session()
    try:
        user = session.get(User, user_id)
        if not user:
            return False, 'Usuário não encontrado.'
        
        # Verify old password
        if not bcrypt.checkpw(old_password.encode('utf-8'), user.password_hash.encode('utf-8')):
            return False, 'Senha antiga incorreta.'
        
        # Update password
        user.password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        session.commit()
        return True, 'Senha alterada com sucesso.'
    except Exception as e:
        session.rollback()
        return False, f'Erro ao alterar senha: {str(e)}'
    finally:
        session.close()
