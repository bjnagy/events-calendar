# from flask import render_template, redirect, url_for, flash, request
# from urllib.parse import urlsplit
# from flask_login import login_user, logout_user, current_user
# #from flask_babel import _
# import sqlalchemy as sa
# from app import db
# from app.auth.forms import LoginForm, RegistrationForm, ResetPasswordRequestForm, ResetPasswordForm
# from app.models import User
# from app.auth.email import send_password_reset_email

from flask import make_response

from app.bridge import bp
#from app.bridge import openlands
import feeds


@bp.route('/bridge/openlands', methods=['GET'])
def openlands_bridge():
    data = feeds.Openlands.get('bridge')
    return data
    # rss_xml = openlands.create_feed()
    # response = make_response(rss_xml)
    # response.headers.set('Content-Type', 'application/rss+xml')
    # return response