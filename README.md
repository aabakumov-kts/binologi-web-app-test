# legacy-web-app
Sources of the legacy web app.

## Set up & Run
It's assumed you have Python 3.8 installed.

You'll need PostgreSQL 11 & PostGIS 2.5 for DB layer and Redis 5.x. For Docker it's possible to leverage this:

https://hub.docker.com/r/mdillon/postgis.

Create new virtual environment at `.venv` and install deps listed in `requirements.txt`.

You need Bower installed globally (`npm install -g bower`) to install some frontend deps via `bower install` at 
`static` subfolder.

Make sure `DATABASES` setting in `electrobin/settings.py` makes sense and use Django migrations to set up database 
schema (`manage.py migrate`). With that ready import fixtures via Django admin:

```
python manage.py loaddata container-types.xml
python manage.py loaddata equipment.xml
python manage.py loaddata errortype.xml
python manage.py loaddata wastetype.xml
python manage.py loaddata sensors/container_types.xml
python manage.py loaddata sensors/error_types.xml
```

Create super admin user (`manage.py createsuperuser`) to access admin website & set up 
some data (countries, companies, containers, operators, drivers etc). Alternatively use `dbseed` management command 
(see [Seeding DB](#seeding-db) section for details).

Use Django Server to run the whole web app.

## Run in Docker
The easiest way is to use Docker Compose, it assumed that you're using Docker 18+ and Compose 1.17+.

Create `.env` file at the root of the source, it should contain following params:

- `WEB_DB_URL`: main PostgreSQL DB connection URL in sense of [dj-database-url](https://github.com/kennethreitz/dj-database-url).
- `NETWORK_NAME`: name of the network to connect web app container to, it should also have PostgreSQL & Redis 
containers connected to it if you're using Docker to run these.
- `REDIS_HOST_NAME`: host name of the Redis server. In case of Docker is network alias of Redis container.
- MQTT settings: TODO

Run `docker-compose up` to get web app running in Docker.

## Known Issues
- None at the moment

## Releasing
Upon releasing from `develop` the existing `master` branch is tagged in the form of `vYYYY-MM-DD.N` and force pushed to 
current `develop` position. Docker Hub builds these tags automatically for historical & safety purposes, N is a 
sequential build number reserved for rebuilds on the same date, typically it's just 1.

To leverage Sentry releases features `release-info.txt` file should be present at root level consisting of two lines:
- Release name, i.e. "legacy-web-app@1.0"
- SHA of the last common commit between current `develop` and previous `master`

Upon releasing both should be bumped correctly. For ease of that `create-release-info.sh` is present at root level. 
After force pushing `master` execute it in `develop` with release version of the next release which will be worked on 
in `develop` and commit updated `release-info.txt`.

## Performance profiling

To profile performance use `runprofileserver` Django admin command from `django-extensions` package.

Execute dev server with the following command:

```python manage.py runprofileserver --use-cprofile --prof-path=./raw-profiler-data```

Then each request rendering pipeline profile will be saved in `raw-profiler-data` folder.

You can then pick & analyze results using `pstats` or your favorite GUI analyzer.

**A note for PyCharm users**: for some reason `Tools > Open CProfile snapshot` won't work until .prof file extension will be replaced with .pstat.

## Seeding DB

To quickly & automatically fill DB with sample data use `dbseed` management command as follows:

```python manage.py dbseed```

See `dbseed` source code at `apps/main/management/commands/dbseed.py` for details of user accounts created.
