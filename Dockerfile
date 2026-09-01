# Single-container deploy: nginx (static site + reverse proxy) + the stdlib
# Python backend, talking over a unix socket inside the container. Isolation
# here is the container boundary itself, replacing the systemd sandboxing
# install.sh used for the bare-metal deploy (see src/skill-agents-library.service.in).
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -d /home/app -g www-data -s /usr/sbin/nologin app

ENV HOME=/home/app
WORKDIR /app

COPY src /app/src
COPY docker/nginx.conf /etc/nginx/nginx.conf
COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh /app/src/regenerate.sh

EXPOSE 80
ENTRYPOINT ["/entrypoint.sh"]
