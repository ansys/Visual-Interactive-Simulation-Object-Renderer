FROM python:3.11-slim AS release

ARG PACKAGE_VERSION

RUN echo "Building ansys-visor-viewer version: $PACKAGE_VERSION"

WORKDIR /app

# Install runtime dependencies
# - Running Python backend (libx11-6, libxrender1 for VTK and headless rendering)
# - Enabling headless GUI support (xvfb for tests or rendering that require a display)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libx11-6 \
    libxrender1 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Install Python runtime dependency
RUN pip install --no-cache-dir uvicorn

# Set up Xvfb for headless GUI support.
RUN echo 'Xvfb :99 -screen 0 1024x768x24 & export DISPLAY=:99' > /etc/profile.d/xvfb.sh \
 && chmod +x /etc/profile.d/xvfb.sh \
 && echo 'source /etc/profile.d/xvfb.sh' >> /root/.bashrc

# Create a non-root user and set permissions
RUN useradd -m visoruser
RUN mkdir -p /app/logs && chown visoruser /app/logs
RUN mkdir -p /tmp/.X11-unix && chmod 1777 /tmp/.X11-unix

# Secure pip install using BuildKit secret
RUN --mount=type=secret,id=SOLUTIONS_PYPI_PRIVATE_PAT \
    pip install --no-cache-dir ansys-visor-viewer==${PACKAGE_VERSION} \
    --extra-index-url "https://__token__:$(cat /run/secrets/SOLUTIONS_PYPI_PRIVATE_PAT)@pkgs.dev.azure.com/ansys-solutions/_packaging/ansys-solutions/pypi/simple/"

# Set the user to run the application
USER visoruser

EXPOSE 53211
EXPOSE 8081
ENV PYTHONPATH=/app/src

ENTRYPOINT ["/bin/bash", "-c", "rm -f /tmp/.X99-lock; Xvfb :99 -screen 0 1024x768x24 & export DISPLAY=:99 && exec \"$@\"", "--"]

CMD ["uvicorn", "ansys.visor.viewer.api.server:app", "--host", "0.0.0.0", "--port", "53211"]



