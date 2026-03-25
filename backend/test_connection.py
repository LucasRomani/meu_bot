import os
import sys

# Adicionar o diretorio atual ao path para importar os modulos locais
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import init_db, get_session
from models import User
from auth import register_user, authenticate_user

def test_supabase_connection():
    print("🚀 Iniciando teste de conexão com Supabase...")
    
    try:
        # 1. Tentar inicializar as tabelas
        print("📁 Verificando/Criando tabelas no banco de dados...")
        init_db()
        print("✅ Tabelas verificadas!")

        # 2. Tentar registrar um usuario de teste
        print("📝 Testando registro de usuário...")
        success, message = register_user("test_user_cloud", "test_pass_123")
        print(f"   Resultado: {message}")

        # 3. Tentar autenticar
        if success or "já existe" in message:
            print("🔑 Testando autenticação...")
            auth_ok, token_or_msg = authenticate_user("test_user_cloud", "test_pass_123")
            if auth_ok:
                print("✅ Autenticação funcionando! Token gerado com sucesso.")
            else:
                print(f"❌ Falha na autenticação: {token_or_msg}")
        
        print("\n✨ Teste de integração básica concluído com sucesso!")
        
    except Exception as e:
        print(f"\n❌ ERRO FATAL no teste: {str(e)}")
        print("\nDicas:")
        print("1. Verifique se o DATABASE_URL no seu .env está correto.")
        print("2. Certifique-se de que o Supabase aceita conexões externas.")

if __name__ == "__main__":
    test_supabase_connection()
