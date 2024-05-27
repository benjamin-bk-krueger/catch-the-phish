#!/bin/sh
# export FLASK_APP=app              # flask app to be started (app.py)

cd /home/phisher || exit          # go to our home directory
# flask run -h 0.0.0.0 -p 5030    # listen to port 5030 on all interfaces <- development server
waitress-serve --port=5030 --host=0.0.0.0 app:app # listen to port 5030 on all interfaces <-  production-ready server
