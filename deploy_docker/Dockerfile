# Standalone image for the SOILL Best Practices Chainlit chatbot.
# Connects to MongoDB Atlas (or other remote MongoDB) and Mistral API via env vars.
#
# Local build (from repository root):
#   docker build -f deploy_docker/Dockerfile -t soill-best-practices .
#
# Render.com: set Root Directory to the repo root, Dockerfile path to
# deploy_docker/Dockerfile (default context is the repo root).

FROM python:3.11-slim-bookworm

WORKDIR /app

COPY deploy_docker/requirements-docker.txt requirements-docker.txt
RUN pip install --upgrade pip \
    && pip install --no-cache-dir \
        pymongo python-dotenv dnspython faiss-cpu "numpy>=1.26.0" "mistralai>=1.2.0,<3" \
    && pip install --no-cache-dir "traceloop-sdk==0.60.0" \
    && pip install --no-cache-dir "chainlit==2.11.0"

COPY config.py app.py build_faiss_index.py ./
COPY soill_chatbot ./soill_chatbot
COPY .chainlit ./.chainlit

RUN mkdir -p data/faiss

COPY deploy_docker/docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

EXPOSE 8000

ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/docker-entrypoint.sh"]
