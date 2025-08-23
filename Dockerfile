FROM n8nio/n8n:latest
 
# Install python3
USER root
RUN apk add --update python3 py3-pip
 
USER node
RUN python3 -m pip install --user --break-system-packages pipx readability-lxml beautifulsoup4 html2text requests

# Add the path of the pipx installation to PATH
ENV PATH="/home/node/.local/bin:$PATH"

# Make sure the virtual environment is activated by default
ENV PATH="/home/node/.n8n/read_url_markdown/venv/bin:$PATH"