#!/usr/bin/env bash
set -e

# Controlla se lo script è eseguito come root
if [ "$EUID" -ne 0 ]; then
  echo "Errore: Esegui questo script come root (usa sudo)."
  exit 1
fi

echo "=== 1. Installazione di nvidia-container-toolkit ==="
apt-get update
apt-get install -y nvidia-container-toolkit

echo "=== 2. Configurazione di Docker per utilizzare NVIDIA come runtime di default ==="
# Configura nvidia-container-toolkit per docker e lo imposta come default-runtime
nvidia-ctk runtime configure --runtime=docker --set-as-default

echo "=== 3. Riavvio del servizio Docker ==="
systemctl restart docker

echo "=== 4. Verifica dell'accesso alla GPU da Docker ==="
if docker run --rm --gpus all nvidia/cuda:12.3.0-runtime-ubuntu22.04 nvidia-smi; then
  echo "=== Successo: Docker ha accesso alla GPU! ==="
else
  echo "=== Errore o Avviso: Il test container non è riuscito, ma la configurazione è stata applicata. ==="
fi
