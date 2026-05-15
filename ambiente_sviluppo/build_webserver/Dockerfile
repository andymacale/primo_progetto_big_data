FROM kathara/bind

RUN apt-get update -qq && \
    apt-get install -y -qq apache2 && \
    rm -rf /var/lib/apt/lists/*

CMD ["/bin/bash"]
