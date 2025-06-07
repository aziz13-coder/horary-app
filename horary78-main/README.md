# Horary App Docker Instructions

This repository contains the backend and frontend for the Horary astrology application. A `Dockerfile` is provided to build a container that bundles both parts and serves the API via Gunicorn.

## Build the Image

From the repository root run:

```bash
docker build -t horary-app .
```

## Run the Container

After building the image, start the application with:

```bash
docker run -p 5000:5000 horary-app
```

The API will be available on `http://localhost:5000`.
