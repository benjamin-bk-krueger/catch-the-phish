#!/bin/sh
. ~/.profile
echo "Starting..."

# Stop server
killall /home/phisher/venv/bin/python3

# Pull current GIT repo
cd /home/phisher/git/catch-the-phish/
git pull

# Purge and copy files to target folders
rm -rf /home/phisher/templates/*
rm -rf /home/phisher/static/*
rm -rf /home/phisher/docs/*

cp -v *.py *.sh *.yml /home/phisher/
cp -v templates/* /home/phisher/templates/
cp -vr static/* /home/phisher/static/
cp -vr docs/* /home/phisher/docs/
git log -1 > /home/phisher/gitlog.txt

# Update mkdocs files
cd /home/phisher/
mkdocs build

# Start server
nohup ./flask.sh >/dev/null 2>&1 &
sleep 5
echo "Finished."
