import os  # for direct file system and environment access
import re  # for regular expressions
import random  # for captcha random numbers
import string  # for string operations
import logging  # enable logging
import fitz  # for PDF to image conversion
import json  # for JSON handling

import boto3  # for S3 storage
import forms
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, \
    session  # most important Flask modules
from flask_login import UserMixin, LoginManager, login_user, logout_user, login_required, \
    current_user  # to manage user sessions
from flask_mail import Mail, Message  # to send mails
from flask_marshmallow import Marshmallow  # to marshall our objects
from flask_restx import Api, Resource   # to enable the REST API
from flask_sitemap import Sitemap  # to generate sitemap.xml
from flask_sqlalchemy import SQLAlchemy  # object-relational mapper (ORM)
from flask_wtf.csrf import CSRFProtect  # CSRF protection
from werkzeug.security import generate_password_hash, check_password_hash  # for password hashing
from werkzeug.utils import secure_filename  # to prevent path traversal attacks
from markupsafe import escape  # to safely escape form data
from logging.handlers import SMTPHandler  # get crashes via mail
from urllib.parse import unquote  # for URL encoding and decoding

from forms import (LoginForm, PasswordForm, PasswordResetForm, FileRenameForm, FileUploadForm, ContactForm, AccountForm,
                   StudentMailForm, StudentPasswordForm, StudentDeletionForm, StudentResetForm, CampaignForm,
                   ScenarioForm, AreaForm)  # Flask/Jinja template forms


# the app configuration is done via environmental variables
POSTGRES_URL = os.environ['POSTGRES_URL']  # DB connection data
POSTGRES_USER = os.environ['POSTGRES_USER']
POSTGRES_PW = os.environ['POSTGRES_PW']
POSTGRES_DB = os.environ['POSTGRES_DB']
SECRET_KEY = os.environ['SECRET_KEY']
WWW_SERVER = os.environ['WWW_SERVER']
MAIL_SERVER = os.environ['MAIL_SERVER']  # mail host
MAIL_SENDER = os.environ['MAIL_SENDER']
MAIL_ADMIN = os.environ['MAIL_ADMIN']
MAIL_ENABLE = int(os.environ['MAIL_ENABLE'])
S3_ENDPOINT = os.environ['S3_ENDPOINT']  # where S3 buckets are located
S3_QUOTA = os.environ['S3_QUOTA']
S3_BUCKET = os.environ['S3_BUCKET']
S3_GLOBAL = os.environ['S3_GLOBAL']
UPLOAD_FOLDER = os.environ['HOME'] + "/uploads"  # directory for program data
DOWNLOAD_FOLDER = os.environ['HOME'] + "/downloads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}
APP_VERSION = os.environ['APP_VERSION']
APP_PREFIX = os.environ['APP_PREFIX']
LOG_ENABLE = int(os.environ['LOG_ENABLE'])
LOG_FILE = os.environ['LOG_FILE']
SITEMAP_DATE = os.environ['SITEMAP_DATE']

# internal error messages
ERR_NOT_EXIST = "That entry does not exist."
ERR_ALREADY_EXIST = "That entry does already exist."
ERR_AUTH = "You are not authorized to perform that action or to view that page."

# internal page modes
PAGE_INIT = "init"
PAGE_MODAL = "modal"
PAGE_MAIL = "mail"
PAGE_PASS = "pass"
PAGE_DELETE = "delete"
PAGE_UPLOAD = "upload"
PAGE_RENAME = "rename"
PAGE_RESET = "reset"

# internal roles
ROLE_ADMIN = "admin"
ROLE_USER = "student"

# internal file name
FILE_ALT_ENDING = "_2"
FILE_ALT_WARNING = "Name already exists. New name selected."

# Flask app configuration containing static (css, img) path and template directory
app = Flask(__name__,
            static_url_path=APP_PREFIX + '/static',
            static_folder='static',
            template_folder='templates')


# enable global variables
@app.context_processor
def inject_version_and_prefix():
    return dict(version=APP_VERSION, prefix=APP_PREFIX)


# Enable logging and crashes via mail
if MAIL_ENABLE == 1:
    mail_handler = SMTPHandler(
        mailhost='127.0.0.1',
        fromaddr=MAIL_SENDER,
        toaddrs=[MAIL_ADMIN],
        subject='www.catch-the-phish.com: Application Error'
    )
    mail_handler.setLevel(logging.ERROR)
    mail_handler.setFormatter(logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    ))

    if not app.debug:
        app.logger.addHandler(mail_handler)


# Enable CSRF protection for the app
csrf = CSRFProtect(app)

# Limit file uploads to 16MB
app.config['MAX_CONTENT_LENGTH'] = 16 * 1000 * 1000

# sitemap.xml configuration
ext = Sitemap(app=app)

# REST API configuration
api = Api(app, decorators=[csrf.exempt])

# Marshall configuration
marsh = Marshmallow(app)

# E-Mail configuration
mail = Mail(app)
app.config['MAIL_SERVER'] = MAIL_SERVER

# DB configuration
db = SQLAlchemy()
DB_URL = 'postgresql+psycopg2://{user}:{pw}@{url}/{db}'.format(user=POSTGRES_USER, pw=POSTGRES_PW, url=POSTGRES_URL,
                                                               db=POSTGRES_DB)
app.config['SECRET_KEY'] = SECRET_KEY
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False  # silence the deprecation warning
db.init_app(app)

# Login Manager configuration
login_manager = LoginManager()
login_manager.login_view = 'show_login'  # show this page if a login is required
login_manager.init_app(app)


# link the Login Manager to the correct user entry
@login_manager.user_loader
def load_user(student_id):
    # since the student_id is just the primary key of our user table, use it in the query for the user
    return Student.query.get(int(student_id))


# --------------------------------------------------------------
# ORM classes
# --------------------------------------------------------------

# ORM model classes, Student table is used for the Login Manager
# for each REST-enabled element, we add marshmallow schemas
# enable a REST API to modify the database contents
def json_error_syntax():
    return jsonify({'error': "wrong JSON format"})


def json_error_permissions():
    return jsonify({'error': "wrong credentials or permissions"})


def json_error_existing():
    return jsonify({'error': "conflict with existing entry"})


class Student(UserMixin, db.Model):
    __tablename__ = "student"
    student_id = db.Column(db.INTEGER, primary_key=True)
    student_name = db.Column(db.VARCHAR(100))
    student_mail = db.Column(db.VARCHAR(100), unique=True)
    student_desc = db.Column(db.VARCHAR(1024))
    student_pass = db.Column(db.VARCHAR(256))
    student_img = db.Column(db.VARCHAR(384))
    student_role = db.Column(db.VARCHAR(20))
    active = db.Column(db.INTEGER, default=0)
    notification = db.Column(db.INTEGER, default=0)
    password_reset = db.Column(db.VARCHAR(100))

    # match the correct row for the Login Manager ID
    def get_id(self):
        return self.student_id

    def __repr__(self):
        return '<Student %s>' % self.student_name


class Invitation(db.Model):
    __tablename__ = "invitation"
    invitation_id = db.Column(db.INTEGER, primary_key=True)
    invitation_code = db.Column(db.VARCHAR(20), unique=True)
    invitation_role = db.Column(db.VARCHAR(20))
    invitation_forever = db.Column(db.INTEGER, default=0)
    invitation_taken = db.Column(db.INTEGER, default=0)

    def __repr__(self):
        return '<Invitation %s>' % self.invitation_id


class Campaign(db.Model):
    __tablename__ = "campaign"
    campaign_id = db.Column(db.INTEGER, primary_key=True)
    student_id = db.Column(db.INTEGER, db.ForeignKey("student.student_id"))
    campaign_name = db.Column(db.VARCHAR(100), unique=True)
    campaign_desc = db.Column(db.VARCHAR(1024))
    campaign_img = db.Column(db.VARCHAR(384))
    public_ind = db.Column(db.INTEGER, default=0)

    def __repr__(self):
        return '<Campaign %s>' % self.campaign_name


class CampaignSchema(marsh.Schema):
    class Meta:
        fields = ("campaign_id", "student_id", "campaign_name", "campaign_desc",
                  "campaign_img", "public_ind")
        model = Campaign


campaign_schema = CampaignSchema()
campaigns_schema = CampaignSchema(many=True)


class CampaignListResource(Resource):
    @staticmethod
    def get():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN, ROLE_USER]):
            campaigns = Campaign.query.all()
            return campaigns_schema.dump(campaigns)
        else:
            campaigns = Campaign.query.filter_by(public_ind=1).all()
            return campaigns_schema.dump(campaigns)

    @staticmethod
    def post():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            if all(s in request.json for s in ('campaign_name', 'campaign_desc',
                                               'campaign_img', 'public_ind')):
                if select_campaign(escape(request.json['campaign_name'])) is None:
                    new_campaign = Campaign(
                        student_id=student.student_id,
                        campaign_name=escape(request.json['campaign_name']),
                        campaign_desc=request.json['campaign_desc'],
                        campaign_img=clean_url(request.json['campaign_img']),
                        public_ind=int(request.json['public_ind'])
                    )
                    db.session.add(new_campaign)
                    db.session.commit()
                    return campaign_schema.dump(new_campaign)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


class CampaignResource(Resource):
    @staticmethod
    def get(campaign_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN, ROLE_USER]):
            campaign = Campaign.query.filter_by(campaign_name=campaign_name).first()
            return campaign_schema.dump(campaign)
        else:
            campaign = Campaign.query.filter_by(campaign_name=campaign_name).filter_by(public_ind=1).first()
            return campaign_schema.dump(campaign)

    @staticmethod
    def patch(campaign_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            campaign = Campaign.query.filter_by(student_id=student.student_id).\
                filter_by(campaign_name=campaign_name).first()
            if campaign and all(s in request.json for s in ('campaign_name', 'campaign_desc',
                                                            'campaign_img', 'public_ind')):
                if (request.json['campaign_name'] == campaign_name or
                        select_campaign(escape(request.json['campaign_name'])) is None):
                    campaign.campaign_name = escape(request.json['campaign_name'])
                    campaign.campaign_desc = request.json['campaign_desc']
                    campaign.campaign_img = clean_url(request.json['campaign_img'])
                    campaign.public_ind = int(request.json['public_ind'])
                    db.session.commit()
                    return campaign_schema.dump(campaign)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()

    @staticmethod
    def delete(campaign_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            campaign = Campaign.query.filter_by(student_id=student.student_id).\
                filter_by(campaign_name=campaign_name).first()
            if campaign:
                db.session.delete(campaign)
                db.session.commit()
                return '', 204
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


api.add_resource(CampaignListResource, APP_PREFIX + '/api/campaigns')
api.add_resource(CampaignResource, APP_PREFIX + '/api/campaigns/<string:campaign_name>')


class Scenario(db.Model):
    __tablename__ = "scenario"
    scenario_id = db.Column(db.INTEGER, primary_key=True)
    student_id = db.Column(db.INTEGER, db.ForeignKey("student.student_id"))
    campaign_id = db.Column(db.INTEGER, db.ForeignKey("campaign.campaign_id"))
    scenario_name = db.Column(db.VARCHAR(100), unique=True)
    scenario_desc = db.Column(db.VARCHAR(1024))
    scenario_brief = db.Column(db.VARCHAR(1024))
    scenario_img = db.Column(db.VARCHAR(384))
    legitimate = db.Column(db.INTEGER, default=0)

    def __repr__(self):
        return '<Scenario %s>' % self.scenario_name


class ScenarioSchema(marsh.Schema):
    class Meta:
        fields = ("scenario_id", "student_id", "campaign_id", "scenario_name", "scenario_desc", "scenario_brief",
                  "scenario_img", "legitimate")
        model = Scenario


scenario_schema = ScenarioSchema()
scenarios_schema = ScenarioSchema(many=True)


class ScenarioListResource(Resource):
    @staticmethod
    def get():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN, ROLE_USER]):
            scenarios = Scenario.query.all()
            return scenarios_schema.dump(scenarios)
        else:
            active_campaigns = Campaign.query.filter_by(public_ind=1).all()
            scenarios = Scenario.query.filter(Scenario.campaign_id.in_(extract_campaign_id(active_campaigns))).all()
            return scenarios_schema.dump(scenarios)

    @staticmethod
    def post():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            if all(s in request.json for s in ('campaign_id', 'scenario_name', 'scenario_desc', 'scenario_brief',
                                               'scenario_img', 'legitimate')):
                if select_scenario(escape(request.json['scenario_name'])) is None:
                    new_scenario = Scenario(
                        student_id=student.student_id,
                        campaign_id=int(escape(request.json['campaign_id'])),
                        scenario_name=escape(request.json['scenario_name']),
                        scenario_desc=request.json['scenario_desc'],
                        scenario_brief=request.json['scenario_brief'],
                        scenario_img=clean_url(request.json['scenario_img']),
                        legitimate=int(request.json['legitimate'])
                    )
                    db.session.add(new_scenario)
                    db.session.commit()
                    return scenario_schema.dump(new_scenario)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


class ScenarioResource(Resource):
    @staticmethod
    def get(scenario_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN, ROLE_USER]):
            scenario = Scenario.query.filter_by(scenario_name=scenario_name).first()
            return scenario_schema.dump(scenario)
        else:
            active_campaigns = Campaign.query.filter_by(public_ind=1).all()
            scenario = Scenario.query.filter(Scenario.campaign_id.in_(extract_campaign_id(active_campaigns))).filter_by(
                scenario_name=scenario_name).first()
            return scenario_schema.dump(scenario)

    @staticmethod
    def patch(scenario_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            scenario = Scenario.query.filter_by(student_id=student.student_id).\
                filter_by(scenario_name=scenario_name).first()
            if scenario and all(s in request.json for s in ('campaign_id', 'scenario_name', 'scenario_desc',
                                                            'scenario_brief', 'scenario_img', 'legitimate')):
                if (request.json['scenario_name'] == scenario_name or
                        select_scenario(escape(request.json['scenario_name'])) is None):
                    scenario.campaign_id = int(escape(request.json['campaign_id'])),
                    scenario.scenario_name = escape(request.json['scenario_name']),
                    scenario.scenario_desc = request.json['scenario_desc'],
                    scenario.scenario_brief = request.json['scenario_brief'],
                    scenario.scenario_img = clean_url(request.json['scenario_img']),
                    scenario.legitimate = int(request.json['legitimate'])
                    db.session.commit()
                    return scenario_schema.dump(scenario)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()

    @staticmethod
    def delete(scenario_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            scenario = Scenario.query.filter_by(student_id=student.student_id).\
                filter_by(scenario_name=scenario_name).first()
            if scenario:
                db.session.delete(scenario)
                db.session.commit()
                return '', 204
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


api.add_resource(ScenarioListResource, APP_PREFIX + '/api/scenarios')
api.add_resource(ScenarioResource, APP_PREFIX + '/api/scenarios/<string:scenario_name>')


class Area(db.Model):
    __tablename__ = "area"
    area_id = db.Column(db.INTEGER, primary_key=True)
    student_id = db.Column(db.INTEGER, db.ForeignKey("student.student_id"))
    scenario_id = db.Column(db.INTEGER, db.ForeignKey("scenario.scenario_id"))
    start_x = db.Column(db.INTEGER, default=10)
    start_y = db.Column(db.INTEGER, default=10)
    end_x = db.Column(db.INTEGER, default=20)
    end_y = db.Column(db.INTEGER, default=20)
    points = db.Column(db.INTEGER, default=0)
    hover = db.Column(db.VARCHAR(384))

    def __repr__(self):
        return '<Area %s>' % self.area_id


class AreaSchema(marsh.Schema):
    class Meta:
        fields = ("area_id", "student_id", "scenario_id", "start_x", "start_y", "end_x", "end_y", "points", "hover")
        model = Area


area_schema = AreaSchema()
areas_schema = AreaSchema(many=True)


class AreaListResource(Resource):
    @staticmethod
    def get():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            areas = Area.query.all()
            return areas_schema.dump(areas)
        else:
            return json_error_permissions()

    @staticmethod
    def post():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            if all(s in request.json for s in ('scenario_id', 'start_x', 'start_y', 'end_x', 'end_y', 'points',
                                               'hover')):
                new_area = Area(
                    student_id=student.student_id,
                    scenario_id=int(escape(request.json['scenario_id'])),
                    start_x=int(escape(request.json['start_x'])),
                    start_y=int(escape(request.json['start_y'])),
                    end_x=int(escape(request.json['end_x'])),
                    end_y=int(escape(request.json['end_y'])),
                    points=int(escape(request.json['points'])),
                    hover=escape(request.json['hover'])
                )
                db.session.add(new_area)
                db.session.commit()
                return area_schema.dump(new_area)
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


class AreaResource(Resource):
    @staticmethod
    def get(area_id):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            area = Area.query.filter_by(area_id=area_id).first()
            return area_schema.dump(area)
        else:
            return json_error_permissions()

    @staticmethod
    def patch(area_id):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            area = Area.query.filter_by(student_id=student.student_id).\
                filter_by(area_id=area_id).first()
            if area and all(s in request.json for s in ('start_x', 'start_y', 'end_x', 'end_y', 'points', 'hover')):
                area.start_x = int(escape(request.json['start_x'])),
                area.start_y = int(escape(request.json['start_y'])),
                area.end_x = int(escape(request.json['end_x'])),
                area.end_y = int(escape(request.json['end_y'])),
                area.points = int(escape(request.json['points'])),
                area.hover = escape(request.json['hover'])
                db.session.commit()
                return area_schema.dump(area)
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()

    @staticmethod
    def delete(area_id):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            area = Area.query.filter_by(student_id=student.student_id).\
                filter_by(area_id=area_id).first()
            if area:
                db.session.delete(area)
                db.session.commit()
                return '', 204
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


api.add_resource(AreaListResource, APP_PREFIX + '/api/areas')
api.add_resource(AreaResource, APP_PREFIX + '/api/areas/<int:area_id>')


class Category(db.Model):
    __tablename__ = "category"
    category_id = db.Column(db.INTEGER, primary_key=True)
    student_id = db.Column(db.INTEGER, db.ForeignKey("student.student_id"))
    category_name = db.Column(db.VARCHAR(100), unique=True)

    def __repr__(self):
        return '<Category %s>' % self.category_name


class CategorySchema(marsh.Schema):
    class Meta:
        fields = ("category_id", "student_id", "category_name")
        model = Category


category_schema = CategorySchema()
categories_schema = CategorySchema(many=True)


class CategoryListResource(Resource):
    @staticmethod
    def get():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            categories = Category.query.all()
            return categories_schema.dump(categories)
        else:
            return json_error_permissions()

    @staticmethod
    def post():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            if all(s in request.json for s in ('category_name', 'sample')):
                if select_category(escape(request.json['category_name'])) is None:
                    new_category = Category(
                        student_id=student.student_id,
                        category_name=escape(request.json['category_name'])
                    )
                    db.session.add(new_category)
                    db.session.commit()
                    return category_schema.dump(new_category)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


class CategoryResource(Resource):
    @staticmethod
    def get(category_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            category = Category.query.filter_by(category_name=category_name).first()
            return category_schema.dump(category)
        else:
            return json_error_permissions()

    @staticmethod
    def patch(category_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            category = Category.query.filter_by(student_id=student.student_id).\
                filter_by(category_name=category_name).first()
            if category and all(s in request.json for s in ('category_name', 'sample')):
                if select_category(escape(request.json['category_name'])) is None:
                    category.category_name = escape(request.json['category_name'])
                    db.session.commit()
                    return category_schema.dump(category)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()

    @staticmethod
    def delete(category_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            category = Category.query.filter_by(student_id=student.student_id).\
                filter_by(category_name=category_name).first()
            if category:
                db.session.delete(category)
                db.session.commit()
                return '', 204
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


api.add_resource(CategoryListResource, APP_PREFIX + '/api/categories')
api.add_resource(CategoryResource, APP_PREFIX + '/api/categories/<string:category_name>')


class Language(db.Model):
    __tablename__ = "language"
    language_id = db.Column(db.INTEGER, primary_key=True)
    student_id = db.Column(db.INTEGER, db.ForeignKey("student.student_id"))
    language_name = db.Column(db.VARCHAR(100), unique=True)

    def __repr__(self):
        return '<Language %s>' % self.language_name


class LanguageSchema(marsh.Schema):
    class Meta:
        fields = ("language_id", "student_id", "language_name")
        model = Language


language_schema = LanguageSchema()
languages_schema = LanguageSchema(many=True)


class LanguageListResource(Resource):
    @staticmethod
    def get():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            languages = Language.query.all()
            return languages_schema.dump(languages)
        else:
            return json_error_permissions()

    @staticmethod
    def post():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            if all(s in request.json for s in ('language_name', 'sample')):
                if select_language(escape(request.json['language_name'])) is None:
                    new_language = Language(
                        student_id=student.student_id,
                        language_name=escape(request.json['language_name'])
                    )
                    db.session.add(new_language)
                    db.session.commit()
                    return language_schema.dump(new_language)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


class LanguageResource(Resource):
    @staticmethod
    def get(language_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            language = Language.query.filter_by(language_name=language_name).first()
            return language_schema.dump(language)
        else:
            return json_error_permissions()

    @staticmethod
    def patch(language_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            language = Language.query.filter_by(student_id=student.student_id).\
                filter_by(language_name=language_name).first()
            if language and all(s in request.json for s in ('language_name', 'sample')):
                if select_language(escape(request.json['language_name'])) is None:
                    language.language_name = escape(request.json['language_name'])
                    db.session.commit()
                    return language_schema.dump(language)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()

    @staticmethod
    def delete(language_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            language = Language.query.filter_by(student_id=student.student_id).\
                filter_by(language_name=language_name).first()
            if language:
                db.session.delete(language)
                db.session.commit()
                return '', 204
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


api.add_resource(LanguageListResource, APP_PREFIX + '/api/languages')
api.add_resource(LanguageResource, APP_PREFIX + '/api/languages/<string:language_name>')


class Lesson(db.Model):
    __tablename__ = "lesson"
    lesson_id = db.Column(db.INTEGER, primary_key=True)
    student_id = db.Column(db.INTEGER, db.ForeignKey("student.student_id"))
    lesson_cat = db.Column(db.INTEGER, db.ForeignKey("category.category_id"))
    lesson_lang = db.Column(db.INTEGER, db.ForeignKey("language.language_id"))
    lesson_name = db.Column(db.VARCHAR(100))
    lesson_mov = db.Column(db.VARCHAR(384))

    def __repr__(self):
        return '<Lesson %s>' % self.lesson_name


class LessonSchema(marsh.Schema):
    class Meta:
        fields = ("lesson_id", "student_id", "lesson_cat", "lesson_lang", "lesson_name",
                  "lesson_mov")
        model = Lesson


lesson_schema = LessonSchema()
lessons_schema = LessonSchema(many=True)


class LessonListResource(Resource):
    @staticmethod
    def get():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            lessons = Lesson.query.all()
            return lessons_schema.dump(lessons)
        else:
            return json_error_permissions()

    @staticmethod
    def post():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            if all(s in request.json for s in ('lesson_cat', 'lesson_lang', 'lesson_name', 'lesson_mov')):
                if select_lesson(int(escape(request.json['lesson_lang'])), escape(request.json['lesson_name'])) is None:
                    new_lesson = Lesson(
                        student_id=student.student_id,
                        lesson_cat=int(escape(request.json['lesson_cat'])),
                        lesson_lang=int(escape(request.json['lesson_lang'])),
                        lesson_name=escape(request.json['lesson_name']),
                        lesson_mov=clean_url(request.json['lesson_mov'])
                    )
                    db.session.add(new_lesson)
                    db.session.commit()
                    return lesson_schema.dump(new_lesson)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


class LessonResource(Resource):
    @staticmethod
    def get(lesson_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            lesson = Lesson.query.filter_by(lesson_name=lesson_name).first()
            return lesson_schema.dump(lesson)
        else:
            return json_error_permissions()

    @staticmethod
    def patch(lesson_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            lesson = Lesson.query.filter_by(student_id=student.student_id).\
                filter_by(lesson_name=lesson_name).first()
            if lesson and all(s in request.json for s in ('lesson_cat', 'lesson_lang', 'lesson_name', 'lesson_mov')):
                if (request.json['lesson_name'] == lesson_name or
                        select_lesson(int(escape(request.json['lesson_lang'])), escape(request.json['lesson_name']))
                        is None):
                    lesson.lesson_cat = int(escape(request.json['lesson_cat'])),
                    lesson.lesson_lang = int(escape(request.json['lesson_lang'])),
                    lesson.lesson_name = escape(request.json['lesson_name']),
                    lesson.lesson_mov = clean_url(request.json['lesson_mov'])
                    db.session.commit()
                    return lesson_schema.dump(lesson)
                else:
                    return json_error_existing()
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()

    @staticmethod
    def delete(lesson_name):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            lesson = Lesson.query.filter_by(student_id=student.student_id).\
                filter_by(lesson_name=lesson_name).first()
            if lesson:
                db.session.delete(lesson)
                db.session.commit()
                return '', 204
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


api.add_resource(LessonListResource, APP_PREFIX + '/api/lessons')
api.add_resource(LessonResource, APP_PREFIX + '/api/lessons/<string:lesson_name>')


class Quiz(db.Model):
    __tablename__ = "quiz"
    quiz_id = db.Column(db.INTEGER, primary_key=True)
    student_id = db.Column(db.INTEGER, db.ForeignKey("student.student_id"))
    quiz_cat = db.Column(db.INTEGER, db.ForeignKey("category.category_id"))
    quiz_lang = db.Column(db.INTEGER, db.ForeignKey("language.language_id"))
    quiz_question = db.Column(db.VARCHAR(1024))
    answer_first = db.Column(db.VARCHAR(256))
    answer_second = db.Column(db.VARCHAR(256))
    answer_third = db.Column(db.VARCHAR(256))
    answer_fourth = db.Column(db.VARCHAR(256))
    quiz_solution = db.Column(db.INTEGER, default=1)
    points = db.Column(db.INTEGER, default=0)

    def __repr__(self):
        return '<Quiz %s>' % self.quiz_question


class QuizSchema(marsh.Schema):
    class Meta:
        fields = ("quiz_id", "student_id", "quiz_cat", "quiz_lang", "quiz_question", "answer_first", "answer_second",
                  "answer_third", "answer_fourth", "quiz_solution", "points")
        model = Quiz


quiz_schema = QuizSchema()
quizzes_schema = QuizSchema(many=True)


class QuizListResource(Resource):
    @staticmethod
    def get():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            quizzes = Quiz.query.all()
            return quizzes_schema.dump(quizzes)
        else:
            return json_error_permissions()

    @staticmethod
    def post():
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            if all(s in request.json for s in ('quiz_cat', 'quiz_lang', 'quiz_question', 'answer_first',
                                               'answer_second', 'answer_third', 'answer_fourth', 'quiz_solution',
                                               'points')):
                new_quiz = Quiz(
                    student_id=student.student_id,
                    quiz_cat=int(escape(request.json['quiz_cat'])),
                    quiz_lang=int(escape(request.json['quiz_lang'])),
                    quiz_question=escape(request.json['quiz_question']),
                    answer_first=escape(request.json['answer_first']),
                    answer_second=escape(request.json['answer_second']),
                    answer_third=escape(request.json['answer_third']),
                    answer_fourth=escape(request.json['answer_fourth']),
                    quiz_solution=int(escape(request.json['quiz_solution'])),
                    points=int(escape(request.json['points'])),
                )
                db.session.add(new_quiz)
                db.session.commit()
                return quiz_schema.dump(new_quiz)
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


class QuizResource(Resource):
    @staticmethod
    def get(quiz_id):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            quiz = Quiz.query.filter_by(quiz_id=quiz_id).first()
            return quiz_schema.dump(quiz)
        else:
            return json_error_permissions()

    @staticmethod
    def patch(quiz_id):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            quiz = Quiz.query.filter_by(student_id=student.student_id).\
                filter_by(quiz_id=quiz_id).first()
            if quiz and all(s in request.json for s in ('quiz_cat', 'quiz_lang', 'quiz_question', 'answer_first',
                                                        'answer_second', 'answer_third', 'answer_fourth',
                                                        'quiz_solution', 'points')):
                quiz.quiz_cat = int(escape(request.json['quiz_cat'])),
                quiz.quiz_lang = int(escape(request.json['quiz_lang'])),
                quiz.quiz_question = escape(request.json['quiz_question']),
                quiz.answer_first = escape(request.json['answer_first']),
                quiz.answer_second = escape(request.json['answer_second']),
                quiz.answer_third = escape(request.json['answer_third']),
                quiz.answer_fourth = escape(request.json['answer_fourth']),
                quiz.quiz_solution = int(escape(request.json['quiz_solution'])),
                quiz.points = int(escape(request.json['points']))
                db.session.commit()
                return quiz_schema.dump(quiz)
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()

    @staticmethod
    def delete(quiz_id):
        if AuthChecker().check(request.authorization, [ROLE_ADMIN]):
            student = Student.query.filter_by(student_mail=request.authorization['username']).first()
            quiz = Quiz.query.filter_by(student_id=student.student_id).\
                filter_by(quiz_id=quiz_id).first()
            if quiz:
                db.session.delete(quiz)
                db.session.commit()
                return '', 204
            else:
                return json_error_syntax()
        else:
            return json_error_permissions()


api.add_resource(QuizListResource, APP_PREFIX + '/api/quizzes')
api.add_resource(QuizResource, APP_PREFIX + '/api/quizzes/<int:quiz_id>')


class QuizScore(db.Model):
    __tablename__ = "quiz_score"
    quiz_score_id = db.Column(db.INTEGER, primary_key=True)
    student_id = db.Column(db.INTEGER, db.ForeignKey("student.student_id"))
    quiz_id = db.Column(db.INTEGER, db.ForeignKey("quiz.quiz_id"))
    points = db.Column(db.INTEGER, default=0)

    def __repr__(self):
        return '<Quiz Score %s>' % self.quiz_score_id


class ScenarioScore(db.Model):
    __tablename__ = "scenario_score"
    scenario_score_id = db.Column(db.INTEGER, primary_key=True)
    student_id = db.Column(db.INTEGER, db.ForeignKey("student.student_id"))
    scenario_id = db.Column(db.INTEGER, db.ForeignKey("scenario.scenario_id"))
    points = db.Column(db.INTEGER, default=0)

    def __repr__(self):
        return '<Scenario Score %s>' % self.scenario_score_id


# --------------------------------------------------------------
# Internal functions
# --------------------------------------------------------------

# S3 storage helper functions
def upload_file(bucket: str, object_name: str, file_name: str) -> str:
    s3_client = boto3.client('s3', endpoint_url=S3_ENDPOINT)
    response = s3_client.upload_file(file_name, bucket, object_name)
    return response


def download_file(bucket: str, object_name: str, file_name: str) -> str:
    s3 = boto3.resource('s3', endpoint_url=S3_ENDPOINT)
    s3.Bucket(bucket).download_file(object_name, file_name)
    return file_name


def delete_file(bucket: str, object_name: str):
    s3 = boto3.resource('s3', endpoint_url=S3_ENDPOINT)
    s3.Object(bucket, object_name).delete()


def rename_file(bucket: str, object_name_new: str, object_name_old: str):
    s3 = boto3.resource('s3', endpoint_url=S3_ENDPOINT)
    s3.Object(bucket, object_name_new).copy_from(CopySource=f"{bucket}/{object_name_old}")
    s3.Object(bucket, object_name_old).delete()


def list_files(bucket: str, folder_name: str) -> list[str]:
    s3 = boto3.client('s3', endpoint_url=S3_ENDPOINT)
    contents = []
    for item in s3.list_objects(Bucket=bucket)['Contents']:
        if item['Key'].startswith(f"{folder_name}") and item['Key'] != f"{folder_name}/":
            contents.append(item['Key'].replace(f"{folder_name}/", ""))
    return contents


def get_size(bucket: str, path: str) -> int:
    s3 = boto3.resource('s3', endpoint_url=S3_ENDPOINT)
    my_bucket = s3.Bucket(bucket)
    total_size = 0

    for obj in my_bucket.objects.filter(Prefix=path):
        total_size = total_size + obj.size

    return total_size


def get_all_size(bucket: str) -> dict:
    s3 = boto3.client('s3', endpoint_url=S3_ENDPOINT)
    top_level_folders = dict()
    for key in s3.list_objects(Bucket=bucket)['Contents']:
        folder = key['Key'].split('/')[0]
        if folder in top_level_folders:
            top_level_folders[folder] += key['Size']
        else:
            top_level_folders[folder] = key['Size']

    return top_level_folders


# File upload helper
def upload_helper(s3_folder: str, space_used: int, filename: str, file: forms.FileField):
    if allowed_file(filename) and space_used < 100:
        local_folder_name = f"{UPLOAD_FOLDER}/{s3_folder}"
        local_file = os.path.join(local_folder_name, filename)
        remote_file = f"{s3_folder}/{filename}"
        if not os.path.exists(local_folder_name):
            os.makedirs(local_folder_name)
        file.data.save(local_file)
        upload_file(S3_BUCKET, remote_file, local_file)


# URL sanitization
def clean_url(url: str) -> str:
    return re.sub('[^-A-Za-z0-9+&@#/%?=~_|!:,.;()]', '', url)


# Path traversal prevention
def allowed_file(filename: str) -> bool:
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# check if the basic authentication is valid, used for API calls
class AuthChecker:
    @staticmethod
    def check(auth, role):
        if auth:
            student_mail = auth['username']
            student_pass = auth['password']
            student = Student.query.filter_by(active=1).filter_by(student_mail=student_mail).first()

            if student and check_password_hash(student.student_pass, student_pass) and student.student_role in role:
                return True
        return False


# Sitemap page
@ext.register_generator
def index():
    # Not needed if you set SITEMAP_INCLUDE_RULES_WITHOUT_PARAMS=True
    yield 'show_index', {}, SITEMAP_DATE, 'monthly'
    yield 'show_lessons', {'language': 0}, SITEMAP_DATE, 'weekly'
    yield 'show_campaigns', {}, SITEMAP_DATE, 'weekly'
    # campaigns = Campaign.query.filter_by(public_ind=1).order_by(Campaign.campaign_name.asc()).all()
    # for campaign in campaigns:
    #      yield 'show_campaign', {'campaign_name': campaign.campaign_name}, SITEMAP_DATE, 'weekly'
    yield 'show_scenarios', {}, SITEMAP_DATE, 'weekly'
    # scenarios = (Scenario.query.filter(Scenario.campaign_id.in_(extract_campaign_id(campaigns))).
    #              order_by(Scenario.scenario_name.asc()).all())
    # for scenario in scenarios:
    #     yield 'show_scenario', {'scenario_name': scenario.scenario_name}, SITEMAP_DATE, 'weekly'
    yield 'show_release', {}, SITEMAP_DATE, 'monthly'
    yield 'show_privacy', {}, SITEMAP_DATE, 'monthly'
    yield 'show_stats', {}, SITEMAP_DATE, 'weekly'


# Send an e-mail
def send_mail(recipients: list[str], mail_header: str, mail_body: str):
    if MAIL_ENABLE == 1:
        msg = Message(mail_header,
                      sender=MAIL_SENDER,
                      recipients=recipients)
        msg.body = mail_body
        mail.send(msg)


def send_massmail(mail_header: str, mail_body: str):
    if MAIL_ENABLE == 1:
        students = Student.query.filter_by(active=1).order_by(Student.student_name.asc())
        recipients = list()
        bcc = list()
        recipients.append(MAIL_SENDER)
        for student in students:
            if student.notification == 1:
                bcc.append(student.student_mail)
        msg = Message(mail_header,
                      sender=MAIL_SENDER,
                      recipients=recipients,
                      bcc=bcc)
        msg.body = mail_body
        mail.send(msg)


# Internal logging
def log_entry(operation: str, parameters: list = None):
    if parameters is None:
        parameters = ["none"]
    if LOG_ENABLE == 1:
        logf = open(LOG_FILE, "a")  # append mode
        logf.write("Operation: " + operation + "\n")
        logf.close()
    elif LOG_ENABLE == 2:
        logf = open(LOG_FILE, "a")  # append mode
        logf.write("Operation: " + operation + ", Parameters: " + ', '.join(parameters) + "\n")
        logf.close()


# Internal helpers - return choices list used in HTML select elements
def get_file_choices(folder: str) -> list[str]:
    image_choices = list_files(S3_BUCKET, folder)
    image_choices.insert(0, "No Image")
    return image_choices


def get_campaign_choices(campaigns: list[Campaign]) -> list[tuple[int, str]]:
    campaigns_choices = list()
    for campaign in campaigns:
        campaigns_choices.append((campaign.campaign_id, campaign.campaign_name))
    return campaigns_choices


def extract_campaign_id(campaigns: list[Campaign]) -> list[int]:
    id_list = list()
    for campaign in campaigns:
        id_list.append(campaign.campaign_id)
    return id_list


# Internal helpers - return database content based on given criteria
def select_campaigns() -> list[Campaign]:
    if current_user.is_authenticated and current_user.student_role in [ROLE_ADMIN, ROLE_USER]:
        campaigns = Campaign.query.order_by(Campaign.campaign_name.asc()).all()
    else:
        campaigns = Campaign.query.filter_by(public_ind=1).order_by(Campaign.campaign_name.asc()).all()
    return campaigns


def select_campaign(campaign_name: str) -> Campaign:
    if current_user.is_authenticated and current_user.student_role in [ROLE_ADMIN, ROLE_USER]:
        campaign = Campaign.query.filter_by(campaign_name=campaign_name).first()
    else:
        campaign = Campaign.query.filter_by(public_ind=1).filter_by(campaign_name=campaign_name).first()
    return campaign


def select_scenarios() -> list[Scenario]:
    if current_user.is_authenticated and current_user.student_role in [ROLE_ADMIN, ROLE_USER]:
        scenarios = Scenario.query.order_by(Scenario.scenario_name.asc()).all()
    else:
        active_campaigns = Campaign.query.filter_by(public_ind=1).all()
        scenarios = (Scenario.query.filter(Scenario.campaign_id.in_(extract_campaign_id(active_campaigns))).
                     order_by(Scenario.scenario_name.asc()).all())
    return scenarios


def select_scenarios_cid(campaign_id: int) -> list[Scenario]:
    if current_user.is_authenticated and current_user.student_role in [ROLE_ADMIN, ROLE_USER]:
        scenarios = Scenario.query.filter_by(campaign_id=campaign_id).order_by(Scenario.scenario_name.asc()).all()
    else:
        active_campaigns = Campaign.query.filter_by(public_ind=1).all()
        scenarios = (Scenario.query.filter(Scenario.campaign_id.in_(extract_campaign_id(active_campaigns))).
                     filter_by(campaign_id=campaign_id).order_by(Scenario.scenario_name.asc()).all())
    return scenarios


def select_scenario(scenario_name: str) -> Scenario:
    if current_user.is_authenticated and current_user.student_role in [ROLE_ADMIN, ROLE_USER]:
        scenario = Scenario.query.filter_by(scenario_name=scenario_name).first()
    else:
        active_campaigns = Campaign.query.filter_by(public_ind=1).all()
        scenario = (Scenario.query.filter(Scenario.campaign_id.in_(extract_campaign_id(active_campaigns))).
                    filter_by(scenario_name=scenario_name).first())
    return scenario


def select_categories() -> list[Category]:
    categories = Category.query.order_by(Category.category_name.asc()).all()
    return categories


def select_category(category_name: str) -> Category:
    category = Category.query.filter_by(category_name=category_name).first()
    return category


def select_languages() -> list[Language]:
    languages = Language.query.order_by(Language.language_name.asc()).all()
    return languages


def select_language(language_name: str) -> Language:
    language = Language.query.filter_by(language_name=language_name).first()
    return language


def select_lessons(language: int = None) -> list[Lesson]:
    if language is None:
        lessons = Lesson.query.order_by(Lesson.lesson_cat.asc()).order_by(Lesson.lesson_lang.asc()).all()
    else:
        lessons = Lesson.query.filter_by(lesson_lang=language).order_by(Lesson.lesson_cat.asc()).all()
    return lessons


def select_lesson(language: int, lesson_name: str) -> Lesson:
    lesson = Lesson.query.filter_by(lesson_lang=language).filter_by(lesson_name=lesson_name).first()
    return lesson


def select_quizzes(language: int = None) -> list[Quiz]:
    if language is None:
        quizzes = Quiz.query.order_by(Quiz.quiz_cat.asc()).order_by(Quiz.quiz_lang.asc()).all()
    else:
        quizzes = Quiz.query.filter_by(quiz_lang=language).order_by(Quiz.quiz_cat.asc()).all()
    return quizzes


def select_quiz(language: int, quiz_id: int) -> Quiz:
    quiz = Quiz.query.filter_by(quiz_lang=language).filter_by(quiz_id=quiz_id).first()
    return quiz


def select_quiz_scores() -> list[QuizScore]:
    if current_user.is_authenticated and current_user.student_role in [ROLE_ADMIN, ROLE_USER]:
        quiz_scores = QuizScore.query.filter_by(student_id=current_user.student_id).all()
    else:
        quiz_scores = QuizScore.query.filter_by(quiz_id=-1).all()
    return quiz_scores


def select_scenario_scores() -> list[ScenarioScore]:
    if current_user.is_authenticated and current_user.student_role in [ROLE_ADMIN, ROLE_USER]:
        scenario_scores = (ScenarioScore.query.filter_by(student_id=current_user.student_id).all())
    else:
        scenario_scores = (ScenarioScore.query.filter_by(scenario_id=-1).all())
    return scenario_scores


# Internal helpers - update database content
def update_quiz_score(quiz_id: int, score: int):
    if current_user.is_authenticated and current_user.student_role in [ROLE_ADMIN, ROLE_USER]:
        quiz_score = QuizScore.query.filter_by(student_id=current_user.student_id).filter_by(quiz_id=quiz_id).first()
        if quiz_score:
            if quiz_score.points < score:
                quiz_score.points = score
                db.session.commit()
        else:
            new_quiz_score = QuizScore()
            new_quiz_score.student_id = current_user.student_id
            new_quiz_score.quiz_id = quiz_id
            new_quiz_score.points = score
            db.session.add(new_quiz_score)
            db.session.commit()


def update_scenario_score(scenario_id: int, score: int):
    if current_user.is_authenticated and current_user.student_role in [ROLE_ADMIN, ROLE_USER]:
        scenario_score = (ScenarioScore.query.filter_by(student_id=current_user.student_id).
                          filter_by(scenario_id=scenario_id).first())
        if scenario_score:
            if scenario_score.points < score:
                scenario_score.points = score
                db.session.commit()
        else:
            new_scenario_score = ScenarioScore()
            new_scenario_score.student_id = current_user.student_id
            new_scenario_score.scenario_id = scenario_id
            new_scenario_score.points = score
            db.session.add(new_scenario_score)
            db.session.commit()


# Internal helpers - style manager
def update_style(style: str):
    session['style'] = style


# Internal helpers - language selector
def update_language(language: int):
    session['language'] = language


# Internal helper - map form data to ORM and vice versa
def map_form_to_campaign(campaign: Campaign, campaign_form: CampaignForm):
    campaign.campaign_name = escape(campaign_form.name.data)
    campaign.campaign_desc = campaign_form.description.data
    campaign.campaign_img = clean_url(campaign_form.image.data)
    campaign.public_ind = int(campaign_form.public.data)


def map_campaign_to_form(campaign: Campaign, campaign_form: CampaignForm):
    campaign_form.name.default = campaign.campaign_name
    campaign_form.description.default = campaign.campaign_desc
    campaign_form.image.default = campaign.campaign_img
    campaign_form.public.default = campaign.public_ind


def map_campaign_defaults(campaign_form: CampaignForm, use_alternative: bool):
    if use_alternative:
        campaign_form.name.default = campaign_form.name.data + FILE_ALT_ENDING
        campaign_form.name.errors.append(FILE_ALT_WARNING)
    else:
        campaign_form.name.default = campaign_form.name.data
    campaign_form.description.default = campaign_form.description.data
    campaign_form.image.default = campaign_form.image.data


def map_form_to_scenario(scenario: Scenario, scenario_form: ScenarioForm):
    scenario.scenario_name = escape(scenario_form.name.data)
    scenario.scenario_desc = scenario_form.description.data
    scenario.scenario_brief = scenario_form.briefing.data
    scenario.scenario_img = clean_url(scenario_form.image.data)
    scenario.student_id = current_user.student_id
    scenario.campaign_id = int(escape(scenario_form.campaign.data))
    scenario.legitimate = int(scenario_form.legitimate.data)


def map_scenario_to_form(scenario: Scenario, scenario_form: ScenarioForm):
    scenario_form.name.default = scenario.scenario_name
    scenario_form.description.default = scenario.scenario_desc
    scenario_form.briefing.default = scenario.scenario_brief
    scenario_form.image.default = scenario.scenario_img
    scenario_form.campaign.default = scenario.campaign_id
    scenario_form.legitimate.default = int(scenario.legitimate)


def map_scenario_defaults(scenario_form: ScenarioForm, use_alternative: bool):
    if use_alternative:
        scenario_form.name.default = scenario_form.name.data + FILE_ALT_ENDING
        scenario_form.name.errors.append(FILE_ALT_WARNING)
    else:
        scenario_form.name.default = scenario_form.name.data
    scenario_form.description.default = scenario_form.description.data
    scenario_form.image.default = scenario_form.image.data
    scenario_form.campaign.default = scenario_form.campaign.data
    scenario_form.legitimate.default = scenario_form.legitimate.data


def map_form_to_area(area: Area, area_form: AreaForm, scenario_id: int):
    area.student_id = current_user.student_id
    area.scenario_id = scenario_id
    area.start_x = escape(area_form.start_x.data)
    area.start_y = escape(area_form.start_y.data)
    area.end_x = escape(area_form.end_x.data)
    area.end_y = escape(area_form.end_y.data)
    area.points = escape(area_form.points.data)
    area.hover = escape(area_form.hover.data)


def map_area_defaults(area_form: AreaForm):
    area_form.start_x.default = area_form.start_x.data
    area_form.start_y.default = area_form.start_y.data
    area_form.end_x.default = area_form.end_x.data
    area_form.end_y.default = area_form.end_y.data
    area_form.points.default = area_form.points.data
    area_form.hover.default = area_form.hover.data


# --------------------------------------------------------------
# Flask entry pages
# --------------------------------------------------------------

# Show site index
@app.route(APP_PREFIX + '/web/', methods=['GET'])
def show_index():
    return render_template('index.html')


# Show error page  - for all "hard" crashes a mail is sent to the site admin
@app.route(APP_PREFIX + '/web/error', methods=['GET'])
def show_error():
    return render_template('error.html')


# Force user log-in and return to the site index afterward
@app.route(APP_PREFIX + '/web/logged', methods=['GET'])
@login_required
def show_logged():
    return redirect(url_for('show_index'))


# Show user log-in page
@app.route(APP_PREFIX + '/web/login', methods=['GET', 'POST'])
def show_login():
    login_form = LoginForm()
    if request.method == 'POST' and login_form.validate_on_submit():
        student_mail = escape(login_form.email.data)
        student_pass = login_form.password.data
        remember = bool(escape(login_form.remember.data))
        student = Student.query.filter_by(active=1).filter_by(student_mail=student_mail).first()

        if not student or not check_password_hash(student.student_pass, student_pass):
            log_entry("Login Failure", [student_mail])

            return redirect(url_for('show_login'))
        else:
            if student.student_role == ROLE_ADMIN:
                update_style("main_admin.css")
            else:
                update_style("main.css")

            login_user(student, remember=remember)
            log_entry("Login Success", [student_mail])

            return redirect(url_for('show_index'))
    else:
        login_form.email.default = escape(login_form.email.data)
        login_form.remember.default = escape(login_form.remember.data)
        login_form.process()
        return render_template('login.html', login_form=login_form)


# Log out user and return to the site index afterward
@app.route(APP_PREFIX + '/web/logout', methods=['GET'])
def show_logout():
    update_style("main.css")
    update_language(0)
    logout_user()
    return redirect(url_for('show_index'))


# Show user password reset page
@app.route(APP_PREFIX + '/web/password', methods=['GET', 'POST'])
def show_password():
    password_form = PasswordForm()
    if request.method == 'POST' and password_form.validate_on_submit():
        if MAIL_ENABLE == 1:
            student_email = escape(password_form.email.data)

            student = Student.query.filter_by(active=1).filter_by(student_mail=student_email).first()
            recipients = list()
            if student:
                random_hash = ''.join(random.sample(string.ascii_letters + string.digits, 32))
                student.password_reset = random_hash
                db.session.commit()

                recipients.append(student.student_mail)
                msg = Message("Password Reset Link",
                              sender=MAIL_SENDER,
                              recipients=recipients
                              )
                msg.body = "Reset your password here: " + WWW_SERVER + url_for('show_password_reset',
                                                                               random_hash=random_hash)
                mail.send(msg)
        return redirect(url_for('show_index'))
    else:
        return render_template('password.html', password_form=password_form)


# Show user password reset page
@app.route(APP_PREFIX + '/web/reset_password/<string:random_hash>', methods=['GET', 'POST'])
def show_password_reset(random_hash):
    password_reset_form = PasswordResetForm()
    if request.method == 'POST' and password_reset_form.validate_on_submit() and len(random_hash) > 30:
        student = Student.query.filter_by(active=1).filter_by(password_reset=random_hash).first()
        if student:
            student.student_pass = generate_password_hash(password_reset_form.password.data, method='pbkdf2:sha256',
                                                          salt_length=16)
            student.password_reset = ""
            db.session.commit()

            log_entry("Password Reset", [student.student_mail])

            send_mail([student.student_mail], f"{student.student_name} - Password Reset",
                      "Your password has been reset.")
        return redirect(url_for('show_index'))
    else:
        return render_template('password_reset.html', password_reset_form=password_reset_form, random_hash=random_hash)


# --------------------------------------------------------------
# S3 storage pages
# --------------------------------------------------------------

# Show list of all uploaded filed and upload form
@app.route(APP_PREFIX + "/web/storage", methods=['GET', 'POST'])
@login_required
def show_storage():
    file_upload_form = FileUploadForm()
    file_rename_form = FileRenameForm()
    s3_folder = S3_GLOBAL if current_user.student_role == ROLE_ADMIN else current_user.student_name
    space_used_in_mb = round((get_size(S3_BUCKET, f"{s3_folder}/") / 1024 / 1024), 2)
    space_used = int(space_used_in_mb / int(S3_QUOTA) * 100)

    if request.method == 'POST' and escape(file_upload_form.page_mode.data) == PAGE_UPLOAD and \
            file_upload_form.validate_on_submit():
        filename = secure_filename(file_upload_form.file.data.filename)
        upload_helper(s3_folder, space_used, filename, file_upload_form.file)

        log_entry("Upload", [S3_BUCKET, filename])

        return redirect(url_for('show_storage'))
    elif request.method == 'POST' and escape(file_rename_form.page_mode.data) == PAGE_RENAME and \
            file_rename_form.validate_on_submit():
        remote_file_new = f"{s3_folder}/{secure_filename(file_rename_form.filename_new.data)}"
        remote_file_old = f"{s3_folder}/{secure_filename(file_rename_form.filename_old.data)}"
        if remote_file_new != remote_file_old and allowed_file(remote_file_new):
            rename_file(S3_BUCKET, remote_file_new, remote_file_old)

            log_entry("Rename", [S3_BUCKET, remote_file_new, remote_file_old])

        return redirect(url_for('show_storage'))
    else:
        if escape(file_upload_form.page_mode.data) == PAGE_UPLOAD:
            page_mode = PAGE_UPLOAD
        elif escape(file_rename_form.page_mode.data) == PAGE_RENAME:
            page_mode = PAGE_RENAME
            file_rename_form.filename_new.default = escape(file_rename_form.filename_new.data)
            file_rename_form.filename_old.default = escape(file_rename_form.filename_old.data)
            file_rename_form.process()
        else:
            page_mode = PAGE_INIT
        contents = list_files(S3_BUCKET, s3_folder)
        return render_template('storage.html',
                               contents=contents, space_used_in_mb=space_used_in_mb, space_used=space_used,
                               page_mode=page_mode, file_upload_form=file_upload_form,
                               file_rename_form=file_rename_form, www_server=WWW_SERVER)


# Download a specific file from S3 storage
@app.route(APP_PREFIX + "/web/download/<string:filename>", methods=['GET'])
@login_required
def do_download(filename):
    s3_folder = S3_GLOBAL if current_user.student_role == ROLE_ADMIN else current_user.student_name
    local_folder_name = f"{DOWNLOAD_FOLDER}/{s3_folder}"
    local_filename = os.path.join(local_folder_name, secure_filename(filename))
    remote_file = f"{s3_folder}/{secure_filename(filename)}"

    if not os.path.exists(local_folder_name):
        os.makedirs(local_folder_name)
    output = download_file(S3_BUCKET, remote_file, local_filename)
    # return send_from_directory(app.config["UPLOAD_FOLDER"], name)
    return send_file(output, as_attachment=True)


# Display a specific file from S3 storage - Global and User area
@app.route(APP_PREFIX + "/web/display/<string:username>/<string:filename>", methods=['GET'])
def do_display(username, filename):
    if username == S3_GLOBAL:
        s3_folder = username
    else:
        student = Student.query.filter_by(student_name=username).first()
        if student and (student.student_img == filename or current_user.student_name == username):
            s3_folder = student.student_name
        else:
            return render_template('error.html', error_message=ERR_AUTH)

    local_folder_name = f"{DOWNLOAD_FOLDER}/{s3_folder}"
    local_filename = os.path.join(local_folder_name, secure_filename(filename))
    remote_file = f"{s3_folder}/{secure_filename(filename)}"

    if not os.path.exists(local_folder_name):
        os.makedirs(local_folder_name)
    output = download_file(S3_BUCKET, remote_file, local_filename)

    if filename.rsplit('.', 1)[1].lower() == "pdf":
        dpi = 300  # choose desired dpi here
        zoom = dpi / 72  # zoom factor, standard: 72 dpi
        magnify = fitz.Matrix(zoom, zoom)  # magnifies in x, resp. y direction
        doc = fitz.open(output)  # open document
        # for page in doc:
        #    pix = page.get_pixmap(matrix=magnify)  # render page to an image
        #    pix.save(f"{output}-{page.number}.png")
        pix = doc[0].get_pixmap(matrix=magnify)  # render page to an image
        pix.save(f"{output}.png")
        return send_file(f"{output}.png", as_attachment=False)
    else:
        # return send_from_directory(app.config["UPLOAD_FOLDER"], name)
        return send_file(output, as_attachment=False)


# Remove a specific file from S3 storage
@app.route(APP_PREFIX + "/web/delete/<string:filename>", methods=['GET'])
@login_required
def do_delete(filename):
    s3_folder = S3_GLOBAL if current_user.student_role == ROLE_ADMIN else current_user.student_name
    remote_file = f"{s3_folder}/{secure_filename(filename)}"
    delete_file(S3_BUCKET, remote_file)

    log_entry("Delete", [S3_BUCKET, remote_file])

    return redirect(url_for('show_storage'))


# --------------------------------------------------------------
# Flask side views
# --------------------------------------------------------------

# Show statistics regarding available elements stored in the database and on S3 storage
@app.route(APP_PREFIX + '/web/stats', methods=['GET'])
def show_stats():
    counts = dict()
    counts['student'] = Student.query.count()
    counts['lesson'] = Lesson.query.count()
    counts['quiz'] = Quiz.query.count()
    counts['campaign'] = Campaign.query.count()
    counts['scenario'] = Scenario.query.count()

    if current_user.is_authenticated and current_user.student_role == ROLE_ADMIN:
        bucket_all = get_all_size(S3_BUCKET)
    elif current_user.is_authenticated and current_user.student_role == ROLE_USER:
        bucket_all = dict()
        bucket_all[current_user.student_name] = get_size(S3_BUCKET, current_user.student_name)
    else:
        bucket_all = dict()

    return render_template('stats.html', counts=counts, bucket_all=bucket_all)


# Show information about all major releases
@app.route(APP_PREFIX + '/web/release', methods=['GET'])
def show_release():
    return render_template('release.html')


# Show information about all learning modules in a certain language
@app.route(APP_PREFIX + '/web/lessons/<int:language>', methods=['GET'])
def show_lessons(language):
    update_language(language)

    categories = select_categories()
    languages = select_languages()
    if language == 0:
        lessons = select_lessons()
        quizzes = select_quizzes()
    else:
        lessons = select_lessons(language)
        quizzes = select_quizzes(language)
    quiz_scores = select_quiz_scores()

    return render_template('lesson.html', categories=categories, languages=languages,
                           lessons=lessons, quizzes=quizzes, quiz_scores=quiz_scores)


# Show specific learning module
@app.route(APP_PREFIX + '/web/lesson/<int:language>/<string:lesson_name>', methods=['GET'])
def show_lesson(language, lesson_name):
    update_language(language)

    lesson = select_lesson(language, lesson_name)

    if lesson:
        return render_template('lesson_detail.html', lesson=lesson)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Show specific quiz module
@app.route(APP_PREFIX + '/web/quiz/<int:language>/<int:quiz_id>', methods=['GET'])
def show_quiz(language, quiz_id):
    update_language(language)

    quiz = select_quiz(language, quiz_id)

    if quiz:
        return render_template('quiz_play.html', quiz=quiz)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Rate specific quiz module
@app.route(APP_PREFIX + '/web/rate_quiz/<int:language>/<int:quiz_id>', methods=['GET'])
def rate_quiz(language, quiz_id):
    update_language(language)

    quiz = select_quiz(language, quiz_id)

    if quiz:
        score_cand = 0
        score_target = quiz.points

        cookie = request.cookies.get("quiz-" + str(escape(quiz.quiz_id)))

        if cookie:
            scores = unquote(cookie)
            jsonval = json.loads(scores)

            try:
                if int(jsonval["answer"] == quiz.quiz_solution):
                    score_cand = score_cand + quiz.points
            except KeyError:
                score_cand = score_cand

        update_quiz_score(quiz_id, score_cand)

        return render_template('quiz_rate.html', score_target=score_target, score_cand=score_cand)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Show privacy policy
@app.route(APP_PREFIX + '/web/privacy', methods=['GET'])
def show_privacy():
    return render_template('privacy.html')


# Displays an image file stored on S3 storage
@app.route(APP_PREFIX + '/web/image/<string:filename>', methods=['GET'])
@login_required
def show_image(filename):
    s3_folder = S3_GLOBAL if current_user.student_role == ROLE_ADMIN else current_user.student_name
    return render_template('image.html', username=s3_folder, filename=secure_filename(filename))


# Displays a form to send a message to the site admin - implements a simple captcha as well
@app.route(APP_PREFIX + '/web/contact', methods=['GET', 'POST'])
def show_contact():
    contact_form = ContactForm()
    if request.method == 'POST':
        if contact_form.validate_on_submit():
            contact_name = escape(contact_form.contact_name.data)
            email = escape(contact_form.email.data)
            message = escape(contact_form.message.data)

            send_mail([MAIL_ADMIN], f"{contact_name} - {email}",
                      f"{message}")

            return redirect(url_for('show_index'))
        else:
            contact_form.contact_name.default = escape(contact_form.contact_name.data)
            contact_form.email.default = escape(contact_form.email.data)
            contact_form.message.default = escape(contact_form.message.data)

            random1 = random.randint(1, 10)
            random2 = random.randint(1, 10)
            check_captcha = random1 + random2

            contact_form.check_captcha.default = check_captcha
            contact_form.process()

            return render_template('contact.html', contact_form=contact_form, random1=random1, random2=random2,
                                   check_captcha=check_captcha)
    else:
        random1 = random.randint(1, 10)
        random2 = random.randint(1, 10)
        check_captcha = random1 + random2

        contact_form.check_captcha.default = check_captcha
        contact_form.process()

        return render_template('contact.html', contact_form=contact_form, random1=random1, random2=random2,
                               check_captcha=check_captcha)


# --------------------------------------------------------------
# Flask HTML views to read and modify the database contents
# --------------------------------------------------------------

# Displays all available students
@app.route(APP_PREFIX + '/web/students', methods=['GET'])
@login_required
def show_students():
    if current_user.student_role == ROLE_ADMIN:
        students = Student.query.order_by(Student.student_name.asc())
    else:
        students = Student.query.filter_by(active=1).order_by(Student.student_name.asc())
    return render_template('student.html', students=students)


# Shows information about a specific student
@app.route(APP_PREFIX + '/web/student/<string:student_name>', methods=['GET'])
@login_required
def show_student(student_name):
    if current_user.student_role == ROLE_ADMIN:
        student = Student.query.filter_by(student_name=student_name).first()
    else:
        student = Student.query.filter_by(active=1).filter_by(student_name=student_name).first()

    if student:
        if student.student_role == ROLE_ADMIN:
            folder_name = S3_GLOBAL
        else:
            folder_name = student.student_name
        return render_template('student_detail.html', folder_name=folder_name, student=student)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Displays a form to create a new user (aka student)
@app.route(APP_PREFIX + '/web/new_student', methods=['GET', 'POST'])
def show_new_student():
    account_form = AccountForm()
    if request.method == 'POST' and account_form.validate_on_submit():
        code = escape(account_form.invitation.data)
        invitation = Invitation.query.filter_by(invitation_code=code).first()

        existing_student = Student.query.filter_by(student_mail=escape(account_form.email.data)).first()

        if existing_student is None:
            if invitation and (invitation.invitation_forever == 1 or invitation.invitation_taken == 0):
                student = Student()
                student.student_name = escape(account_form.student.data)
                student.student_mail = escape(account_form.email.data)
                student.student_desc = ""
                student.student_pass = generate_password_hash(account_form.password.data, method='pbkdf2:sha256',
                                                              salt_length=16)
                student.student_role = invitation.invitation_role
                student.student_img = ""
                student.active = 1
                db.session.add(student)
                db.session.commit()

                invitation.invitation_taken = 1
                db.session.commit()

                log_entry("Register automatic", [student.student_mail])

                send_mail([MAIL_ADMIN], f"{student.student_name} - Registration complete",
                          "A new user has registered using an invitation code. No action necessary.")

                send_mail([student.student_mail], f"{student.student_name} - Registration successful",
                          "Your registration has been approved. You can know log in.")
            else:
                student = Student()
                student.student_name = escape(account_form.student.data)
                student.student_mail = escape(account_form.email.data)
                student.student_desc = ""
                student.student_pass = generate_password_hash(account_form.password.data, method='pbkdf2:sha256',
                                                              salt_length=16)
                student.student_role = ROLE_USER
                student.student_img = ""
                student.active = 0
                db.session.add(student)
                db.session.commit()

                log_entry("Register approval", [student.student_mail])

                send_mail([MAIL_ADMIN], f"{student.student_name} - Approval required",
                          "A new user has registered, please approve registration.")

                send_mail([student.student_mail], f"{student.student_name} - Registration pending",
                          "Your registration needs to be approved. This should not take too long.")
            return redirect(url_for('show_students'))
        else:
            return render_template('account.html', account_form=account_form)
    else:
        return render_template('account.html', account_form=account_form)


# Displays various forms to change the currently logged-in user
@app.route(APP_PREFIX + '/web/my_student', methods=['GET', 'POST'])
@login_required
def show_my_student():
    student_mail_form = StudentMailForm()
    student_password_form = StudentPasswordForm()
    student_deletion_form = StudentDeletionForm()
    student_reset_form = StudentResetForm()
    student = Student.query.filter_by(student_id=current_user.student_id).first()

    if request.method == 'POST' and escape(student_mail_form.page_mode.data) == PAGE_MAIL and \
            student_mail_form.validate_on_submit():
        old_mail = student.student_mail
        student.student_mail = escape(student_mail_form.email.data)
        student.student_desc = student_mail_form.description.data
        student.student_img = escape(student_mail_form.image.data)
        student.notification = int(student_mail_form.notification.data)
        db.session.commit()

        send_mail([student.student_mail], "Notification: E-Mail changed",
                  f"You have changed you e-mail address from {old_mail} to {student.student_mail}.")

        return redirect(url_for('show_my_student'))
    elif request.method == 'POST' and escape(student_password_form.page_mode.data) == PAGE_PASS and \
            student_password_form.validate_on_submit():
        student.student_pass = generate_password_hash(student_password_form.password.data, method='pbkdf2:sha256',
                                                      salt_length=16)
        db.session.commit()
        return redirect(url_for('show_my_student'))
    elif request.method == 'POST' and escape(student_deletion_form.page_mode.data) == PAGE_DELETE and \
            student_deletion_form.validate_on_submit():
        Student.query.filter_by(student_id=current_user.student_id).delete()
        db.session.commit()
        logout_user()
        return redirect(url_for('show_index'))
    elif request.method == 'POST' and escape(student_reset_form.page_mode.data) == PAGE_RESET and \
            student_reset_form.validate_on_submit():
        QuizScore.query.filter_by(student_id=current_user.student_id).delete()
        ScenarioScore.query.filter_by(student_id=current_user.student_id).delete()
        db.session.commit()
        return redirect(url_for('show_index'))
    else:
        if escape(student_mail_form.page_mode.data) == PAGE_MAIL:
            page_mode = PAGE_MAIL
        elif escape(student_password_form.page_mode.data) == PAGE_PASS:
            page_mode = PAGE_PASS
        elif escape(student_deletion_form.page_mode.data) == PAGE_DELETE:
            page_mode = PAGE_DELETE
        elif escape(student_reset_form.page_mode.data) == PAGE_RESET:
            page_mode = PAGE_RESET
        else:
            page_mode = PAGE_INIT

        student_mail_form.email.default = student.student_mail
        student_mail_form.description.default = student.student_desc
        if current_user.student_role == ROLE_ADMIN:
            student_mail_form.image.choices = get_file_choices(S3_GLOBAL)
            student_mail_form.image.default = student.student_img
        else:
            student_mail_form.image.choices = get_file_choices(student.student_name)
            student_mail_form.image.default = student.student_img
        student_mail_form.notification.default = student.notification
        student_mail_form.process()
        return render_template('account_detail.html', student=student, page_mode=page_mode,
                               student_mail_form=student_mail_form, student_password_form=student_password_form,
                               student_reset_form=student_reset_form, student_deletion_form=student_deletion_form)


# Approve a user's registration
@app.route(APP_PREFIX + '/web/approve_student/<string:student_name>', methods=['GET'])
@login_required
def show_approve_student(student_name):
    if current_user.student_role == ROLE_ADMIN:
        student = Student.query.filter_by(student_name=student_name).first()
        student.active = 1
        db.session.commit()

        log_entry("Approval", [student.student_mail])

        send_mail([student.student_mail], f"{student.student_name} - Registration complete",
                  "Your registration has been approved. You can use your login now.")

        return redirect(url_for('show_students'))
    else:
        return render_template('error.html', error_message=ERR_AUTH)


# Displays all available campaigns
@app.route(APP_PREFIX + '/web/campaigns', methods=['GET'])
def show_campaigns():
    campaign_form = CampaignForm()
    campaign_form.image.choices = get_file_choices(S3_GLOBAL)
    campaign_form.image.default = "No Image"
    campaign_form.process()

    campaigns = select_campaigns()

    return render_template('campaign.html', campaigns=campaigns, page_mode=PAGE_INIT,
                           campaign_form=campaign_form)


# Post a new campaign - if it doesn't already exist
@app.route(APP_PREFIX + '/web/campaigns', methods=['POST'])
@login_required
def show_campaigns_p():
    campaign_form = CampaignForm()
    conflicting_campaign = select_campaign(escape(campaign_form.name.data))

    if current_user.student_role == ROLE_ADMIN and campaign_form.validate_on_submit() and conflicting_campaign is None:
        campaign = Campaign()
        campaign.student_id = current_user.student_id
        map_form_to_campaign(campaign, campaign_form)
        db.session.add(campaign)
        db.session.commit()

        log_entry("Campaign Add", [campaign.campaign_name])

        return redirect(url_for('show_campaigns'))
    elif current_user.student_role == ROLE_ADMIN and (not campaign_form.validate_on_submit() or conflicting_campaign):
        campaign_form.image.choices = get_file_choices(S3_GLOBAL)
        map_campaign_defaults(campaign_form, (conflicting_campaign is not None))
        campaign_form.process()

        campaigns = select_campaigns()

        return render_template('campaign.html', campaigns=campaigns, page_mode=PAGE_MODAL,
                               campaign_form=campaign_form)
    else:
        return render_template('error.html', error_message=ERR_AUTH)


# Shows information about a specific campaign
@app.route(APP_PREFIX + '/web/campaign/<string:campaign_name>', methods=['GET'])
def show_campaign(campaign_name):
    campaign_form = CampaignForm()

    campaign = select_campaign(campaign_name)

    if campaign:
        student = Student.query.filter_by(student_id=campaign.student_id).first()
        scenarios = select_scenarios_cid(campaign.campaign_id)

        campaign_form.image.choices = get_file_choices(S3_GLOBAL)
        map_campaign_to_form(campaign, campaign_form)
        campaign_form.process()

        return render_template('campaign_detail.html', campaign=campaign, scenarios=scenarios,
                               student=student, folder_name=S3_GLOBAL, page_mode=PAGE_INIT,
                               campaign_form=campaign_form)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Post a change in an campaign's data
@app.route(APP_PREFIX + '/web/campaign/<string:campaign_name>', methods=['POST'])
@login_required
def show_campaign_p(campaign_name):
    campaign_form = CampaignForm()
    campaign = select_campaign(campaign_name)
    conflicting_campaign = select_campaign(escape(campaign_form.name.data))

    if (current_user.student_role == ROLE_ADMIN and campaign_form.validate_on_submit() and
            (campaign_name == escape(campaign_form.name.data) or conflicting_campaign is None)):
        if campaign:
            map_form_to_campaign(campaign, campaign_form)
            db.session.commit()

            log_entry("Campaign Modified", [campaign.campaign_name])

            return redirect(url_for('show_campaign', campaign_name=campaign.campaign_name))
        else:
            return render_template('error.html', error_message=ERR_NOT_EXIST)
    elif current_user.student_role == ROLE_ADMIN and (not campaign_form.validate_on_submit() or conflicting_campaign):
        student = Student.query.filter_by(student_id=campaign.student_id).first()
        scenarios = select_scenarios_cid(campaign.campaign_id)

        campaign_form.image.choices = get_file_choices(S3_GLOBAL)
        map_campaign_defaults(campaign_form, (conflicting_campaign is not None))
        campaign_form.process()

        return render_template('campaign_detail.html', campaign=campaign, scenarios=scenarios,
                               student=student, folder_name=S3_GLOBAL, page_mode=PAGE_MODAL,
                               campaign_form=campaign_form)
    else:
        return render_template('error.html', error_message=ERR_AUTH)


# Delete a specific campaign - and all included elements!!!
@app.route(APP_PREFIX + '/web/delete_campaign/<string:campaign_name>', methods=['GET'])
@login_required
def delete_campaign(campaign_name):
    campaign = select_campaign(campaign_name)

    if current_user.student_role == ROLE_ADMIN:
        if campaign:
            Campaign.query.filter_by(campaign_name=campaign_name).delete()
            db.session.commit()

            log_entry("Campaign Delete", [campaign.campaign_name])

            return redirect(url_for('show_campaigns'))
        else:
            return render_template('error.html', error_message=ERR_NOT_EXIST)
    else:
        return render_template('error.html', error_message=ERR_AUTH)


# Displays all available scenarios
@app.route(APP_PREFIX + '/web/scenarios', methods=['GET'])
def show_scenarios():
    scenario_form = ScenarioForm()
    scenario_form.image.choices = get_file_choices(S3_GLOBAL)
    scenario_form.image.default = "No Image"
    scenario_form.campaign.choices = get_campaign_choices(select_campaigns())
    scenario_form.process()

    campaigns = select_campaigns()
    scenarios = select_scenarios()
    scenario_scores = select_scenario_scores()

    return render_template('scenario.html', scenarios=scenarios, page_mode=PAGE_INIT,
                           campaigns=campaigns, scenario_scores=scenario_scores, scenario_form=scenario_form)


# Post a new scenario - if it doesn't already exist
@app.route(APP_PREFIX + '/web/scenarios', methods=['POST'])
@login_required
def show_scenarios_p():
    scenario_form = ScenarioForm()
    conflicting_scenario = select_scenario(escape(scenario_form.name.data))

    if current_user.student_role == ROLE_ADMIN and scenario_form.validate_on_submit() and conflicting_scenario is None:
        scenario = Scenario()
        scenario.student_id = current_user.student_id
        map_form_to_scenario(scenario, scenario_form)
        db.session.add(scenario)
        db.session.commit()

        log_entry("Scenario Add", [scenario.scenario_name])

        return redirect(url_for('show_scenarios'))
    elif current_user.student_role == ROLE_ADMIN and (not scenario_form.validate_on_submit() or conflicting_scenario):
        scenario_form.image.choices = get_file_choices(S3_GLOBAL)
        scenario_form.campaign.choices = get_campaign_choices(select_campaigns())
        map_scenario_defaults(scenario_form, (conflicting_scenario is not None))
        scenario_form.process()

        scenarios = select_scenarios()

        return render_template('scenario.html', scenarios=scenarios, page_mode=PAGE_MODAL,
                               scenario_form=scenario_form)
    else:
        return render_template('error.html', error_message=ERR_AUTH)


# Shows information about a specific scenario
@app.route(APP_PREFIX + '/web/scenario/<string:scenario_name>', methods=['GET'])
def show_scenario(scenario_name):
    scenario_form = ScenarioForm()

    scenario = select_scenario(scenario_name)

    if scenario:
        campaign = Campaign.query.filter_by(campaign_id=scenario.campaign_id).first()
        student = Student.query.filter_by(student_id=campaign.student_id).first()

        scenario_form.image.choices = get_file_choices(S3_GLOBAL)
        scenario_form.campaign.choices = get_campaign_choices(select_campaigns())
        map_scenario_to_form(scenario, scenario_form)
        scenario_form.process()

        return render_template('scenario_detail.html', scenario=scenario, student=student,
                               campaign=campaign, folder_name=S3_GLOBAL, page_mode=PAGE_INIT,
                               scenario_form=scenario_form)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Post a change in a scenario's data
@app.route(APP_PREFIX + '/web/scenario/<string:scenario_name>', methods=['POST'])
@login_required
def show_scenario_p(scenario_name):
    scenario_form = ScenarioForm()
    scenario = select_scenario(scenario_name)
    conflicting_scenario = select_scenario(escape(scenario_form.name.data))

    if (current_user.student_role == ROLE_ADMIN and scenario_form.validate_on_submit() and
            (scenario_name == escape(scenario_form.name.data) or conflicting_scenario is None)):
        if scenario:
            map_form_to_scenario(scenario, scenario_form)
            db.session.commit()

            log_entry("Scenario Modify", [scenario.scenario_name])

            return redirect(url_for('show_scenario', scenario_name=scenario.scenario_name))
        else:
            return render_template('error.html', error_message=ERR_NOT_EXIST)
    elif current_user.student_role == ROLE_ADMIN and (not scenario_form.validate_on_submit() or conflicting_scenario):
        campaign = Campaign.query.filter_by(campaign_id=scenario.campaign_id).first()
        student = Student.query.filter_by(student_id=campaign.student_id).first()

        scenario_form.image.choices = get_file_choices(S3_GLOBAL)
        scenario_form.campaign.choices = get_campaign_choices(select_campaigns())
        map_scenario_defaults(scenario_form, (conflicting_scenario is not None))
        scenario_form.process()

        return render_template('scenario_detail.html', scenario=scenario, student=student,
                               campaign=campaign, folder_name=S3_GLOBAL, page_mode=PAGE_MODAL,
                               scenario_form=scenario_form)
    else:
        return render_template('error.html', error_message=ERR_AUTH)


# Delete a specific scenario - and all included elements!!!
@app.route(APP_PREFIX + '/web/delete_scenario/<string:scenario_name>', methods=['GET'])
@login_required
def delete_scenario(scenario_name):
    scenario = select_scenario(scenario_name)

    if current_user.student_role == ROLE_ADMIN:
        if scenario:
            Scenario.query.filter_by(scenario_name=scenario_name).delete()
            db.session.commit()

            log_entry("Scenario Delete", [scenario.scenario_name])

            return redirect(url_for('show_scenarios'))
        else:
            return render_template('error.html', error_message=ERR_NOT_EXIST)
    else:
        return render_template('error.html', error_message=ERR_AUTH)


# Play a scenario
@app.route(APP_PREFIX + '/web/play_scenario/<string:scenario_name>', methods=['GET'])
def play_scenario(scenario_name):
    scenario = select_scenario(scenario_name)

    if scenario:
        areas = Area.query.filter_by(scenario_id=scenario.scenario_id).all()
        return render_template('scenario_play.html', username=S3_GLOBAL, filename=scenario.scenario_img,
                               areas=areas, counter=0, campaign="none", scenario=scenario)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Play a campaign
@app.route(APP_PREFIX + '/web/play_campaign/<string:campaign_name>/<int:counter>', methods=['GET'])
def play_campaign(campaign_name, counter):
    campaign = select_campaign(campaign_name)
    if campaign:
        scenarios = select_scenarios_cid(campaign.campaign_id)

        if scenarios:
            if len(scenarios) > counter:
                scenario = scenarios[counter]
                areas = Area.query.filter_by(scenario_id=scenario.scenario_id).all()
                c = counter + 1
                return render_template('scenario_play.html', username=S3_GLOBAL, filename=scenario.scenario_img,
                                       areas=areas, counter=c, campaign=campaign, scenario=scenario)
            else:
                return redirect(url_for('rate_campaign', campaign_name=campaign.campaign_name))
        else:
            return render_template('error.html', error_message=ERR_NOT_EXIST)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Rate a scenario
@app.route(APP_PREFIX + '/web/rate_scenario/<string:scenario_name>', methods=['GET'])
def rate_scenario(scenario_name):
    scenario = select_scenario(scenario_name)

    if scenario:
        score_cand = 0
        score_target = 0
        ind_found = 0
        ind_target = 0
        legitimate = -1

        areas = Area.query.filter_by(scenario_id=scenario.scenario_id).all()
        cookie = request.cookies.get(escape(scenario.scenario_name).replace(' ', '%20'))

        score_target = score_target + 10
        if cookie:
            scores = unquote(cookie)
            jsonval = json.loads(scores)

            try:
                if int(jsonval["level"] == scenario.legitimate):
                    score_cand = score_cand + 10
                    legitimate = int(jsonval["level"])
            except KeyError:
                score_cand = score_cand

        for area in areas:
            score_target = score_target + area.points
            ind_target = ind_target + 1
            if cookie:
                scores = unquote(cookie)
                jsonval = json.loads(scores)

                try:
                    score_cand = score_cand + int(jsonval["area-" + str(area.area_id)])
                    ind_found = ind_found + 1
                except KeyError:
                    score_cand = score_cand

        update_scenario_score(scenario.scenario_id, score_cand)

        return render_template('scenario_rate.html', scenario=scenario,
                               legitimate=legitimate, score_target=score_target,
                               score_cand=score_cand, ind_target=ind_target, ind_found=ind_found)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Rate a campaign
@app.route(APP_PREFIX + '/web/rate_campaign/<string:campaign_name>', methods=['GET'])
def rate_campaign(campaign_name):
    campaign = select_campaign(campaign_name)

    if campaign:
        score_cand = 0
        score_target = 0
        ind_found = 0
        ind_target = 0
        legitimate = -1

        scenarios = select_scenarios_cid(campaign.campaign_id)
        for scenario in scenarios:
            score_single = 0

            areas = Area.query.filter_by(scenario_id=scenario.scenario_id).all()
            cookie = request.cookies.get(escape(scenario.scenario_name).replace(' ', '%20'))

            score_target = score_target + 10
            if cookie:
                scores = unquote(cookie)
                jsonval = json.loads(scores)

                try:
                    if int(jsonval["level"] == scenario.legitimate):
                        score_cand = score_cand + 10
                        score_single = score_single + 10
                        legitimate = int(jsonval["level"])
                except KeyError:
                    score_cand = score_cand
                    score_single = score_single

            for area in areas:
                score_target = score_target + area.points
                ind_target = ind_target + 1
                if cookie:
                    scores = unquote(cookie)
                    jsonval = json.loads(scores)

                    try:
                        score_cand = score_cand + int(jsonval["area-" + str(area.area_id)])
                        score_single = score_single + int(jsonval["area-" + str(area.area_id)])
                        ind_found = ind_found + 1
                    except KeyError:
                        score_cand = score_cand
                        score_single = score_single

            update_scenario_score(scenario.scenario_id, score_single)

        return render_template('campaign_rate.html', campaign=campaign,
                               legitimate=legitimate, score_target=score_target,
                               score_cand=score_cand, ind_target=ind_target, ind_found=ind_found)
    else:
        return render_template('error.html', error_message=ERR_NOT_EXIST)


# Edit a scenario's areas
@app.route(APP_PREFIX + '/web/areas/<string:scenario_name>', methods=['GET'])
@login_required
def show_areas(scenario_name):
    area_form = AreaForm()
    area_form.process()

    scenario = select_scenario(scenario_name)

    if current_user.student_role == ROLE_ADMIN:
        if scenario:
            areas = Area.query.filter_by(scenario_id=scenario.scenario_id).all()
            return render_template('area.html', username=S3_GLOBAL, filename=scenario.scenario_img,
                                   areas=areas, scenario=scenario, area_form=area_form)
        else:
            return render_template('error.html', error_message=ERR_NOT_EXIST)
    else:
        return render_template('error.html', error_message=ERR_AUTH)


# Post a new area
@app.route(APP_PREFIX + '/web/areas/<string:scenario_name>', methods=['POST'])
@login_required
def show_areas_p(scenario_name):
    area_form = AreaForm()
    scenario = select_scenario(scenario_name)

    if current_user.student_role == ROLE_ADMIN and area_form.validate_on_submit():
        if scenario:
            area = Area()
            map_form_to_area(area, area_form, scenario.scenario_id)
            db.session.add(area)
            db.session.commit()
            return redirect(url_for('show_areas', scenario_name=scenario_name))
        else:
            return render_template('error.html', error_message=ERR_NOT_EXIST)
    elif current_user.student_role == ROLE_ADMIN and not area_form.validate_on_submit():
        if scenario:
            areas = Area.query.filter_by(scenario_id=scenario.scenario_id).all()
            map_area_defaults(area_form)
            area_form.process()
            return render_template('area.html', username=S3_GLOBAL, filename=scenario.scenario_img,
                                   areas=areas, scenario=scenario, area_form=area_form)
        else:
            return render_template('error.html', error_message=ERR_NOT_EXIST)
    else:
        return render_template('error.html', error_message=ERR_AUTH)


# Delete a specific area
@app.route(APP_PREFIX + '/web/delete_area/<int:area_id>', methods=['GET'])
@login_required
def delete_area(area_id):
    area = Area.query.filter_by(area_id=area_id).first()

    if current_user.student_role == ROLE_ADMIN:
        if area:
            scenario = Scenario.query.filter_by(scenario_id=area.scenario_id).first()
            Area.query.filter_by(area_id=area_id).delete()
            db.session.commit()
            return redirect(url_for('show_areas', scenario_name=scenario.scenario_name))
        else:
            return render_template('error.html', error_message=ERR_NOT_EXIST)
    else:
        return render_template('error.html', error_message=ERR_AUTH)
