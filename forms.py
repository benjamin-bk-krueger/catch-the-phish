import re

from flask_wtf import FlaskForm  # integration with WTForms, data validation and CSRF protection
from flask_wtf.file import FileRequired, FileAllowed
from wtforms import (StringField, PasswordField, BooleanField, HiddenField, FileField, TextAreaField, SelectField,
                     IntegerRangeField)
from wtforms.validators import ValidationError, InputRequired, EqualTo, Email, Length, NumberRange


# Custom validator for standard ASCII characters
def ascii_validator(form, field):
    if not re.search(r"^[A-Za-z0-9_.+-]+$", field.data):
        raise ValidationError('Please use only letters, numbers or the characters -_.')


# Custom validator for standard ASCII characters and additional space
def space_ascii_validator(form, field):
    if not re.search(r"^[A-Za-z0-9_.+ -]*$", field.data):
        raise ValidationError('Please use only letters, numbers or the characters -_.')


# Custom validator for extended ASCII characters
def full_ascii_validator(form, field):
    if not re.search(r"^[\S\n\r\t\v ]*$", field.data):
        raise ValidationError('Please use only ASCII letters and numbers.')


# Custom validator for integer numbers
def integer_validator(form, field):
    if not re.search(r"^[0-9]+$", field.data):
        raise ValidationError('Please use only numbers.')


# Every form used both in the Flask/Jinja templates as well the main Python app is defined here.
# Not all fields have full validators as they are used in modal windows.

class LoginForm(FlaskForm):
    email = StringField('E-Mail', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=20)])
    remember = BooleanField('Remember me', default='checked')


class PasswordForm(FlaskForm):
    email = StringField('E-Mail', validators=[InputRequired(), Email()])


class PasswordResetForm(FlaskForm):
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=20),
                                                     EqualTo('password2', message='Passwords must match')])
    password2 = PasswordField('Password Verification', validators=[InputRequired(), Length(min=8, max=20)])


class FileUploadForm(FlaskForm):
    file = FileField(validators=[FileRequired(), FileAllowed(['png', 'jpg', 'jpeg', 'gif', 'pdf'],
                                                             'Images and Documents only!')])
    page_mode = HiddenField(default='init')


class FileRenameForm(FlaskForm):
    filename_new = StringField('File Name', validators=[InputRequired(), ascii_validator])
    filename_old = HiddenField(default='filename')
    page_mode = HiddenField(default='init')


class ContactForm(FlaskForm):
    contact_name = StringField('Name', validators=[InputRequired(), Length(min=5, max=40), full_ascii_validator])
    email = StringField('E-Mail', validators=[InputRequired(), Email()])
    message = TextAreaField('Message', validators=[Length(max=1024), full_ascii_validator])
    check_captcha = HiddenField(default='0')
    captcha = StringField('Captcha', validators=[InputRequired(), EqualTo('check_captcha', message='Captcha does not '
                                                                                                   'match')])


class AccountForm(FlaskForm):
    student = StringField('Name', validators=[InputRequired(), Length(min=5, max=40), space_ascii_validator])
    email = StringField('E-Mail', validators=[InputRequired(), Email()])
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=20),
                                                     EqualTo('password2', message='Passwords must match')])
    password2 = PasswordField('Password Verification', validators=[InputRequired(), Length(min=8, max=20)])
    invitation = StringField('Invitation Code', validators=[InputRequired(), Length(min=5, max=20)], default='guest')


class StudentMailForm(FlaskForm):
    email = StringField('E-Mail', validators=[InputRequired(), Email()])
    description = TextAreaField('Description', validators=[Length(max=1024), full_ascii_validator])
    image = SelectField('Image', choices=["none"], validate_choice=False)
    notification = BooleanField('Send notifications', default='checked')
    page_mode = HiddenField(default='init')


class StudentPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[InputRequired(), Length(min=8, max=20),
                                                     EqualTo('password2', message='Passwords must match')])
    password2 = PasswordField('Password Verification', validators=[InputRequired(), Length(min=8, max=20)])
    page_mode = HiddenField(default='init')


class StudentDeletionForm(FlaskForm):
    page_mode = HiddenField(default='init')


class StudentResetForm(FlaskForm):
    page_mode = HiddenField(default='init')


class CampaignForm(FlaskForm):
    name = StringField('Name', validators=[InputRequired(), Length(max=100), space_ascii_validator])
    description = TextAreaField('Description', validators=[Length(max=1024), full_ascii_validator])
    image = SelectField('Image', choices=["none"], validate_choice=False)
    public = BooleanField('Public', default='checked')


class ScenarioForm(FlaskForm):
    name = StringField('Name', validators=[InputRequired(), Length(max=100), space_ascii_validator])
    description = TextAreaField('Description', validators=[Length(max=1024), full_ascii_validator])
    briefing = TextAreaField('Briefing', validators=[Length(max=1024), full_ascii_validator])
    image = SelectField('Image', choices=["none"], validate_choice=False)
    campaign = SelectField('Select Campaign', choices=["none"], validate_choice=False)
    legitimate = BooleanField('Legitimate', default='checked')


class AreaForm(FlaskForm):
    start_x = StringField('Start X Coordinate', validators=[InputRequired(), integer_validator])
    start_y = StringField('Start Y Coordinate', validators=[InputRequired(), integer_validator])
    end_x = StringField('End X Coordinate', validators=[InputRequired(), integer_validator])
    end_y = StringField('End Y Coordinate', validators=[InputRequired(), integer_validator])
    points = IntegerRangeField('Points', validators=[NumberRange(min=-10, max=10)])
    hover = TextAreaField('Hover', validators=[Length(max=384), full_ascii_validator])
