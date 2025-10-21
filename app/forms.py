from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, TextAreaField, DateField, TimeField
from wtforms.validators import ValidationError, DataRequired, Email, EqualTo, Length, Optional
import sqlalchemy as sa
from app import db
from app.models import User
import datetime
import json

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    def validate_username(self, username):
        user = db.session.scalar(sa.select(User).where(
            User.username == username.data))
        if user is not None:
            raise ValidationError('Please use a different username.')

    def validate_email(self, email):
        user = db.session.scalar(sa.select(User).where(
            User.email == email.data))
        if user is not None:
            raise ValidationError('Please use a different email address.')
        
class EditProfileForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    about_me = TextAreaField('About me', validators=[Length(min=0, max=140)])
    submit = SubmitField('Submit')

    def __init__(self, original_username, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_username = original_username

    def validate_username(self, username):
        if username.data != self.original_username:
            user = db.session.scalar(sa.select(User).where(
                User.username == username.data))
            if user is not None:
                raise ValidationError('Please use a different username.')
            
class EmptyForm(FlaskForm):
    submit = SubmitField('Submit')

class EventForm(FlaskForm):
    title = TextAreaField('Title of event', validators=[
        DataRequired(), Length(min=1, max=140)])
    description = TextAreaField('Description of event', validators=[
        DataRequired(), Length(min=0)])
    start_date = DateField("Start Date", format='%Y-%m-%d', default=datetime.datetime.now(), validators=[DataRequired()])
    start_time = TimeField("Start time", format='%H:%M', validators=[Optional()])
    end_date = DateField("End Date", format='%Y-%m-%d', validators=[Optional()])
    end_time = TimeField("End time", format='%H:%M', validators=[Optional()])
    location = TextAreaField('Location of event', validators=[Length(min=0)])
    location_desc = TextAreaField('Description of location', validators=[Length(min=0)])
    location_geojson = TextAreaField('GeoJSON object describing location features', validators=[Length(min=0)])
    original_event_url = TextAreaField('URL for the original event posting', validators=[Length(min=0)])
    original_event_category= TextAreaField('Event category for the original event posting', validators=[Length(min=0)])
    submit = SubmitField('Submit')

    def validate_end_time(self, field):
        if not self.end_date.data and field.data:
            raise ValidationError('You cannot specify an end time without an end date')
        
    def validate_location_geojson(self, field):
        try:
            json.loads(field.data)
        except json.JSONDecodeError:
            raise ValidationError('GeoJSON is malformed')
        
class ResetPasswordRequestForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email()])
    submit = SubmitField('Request Password Reset')

class ResetPasswordForm(FlaskForm):
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField(
        'Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Request Password Reset')