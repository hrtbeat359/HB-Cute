FROM nikolaik/python-nodejs:python3.10-nodejs20

# System deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    wget \
    curl \
    unzip \
    gnupg \
    libnss3 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libgtk-3-0 \
    libasound2 \
    libxshmfence1 \
    libdrm2 \
    fonts-liberation \
    xdg-utils \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# App folder
COPY . /app/
WORKDIR /app/

# Install python deps
RUN python3 -m pip install --upgrade pip && \
    pip3 install --no-cache-dir -U -r requirements.txt

# Install Playwright browsers (Chromium only = lighter)
#RUN playwright install chromium \
    #&& playwright install-deps chromium

# Railway default command
CMD bash start
