FROM oven/bun:1-slim

WORKDIR /app

# Install Python and ML dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip3 install --no-cache-dir -r requirements.txt

# Install Bun dependencies
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile

# Copy application code
COPY src/ ./src/
COPY prediction/ ./prediction/
COPY utils/ ./utils/
COPY experiments/ ./experiments/
COPY config.yaml ./

# Download the large model file from Hugging Face
RUN apt-get update && apt-get install -y wget && \
    mkdir -p models && \
    wget -O models/balanced_random_forest_model.pkl https://huggingface.co/MCTEEKUNG123/Heatwave-AI/resolve/main/models/balanced_random_forest_model.pkl && \
    wget -O models/scaler.pkl https://huggingface.co/MCTEEKUNG123/Heatwave-AI/resolve/main/models/scaler.pkl && \
    wget -O models/feature_names.pkl https://huggingface.co/MCTEEKUNG123/Heatwave-AI/resolve/main/models/feature_names.pkl

EXPOSE 10000

CMD ["bun", "run", "src/index.ts"]
