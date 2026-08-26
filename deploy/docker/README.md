# Running VISOR in a Docker Container

The VISOR project contains Docker configurations for both development and release environments.

For each environment, there is a Dockerfile and docker-compose.yml to enable containerizing the FastAPI service,
including its frontend and backend. The Docker configurations are located in the `deploy/docker/dev` directory for development
and `deploy/docker/release` for production.

The containers can be used for local development, debugging, and CI (e.g. running unit tests in GitHub workflows).

Dockerfile
* Installs system and Python dependencies (via poetry)
* Runs visor-setup
* Builds the frontend assets
* Starts the FastAPI app with uvicorn

docker-compose.yml
* Maps the ports (53211, 8081) for frontend/backend access
* Sets the PYTHONPATH environment variable
* Can be extended for additional configuration

## Prerequisites
* [Podman](https://podman.io/) or [Docker ](https://www.docker.com/) installed


## Building and running the docker container
We can build and run the docker container using straight docker commands, or we can use docker compose.

Note that on desktops, Ansys is recommending using podman, which offers analogous commands to docker.  The docker commands are shown below, but they should be interchangeable with podman commands.  (Note that podman also accepts the Dockerfile and docker-compose.yml files as defaults)


### Option 1: Build and run with Docker (or Podman)
#### i. Build the image
```
docker build -t visor-image -f docker/dev/Dockerfile .
```
#### ii. Run the container
```
# on windows:
docker run --name visor-service -p 53211:53211 -p 8081:8081 -v %cd%:/workspace visor-image
# on linux:
docker run --name visor-service -p 53211:53211 -p 8081:8081 -v $(pwd):/workspace visor-image
# Access FastAPI at http://localhost:53211
```

The above command mounts the current directory into the container at `/workspace`,
which is where the FastAPI service expects to find the project files.
You can adjust the volume mount as needed for your project structure.
See the section on [Volume Mounts](#volume-mounts) below for more details.

#### iii. Stop and remove the container
```
docker container stop visor-service
docker container rm visor-service
docker image rm visor-image
```

### Option 2: Use Docker Compose
Docker compose uses the `docker-compose.yml` file to build and run the container,
which simplifies the process by managing the configuration and dependencies in a
single file.

The docker-compose.yml file is located in the root of the VISOR project directory.

#### i. Build the image and run the container

To build and run the container using docker compose, run:
```
docker compose -f deploy/docker/dev/docker-compose.yml up
# uses existing image if available
# To build a new image first, use `docker compose up --build`
```

#### ii. Stop and and remove the container (and optionally the image)

To stop the container, run:
```
docker compose down
# this kills the container but keeps the image
# to remove the image as well, use:
# docker compose -f deploy/docker/dev/docker-compose.yml down --rmi
```

### Access the FastAPI service
Once the container is running, you can access the FastAPI service at: http://localhost:53211

When making calls to the FastAPI service, the `/start` and `/update` APIs
take a `file_path` parameter.  Note that if a relative path is provided, it is relative
to the `/app` directory, which contains only the data that was copied when the image was built.

If you need to specify a file, e.g. `example_file.vtm`, that is included in the
mounted volume (e.g. a file in your local project directory), but was not included in the docker image at the time it was built,
you can specify the file path as follows:

```
{
  "file_path": "/workspace/example_file.vtm"
}
```

Similarly, if you have a custom directory mounted into the container at `/workspace`,
you can specify the file path relative to that directory.


### Volume Mounts

The docker containers that are generated from the above sections provide
access to the user's local disk at runtime, by mounting a volume from the local host
into the container.
This allows the container to read and write files directly from the host filesystem.

Using the above commands, the user's current directory (the top level directory of the
visor repository) is mounted into the container at `/workspace`.

You can adjust the volume mount as needed for your project structure.

#### i. Mounting a Custom Directory Using Docker Run Command
The docker run command shown in [Section ii. Run the container](#ii-run-the-container)
mounts the current directory into the container at `/workspace`.
You can adjust the volume mount as needed for your project structure.

For example, if you are running the docker container from the `visor` project root
and would like to mount a specific data directory for testing or development,
you can specify a path like this:

```
docker run --name visor-service -p 53211:53211 -p 8081:8081 -v C:\ANSYSDev\NoBackup\example-data:/workspace visor-image
```
#### ii. Using Docker Compose
The above command can also be specified in the `docker-compose.yml` file.
On Windows machines, due to the way the file paths are handled, we need to handle
the volume mounts a bit differently than on Linx or MacOS.


##### On Linux/MacOS:
To mount a specific data directory, you can modify the `volumes` section like this:

```yaml
volumes:
  - /path/to/example-data:/workspace
```

#### On Windows:
To mount a specific data directory, you can modify the `volumes` section as follows.
Note this is using the WSL path format, which is required for Docker on Windows.
The absolute path should be specified in the WSL format, which is typically `/mnt/c/` for the C: drive.


```yaml

services:
  backend:
    # other configurations...
    volumes:
      - local_data_volume:/workspace


volumes:
  local_data_volume:
    driver: local
    driver_opts:
      type: none
      o: bind
      # On windows, set path using the WSL path format
      # e.g. for a Windows path like C:\ANSYSDev\NoBackup\example-data:
      device: /mnt/c/ANSYSDev/NoBackup/example-data
```
This code for adding the volume mount is included as a comment in the `docker-compose.yml` file,
so you can uncomment and modify it as needed.

### Notes:
Exec into a running container using bash:
```
docker exec -it visor-service /bin/bash
```

Commands to find and remove all containers and/or images:
```
docker container list -a | grep -v NAMES | awk '{print $NF}' | xargs podman container rm
docker image list -a | grep -v "IMAGE ID" | awk '{print $3}' | xargs podman image rm
```
Note: All commands are interchangeable with docker if preferred.


