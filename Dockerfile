# GILty as a container: `docker run --rm -it ghcr.io/sparecores/gilty` for the
# live view, without -t for status lines (as in Kubernetes logs).
#
# CPython comes from python-build-standalone (installed by uv): for GILty it
# runs about 25% faster than the Alpine (musl) build and 15% faster than
# Debian's, measured on the same node, so the numbers it shows are close to
# what the hardware can do.
FROM ghcr.io/astral-sh/uv:0.8.17-bookworm-slim AS build
ENV UV_PYTHON_INSTALL_DIR=/opt/python UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
RUN uv python install 3.13
WORKDIR /src
COPY pyproject.toml README.md LICENSE ./
COPY gilty ./gilty
RUN uv venv --python 3.13 /opt/gilty && VIRTUAL_ENV=/opt/gilty uv pip install --no-cache .

FROM debian:bookworm-slim
COPY --from=build /opt/python /opt/python
COPY --from=build /opt/gilty /opt/gilty
ENV PATH=/opt/gilty/bin:$PATH
USER 65534
ENTRYPOINT ["gilty"]
