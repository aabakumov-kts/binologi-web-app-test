# Prepare main Django-based image
# We use Debian-based image to avoid too much hassle with Geospatial support
FROM python:3.8.5

ENV DEBUG=False \
    DJANGO_SETTINGS_MODULE=electrobin.settings_codeship \
    # Adding app dir to PYTHONPATH for better module discovery
    PYTHONPATH=/app

# Install Sentry CLI
RUN curl -sL https://sentry.io/get-cli/ | bash

RUN apt-get update && apt-get install -y \
    # Enable Geospatial support
    binutils libproj-dev gdal-bin \
    # PostgreSQL support
    libpq-dev postgresql-client-11 \
    # Translations support
    gettext \
    # APT cleanup
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.fbprophet.txt ./requirements.txt app/

# Install Python deps
RUN pip install -r app/requirements.fbprophet.txt --no-cache-dir
RUN pip install -r app/requirements.txt --no-cache-dir

COPY . app/

WORKDIR app/

# CMD is used instead of ENTRYPOINT to allow other use case easily like run migrations leveraging the same image
CMD ["echo", "Default command is not defined."]
