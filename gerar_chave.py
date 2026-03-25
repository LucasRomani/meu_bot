from cryptography.fernet import Fernet
print("\nCOPIE A CHAVE ABAIXO:")
print(Fernet.generate_key().decode())
print("")