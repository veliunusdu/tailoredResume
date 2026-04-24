FROM texlive/texlive:latest

WORKDIR /app

# Install python and pip
RUN apt-get update && apt-get install -y python3 python3-pip python3-venv

# Set up virtualenv
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY pyproject.toml .
# Install dependencies (uv could be used, but pip is simpler for docker)
RUN pip install .

COPY . .

ENV PYTHONPATH=/app/src
