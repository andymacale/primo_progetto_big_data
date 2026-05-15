FROM apache/spark:3.5.1-scala2.12-java11-ubuntu

# 1. Diventiamo root per permettere a Kathara di usare i comandi di rete
USER root

# 2. Installiamo Python e iproute2 per i comandi di rete (ip address)
RUN apt-get update -qq && \
    apt-get install -y -qq python3 python3-pip iproute2 net-tools iputils-ping && \
    rm -rf /var/lib/apt/lists/*

# 3. Disabilitiamo l'entrypoint restrittivo
ENTRYPOINT []
CMD ["/bin/bash"]
