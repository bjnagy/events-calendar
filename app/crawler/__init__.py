from flask import Blueprint

bp = Blueprint('crawler', __name__)

from app.crawler import routes