FROM python:3.12-slim@sha256:646fb0bca3dd3ea1bcc6feb72c17ed16eed6e10cffc732fcc1478bd3e7f02d7b

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY app/ ./app/

# CR124/N7: ran as root. This container fronts the public marketing site, so it
# is the most exposed process in the stack and the least privileged thing it
# needs to be. Pairs with the M8 change in docker-compose.yml, which moves it
# off the Postgres superuser onto the `ami_website` role.
RUN groupadd --system --gid 1002 amiweb \
    && useradd --system --uid 1002 --gid amiweb --no-create-home amiweb \
    && chown -R amiweb:amiweb /app
USER amiweb

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
