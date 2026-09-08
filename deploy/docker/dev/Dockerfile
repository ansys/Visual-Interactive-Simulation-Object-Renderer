FROM python:3.14-slim

WORKDIR /app

# Install system dependencies required for:
# - Running Python backend (libx11-6, libxrender1 for VTK and headless rendering)
# - Running frontend build tools (nodejs, npm for React/TypeScript build)
# - Enabling headless GUI support (xvfb for tests or rendering that require a display)
# - System and network utilities (procps, psutils, net-tools, iproute2 for debugging & monitoring)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libx11-6 \
    libxrender1 \
    xvfb \
    nodejs \
    npm \
    procps \
    psutils \
    net-tools \
    net-tools \
    iproute2 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set up Xvfb for headless GUI support.
# This creates a shell script that starts a virtual X server (Xvfb) on display :99,
# enabling applications that require a display (e.g., VTK rendering, browser tests) to run in the container.
RUN echo 'Xvfb :99 -screen 0 1024x768x24 & export DISPLAY=:99' > /etc/profile.d/xvfb.sh \
 && chmod +x /etc/profile.d/xvfb.sh \
 && echo 'source /etc/profile.d/xvfb.sh' >> /root/.bashrc

# Install poetry
RUN pip install --no-cache-dir poetry

# Copy backend files
COPY pyproject.toml poetry.lock ./
COPY src ./src

# Copy frontend (visor-client) code
COPY src/ansys/visor/visor-client ./src/ansys/visor/visor-client

# Copy README.rst
COPY README.rst ./

# Copy dev-only directories
COPY tests ./tests
COPY doc ./doc
COPY examples ./examples

# Install backend dependencies with dev (for testing including Playwright) and setup groups
RUN POETRY_VIRTUALENVS_CREATE=false poetry install --with dev,setup --no-interaction --no-ansi

# Run setup script
RUN visor-setup

# Build frontend
WORKDIR /app/src/ansys/visor/visor-client
RUN npm install \
  && chmod +x ./node_modules/.bin/tsc ./node_modules/.bin/vite \
  && npm run build

# Build dash component
WORKDIR /app/src/ansys/visor/dash
RUN npm install \
  && npm run build

WORKDIR /app

RUN poetry run playwright install chromium
RUN poetry run playwright install-deps chromium

EXPOSE 53211
EXPOSE 8081
ENV PYTHONPATH=/app/src

ENTRYPOINT ["/bin/bash", "-c", "rm -f /tmp/.X99-lock; Xvfb :99 -screen 0 1024x768x24 & export DISPLAY=:99 && exec \"$@\"", "--"]

CMD ["uvicorn", "ansys.visor.viewer.api.server:app", "--host", "0.0.0.0", "--port", "53211"]
