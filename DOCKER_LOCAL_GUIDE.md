# 🐳 Guia de Desenvolvimento Local (Docker Desktop)

Este manual explica como rodar o projeto `meu_bot_0.2` na sua máquina local usando Docker, garantindo que as alterações no código sejam refletidas rapidamente.

## 1. Pré-requisitos
*   **Docker Desktop** instalado e RODANDO (o ícone da baleia deve estar verde).
*   **Git Bash** ou Terminal de sua preferência.

## 2. Como Iniciar o Ambiente
Da raiz do projeto (`c:\meu_bot_0.2`), execute:

```bash
# Constrói e sobe os containers em segundo plano
docker-compose up --build -d
```

## 3. Acessando os Serviços
*   **Frontend**: [http://localhost](http://localhost) (Porta 80)
*   **Backend API**: [http://localhost:5000/api/status](http://localhost:5000/api/status)

## 4. Desenvolvimento em Tempo Real (Hot-Reload)
*   **Backend**: O código do backend está mapeado via volumes. Sempre que você alterar um arquivo em `backend/`, o servidor Flask irá reiniciar automaticamente dentro do container.
*   **Frontend**: Para o frontend, o Docker usa uma versão otimizada (Nginx). Se você estiver fazendo muitas mudanças na interface, recomenda-se rodar o frontend fora do Docker para ter o hot-reload instantâneo do Vite:
    ```bash
    cd frontend
    npm install
    npm run dev
    ```

## 5. Resolução de Problemas (Troubleshooting)

### Docker não encontrado / Erro de conexão
Se você vir o erro: `failed to connect to the docker API...`, significa que o **Docker Desktop não está aberto**. 
1. Abra o Docker Desktop no Windows.
2. Espere o status ficar "Engine Running".
3. Tente o comando `docker-compose up` novamente.

### Erro de Porta em Uso
Se a porta 80 ou 5000 já estiver ocupada por outro programa (como Skype ou IIS):
1. Edite o arquivo `docker-compose.yml`.
2. Mude `80:80` para algo como `8080:80`.
3. Acesse via `http://localhost:8080`.

### Verificando Logs
Para ver o que está acontecendo "dentro" do robô:
```bash
docker-compose logs -f backend
```

---
*Nota: Este ambiente é apenas para desenvolvimento. Para produção, continuamos usando Render, Netlify e Supabase.*
