# Muster's control plane: the FastAPI app that fronts the DRAFT and HOLD loops,
# serving the React console (Vite build) as static files from the same process.
#
# Stage one builds the console. Stage two installs the Python package and
# copies the built console into the image at a path set explicitly via
# MUSTER_CONSOLE_DIR - not left to whatever the app would resolve on its own.
# `pip install .` puts `muster` into site-packages, so any path resolved
# relative to the module would land inside the Python installation rather
# than the app, and the console would silently 404. That exact bug shipped on
# a previous project.

FROM node:20-slim AS console-build

WORKDIR /console

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim

WORKDIR /app

# AWS credentials for the live Bedrock calls (DRAFT and HOLD both call
# `global.anthropic.claude-sonnet-4-6` in `us-east-1` by default) are supplied
# at run time by the deployment environment, never baked into the image.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MUSTER_CONSOLE_DIR=/app/frontend/dist

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

COPY --from=console-build /console/dist ./frontend/dist

RUN test -d "$MUSTER_CONSOLE_DIR"

EXPOSE 8080

CMD ["uvicorn", "muster.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
