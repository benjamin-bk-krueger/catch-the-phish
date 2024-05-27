#!/bin/bash
sudo -i -u postgres
createuser --interactive
createdb flask

su - flask -s /bin/bash
psql
ALTER USER flask PASSWORD 'password';
\q


pg_dump -F c phisher > phisher.dump
pg_restore -d phisher phisher.dump
pg_restore -U phisher -d phisher tmp/phisher.dump
