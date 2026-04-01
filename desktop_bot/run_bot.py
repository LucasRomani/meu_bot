"""
Script principal para iniciar o bot via interface gráfica
"""
import sys
import os

# Adiciona o diretório atual ao path para imports locais
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    import interface_bot
