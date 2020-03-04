ARG PYTHON_VERSION=${PYTHON_VERSION:-"3.7-slim"}
FROM python:${PYTHON_VERSION}

ADD ./ /app/

WORKDIR /app

RUN echo "Setting up project..." && \
    pip install -e . && \
    echo "DONE"

ENTRYPOINT ["pokedex"]
CMD ["status"]