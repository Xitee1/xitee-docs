# Welcome!

Visit the page here: https://xitee1.github.io/

## Development setup
1. Clone the repo
2. Make sure python and python venv is installed
3. `python -m venv .venv`
4. `source .venv/bin/activate`
5. `pip install -r requirements.txt`
6. `mkdocs serve` or run via vscode (MkDocs: Serve)

## Docker

You can run the site using Docker. The image is built automatically via GitHub Actions and pushed to the GitHub Container Registry.

### Building the Docker Image Locally

To build the Docker image locally:

```bash
docker build -t xitee1.github.io:local .
```

Then run the container:
```bash
docker run -p 8080:80 xitee1.github.io:local
```

Visit http://localhost:8080 to view the site.

### Docker Compose Example

```yaml
services:
  docs:
    image: ghcr.io/xitee1/xitee1.github.io:latest
    ports:
      - "8080:80"
    restart: unless-stopped
```

Run with:
```bash
docker compose up -d
```

Then visit http://localhost:8080