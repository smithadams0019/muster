# Muster's control plane: the FastAPI app that fronts the DRAFT and HOLD loops.
#
# There is no frontend build stage here — the console (React 18 + Vite) is a
# later piece of work and does not exist in this tree yet. When it lands, this
# file gains a Node build stage and a `MUSTER_CONSOLE_DIR` the API serves from;
# until then this image is the API alone.
#
# `pip install .` is required before uvicorn will start: the API imports
# `muster` as an installed package, not a relative path into `src/`.
FROM python:3.12-slim

WORKDIR /app

# AWS credentials for the live Bedrock calls (DRAFT and HOLD both call
# `global.anthropic.claude-sonnet-4-6` in `us-east-1` by default) are supplied
# at run time by the deployment environment, never baked into the image.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

COPY pyproject.toml ./
COPY src ./src

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "muster.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
