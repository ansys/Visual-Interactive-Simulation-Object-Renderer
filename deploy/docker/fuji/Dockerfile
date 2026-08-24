# --- Release Stage ---
FROM python:3.11-slim AS release

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

# Copy the example assets
COPY examples /app/examples
COPY tests /app/tests

# Install the wheel using BuildKit secret
RUN --mount=type=secret,id=pypi_pat \
    pip install --no-cache-dir ansys-visor-viewer \
    --extra-index-url https://__token__:$(cat /run/secrets/pypi_pat)@pkgs.dev.azure.com/ansys-solutions/_packaging/ansys-solutions/pypi/simple/

# TODO: remove this once buggy trame_vtklocal downloading behaviour is resolved
#       (currently re-downloads this upon each startup even if the files exist)
RUN chown -R visoruser /usr/local/lib/python3.11/site-packages/trame_vtklocal/module

# Set the user to run the application
USER visoruser

EXPOSE 53211
EXPOSE 8081
ENV PYTHONPATH=/app/src

ENTRYPOINT ["/bin/bash", "-c", "rm -f /tmp/.X99-lock; Xvfb :99 -screen 0 1024x768x24 & export DISPLAY=:99 && exec \"$@\"", "--"]

CMD ["python", "examples/python/simple_example.py"]



