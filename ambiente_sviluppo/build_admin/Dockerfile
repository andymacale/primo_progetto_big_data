FROM kathara/base
RUN apt-get update -qq && \
    apt-get install -y -qq python3 python3-pip && \
    pip3 install streamlit pymongo pyspark pandas --break-system-packages && \
    rm -rf /var/lib/apt/lists/*
CMD ["/bin/bash"]
