# GILty as a container: `docker run --rm -it ghcr.io/sparecores/gilty` for the
# live view, without -t for status lines (as in Kubernetes logs).
FROM python:3.13-alpine
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY gilty ./gilty
RUN pip install --no-cache-dir . && rm -rf /src
WORKDIR /
USER 65534
ENTRYPOINT ["gilty"]
