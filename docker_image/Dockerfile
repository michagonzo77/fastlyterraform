# Use the specified base image
FROM ghcr.io/kubiyabot/kubiya-agent:stable
USER root

# Copy script
COPY /scripts/query_fastly.py /usr/local/bin/query-fastly
RUN chmod +x /usr/local/bin/query-fastly

# Copy script
COPY /scripts/query_fastly_realtime.py /usr/local/bin/query-fastly-realtime
RUN chmod +x /usr/local/bin/query-fastly-realtime

# Copy script
COPY /scripts/purge_fastly_cache.sh /usr/local/bin/purge-fastly-cache
RUN chmod +x /usr/local/bin/purge-fastly-cache

# Install dependencies
RUN apt-get update && apt-get install -y \
    curl \
    jq \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Download and install Fastly CLI .deb file
RUN curl -o /tmp/fastly.deb -L https://github.com/fastly/cli/releases/download/v10.10.0/fastly_10.10.0_linux_amd64.deb && \
    apt-get install -y /tmp/fastly.deb && \
    rm /tmp/fastly.deb && \
    chmod +x /usr/local/bin/fastly && \
    chown appuser:appuser /usr/local/bin/fastly

# Install python env libraries
COPY ./requirements.txt /requirements.txt
RUN /usr/local/bin/pip install --no-cache-dir -r /requirements.txt

USER appuser

WORKDIR /tmp