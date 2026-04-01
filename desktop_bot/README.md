# Bot Sischef & QRPedir - Guia de Uso

## Instalação

### 1. Instalar dependências Python
```bash
pip install -r requirements.txt
```

**Pacotes necessários:**
- `pandas` - manipulação de dados CSV
- `requests` - requisições HTTP
- `selenium` - automação web
- `webdriver-manager` - gerenciamento automático do ChromeDriver

### 2. Requisitos do Sistema
- Python 3.8+ instalado e no PATH
- Google Chrome instalado (o bot usa navegador Chrome)
- Conexão com internet
- Arquivo CSV com dados para cadastro (formato esperado no código)

## Como Rodar

### Opção 1: Executar via Script Principal (Recomendado)
```bash
python run_bot.py
```

### Opção 2: Executar Diretamente a Interface
```bash
python interface_bot.py
```

## Estrutura do Projeto

```
desktop_bot/
├── interface_bot.py      # Interface gráfica (tkinter) - ponto de entrada
├── bot_sischef.py        # Bot para Sistema Sischef
├── bot_qrpedir.py        # Bot para QRPedir
├── bot_ncmEditor.py      # Editor de NCM (utilizado por bot_sischef)
├── requirements.txt      # Dependências Python
├── run_bot.py           # Script inicializador (recomendado)
└── README.md            # Este arquivo
```

## Funcionalidades

### Bot Sischef
- Cadastro de produtos
- Edição de NCM
- Edição de tributação
- Atualização de código de barras
- Edição de preço de venda
- Gestão de receitas

### Bot QRPedir
- Automação do sistema QRPedir

## Troubleshooting

### Erro: "Chrome not found"
- Instale o Google Chrome
- Ou ajuste as opções do navegador em `bot_sischef.py`

### Erro: "ModuleNotFoundError"
- Execute: `pip install -r requirements.txt`

### Erro de Conexão
- Verifique sua conexão com a internet
- Verifique se as URLs dos sistemas estão acessíveis

## Notas Importantes
- Os bots usam credenciais (usuário/senha) fornecidas pela interface gráfica
- O arquivo CSV deve estar no formato esperado pela aplicação
- Os bots executam com retenção de estado (podem ser pausados e retomados)
