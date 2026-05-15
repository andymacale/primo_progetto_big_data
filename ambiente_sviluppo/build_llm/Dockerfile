FROM ollama/ollama

# Installiamo i comandi di rete necessari a Kathara
RUN apt-get update -qq && \
    apt-get install -y -qq iproute2 net-tools iputils-ping && \
    rm -rf /var/lib/apt/lists/*

# Disabilitiamo l'entrypoint restrittivo di ollama
ENTRYPOINT []
CMD ["/bin/bash"]
