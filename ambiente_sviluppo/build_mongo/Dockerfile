FROM mongo:7.0

# Installiamo i comandi di rete (ip address, ping) necessari a Kathara
RUN apt-get update -qq && \
    apt-get install -y -qq iproute2 net-tools iputils-ping && \
    rm -rf /var/lib/apt/lists/*
CMD ["/bin/bash"]
