# Install Bower-based deps as a separate build stage
FROM node:10 AS bower-installer

# We don't care about number & size of layers here
COPY ./static/.bowerrc ./static/bower.json bower_install/
WORKDIR bower_install/

RUN npm install -g bower

RUN bower install --allow-root

# Prepare main Django-based image
# We use Debian-based image to avoid too much hassle with Geospatial support
FROM python:3.8.5

ENV DEBUG=False \
    DJANGO_SETTINGS_MODULE=electrobin.settings_docker \
    # Adding app dir to PYTHONPATH for better module discovery
    PYTHONPATH=/app

RUN apt-get update && apt-get install -y \
    # Enable Geospatial support
    binutils libproj-dev gdal-bin \
    # PostgreSQL support
    libpq-dev \
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

COPY --from=bower-installer /bower_install ./static

RUN python manage.py collectstatic --noinput && \
    python manage.py compilemessages -l en -l ru

EXPOSE 8000/tcp

# CMD is used instead of ENTRYPOINT to allow other use case easily like run migrations leveraging the same image
CMD ["gunicorn", "-b", "0.0.0.0:8000", "electrobin.wsgi:application", "--access-logfile", "-", "--error-logfile", "-", "-t", "150"]

# Alternative CMDs:
# CMD ["daphne", "-b", "0.0.0.0", "-p", "8000", "--access-log", "-", "electrobin.asgi:application"] - run Daphne for Websockets support
# CMD ["celery", "beat", "-A", "electrobin"] - run Celery beat scheduler
# CMD ["celery", "worker", "-A", "electrobin"] - run Celery worker process
# CMD ["python", "apps/sensors/mqtt_listener.py", "<MQTT broker host>"] - run MQTT listener for sensors app
