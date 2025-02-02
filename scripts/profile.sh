# Python venv
export PATH=~/venv/bin:$PATH

# Default credentials, need to be changed on production stage
export POSTGRES_URL=localhost:5432
export POSTGRES_USER=phisher
export POSTGRES_PW=phisher
export POSTGRES_DB=phisher
export SECRET_KEY=secret-key-goes-here
export FLASK_ENV=production
export FLASK_DEBUG=0
export S3_ENDPOINT=http://localhost:9000
export S3_QUOTA=100
export S3_BUCKET=phisher
export S3_GLOBAL=GLOBAL
export WWW_SERVER=http://localhost:5020
export MAIL_ENABLE=1
export MAIL_SERVER=localhost
export MAIL_SENDER=mail@localhost
export MAIL_ADMIN=admin@localhost
export APP_VERSION=1.0
export APP_PREFIX=
export LOG_ENABLE=0
export LOG_FILE=phisher.log
export SITEMAP_DATE=2023-11-06