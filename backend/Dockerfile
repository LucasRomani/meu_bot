FROM python:3.11-slim

# Evita arquivos .pyc e permite logs em tempo real
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Instala apenas o essencial para gerenciar repositórios e chaves
RUN apt-get update && apt-get install -y \
    wget \
    gnupg2 \
    curl \
    ca-certificates \
    --no-install-recommends

# Adiciona o repositório do Google Chrome de forma moderna
RUN wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | gpg --dearmor -o /usr/share/keyrings/google-chrome.gpg \
    && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list

# Instala o Chrome (ele vai puxar automaticamente todas as dependências libx11, libnss, etc.)
RUN apt-get update && apt-get install -y \
    google-chrome-stable \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Instala dependências do Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante do código
COPY . .

# Cria pasta de uploads
RUN mkdir -p /app/uploads && chmod 777 /app/uploads

EXPOSE 5000

CMD ["python", "app.py"]