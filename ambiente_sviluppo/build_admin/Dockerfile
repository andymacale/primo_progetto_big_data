FROM kathara/base
RUN apt-get update -qq && \
    apt-get install -y -qq python3 python3-pip default-jre && \
    pip3 install streamlit pymongo pyspark==3.5.1 pandas nltk --break-system-packages && \
    rm -rf /var/lib/apt/lists/*
CMD ["/bin/bash"]
