from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, DateField, TimeField, SelectField
from wtforms.validators import ValidationError, DataRequired, Length, Optional
import sqlalchemy as sa
import datetime
import json
import pytz
#from flask_babel import _, lazy_gettext as _l
from app import db
from app.models import User
from app import location
        
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
    timezone = SelectField('Timezone', choices=[(tz, tz) for tz in pytz.all_timezones], validators=[DataRequired()])
    starts_at_date = DateField("Start Date", default=datetime.datetime.today(), validators=[DataRequired()])
    starts_at_time = TimeField("Start time", format='%H:%M', default=datetime.datetime.now(), validators=[Optional()])
    ends_at_date = DateField("End Date", validators=[Optional()])
    ends_at_time = TimeField("End time", format='%H:%M', validators=[Optional()])
    #starts_at = DateTimeLocalField("Starts At", default=datetime.datetime.now()) #format='%m/%d/%YT%H:%M', 
    #ends_at = DateTimeLocalField("Ends At", validators=[Optional()])
    location = TextAreaField('Location of event', validators=[Length(min=0)])
    location_desc = TextAreaField('Description of location', validators=[Length(min=0)])
    location_geojson = TextAreaField('GeoJSON object describing location features', validators=[Length(min=0)])
    original_event_url = TextAreaField('URL for the original event posting', validators=[Length(min=0)])
    original_event_category= TextAreaField('Event category for the original event posting', validators=[Length(min=0)])
    submit = SubmitField('Submit')

    def validate_ends_at_time(self, field):
        if field.data and not self.ends_at_date.data:
            raise ValidationError('You cannot specify an end time without an end date')
        
    def validate_location(self, field):
        if field.data:
            try:
                coords = location.parse_location(field.data)
                self.coords = coords  # Store the parsed result as a new attribute
            except Exception as e:
                raise ValidationError(f"Error parsing Location: {e}")

    def validate_location_geojson(self, field):
        if field.data:
            try:
                json.loads(field.data)
            except json.JSONDecodeError:
                raise ValidationError('GeoJSON is malformed')