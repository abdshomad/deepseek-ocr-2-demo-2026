# Agent Operations and Workspace Guide

This project is managed and enhanced using AI Coding Agents. This document guides agents on how to install, manage, and run the project context.

## Active Agents

- **AI Coding Agents (Lead Developer)**: Handles workspace setup, Docker configurations, dependency management via `uv`, and proxy integration via Nginx.

## Git Submodule Policy (Mandatory)

**Never modify source code inside a git submodule.** The upstream demo lives in [DeepSeek-OCR-2-Demo](DeepSeek-OCR-2-Demo) (see [.gitmodules](.gitmodules)). Treat submodule trees as read-only vendor code.

- Do **not** edit, refactor, patch, or commit changes under any submodule path.
- Do **not** add files, delete files, or fix bugs by changing submodule source.
- Prefer integration at the repo boundary: [Dockerfile](Dockerfile), [docker-compose.yml](docker-compose.yml), [nginx.conf](nginx.conf), environment variables, wrapper scripts, and top-level project files.

To change behavior, update the parent repository only. To pick up upstream fixes, bump the submodule pointer—do not fork edits inside the submodule checkout.

See [docs/design.md](docs/design.md) for rationale and examples.

## Path Policy (Mandatory)

**Never use hardcoded absolute paths** (such as `/home/<username>/...`) in configuration files, build scripts, volume mappings, or documentation.
- Always use relative paths for files inside the repository (e.g., `./config`, `Dockerfile`).
- Always use dynamic variables like `${HOME}` or standard environment variables for absolute paths on the host system to ensure configuration portability for other logged-in users.

## Issue Tracking Policy (Mandatory)

**Always record any issues, causes, and solutions** in the `/issues/` folder.
- **Definition of an Issue**: An issue refers strictly to a blocking error, bug, or unexpected behavior that requires a fix. New feature requests, additions, or enhancements are not considered issues and should not be logged here.
- File naming convention: `{2-digits-number}-{slug}.md` (e.g., `01-base64-image-display.md`).
- Document the issue clearly, describing the symptoms/errors, the root cause, and the implemented solution.

## App Testing Policy (Mandatory)

When a user intentionally asks to test the app:
- Use browser tools to test the app.
- Take a screenshot for each sample image, each step, and each variant/option until the OCR result appears.
- Save screenshots in the `/screenshots/` folder.
- Use the file naming convention: `{2-digit-numberss}-{steps#}-{variant/options if any}-{slug}.jpg`.

## Agent System Tasks

1. **Dependency Integration**: Keep dependencies synchronized using `uv`. Never touch submodule source code; integrate via env, Docker, Nginx, and parent-repo config instead.
2. **Reverse Proxying**: Handle static asset routing errors through Nginx configuration overrides in [nginx.conf](nginx.conf).
3. **Containerization**: Maintain the [docker-compose.yml](docker-compose.yml) and [Dockerfile](Dockerfile) configurations.

## Useful Commands for Agents

- **Installation**: Run [install.sh](install.sh) to bootstrap local dependencies.
- **Running locally**: Run [run.sh](run.sh) to start the app.
- **Docker Compose**: Run `docker compose up -d` to launch the multi-container stack.
