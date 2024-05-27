FROM ubuntu:latest

LABEL version="0.9"
LABEL maintainer="Ben Krueger <sayhello@blk8.de>"

RUN apt-get update
RUN apt-get install -y python3.9 python3-pip python3-psycopg2

RUN pip3 install Flask Werkzeug==2.3.0 flask-sqlalchemy flask-login Flask-WTF email_validator flask_wtf flask-sitemap Flask-Mail flask-restx flask-marshmallow marshmallow-sqlalchemy markdown2 boto3 mkdocs waitress pymupdf

RUN apt-get clean
RUN rm -rf /var/lib/apt/lists/*

RUN useradd -m -s /bin/false phisher

EXPOSE 5030

USER phisher

RUN mkdir /home/phisher/templates /home/phisher/static /home/phisher/uploads /home/phisher/downloads /home/phisher/.aws

COPY *.py *.sh *.yml /home/phisher/
COPY templates/ /home/phisher/templates/
COPY static/ /home/phisher/static/
COPY docs/ /home/phisher/docs/

RUN cd /home/phisher && mkdocs build

CMD ["/home/phisher/flask.sh"]
