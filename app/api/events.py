from app.api import bp
from app.models import Event
from flask import url_for, abort
from app import db
from app.api.errors import bad_request
import sqlalchemy as sa
from flask import request
from app.api.auth import token_auth

#NEED TO CONFIRM TOKEN IS AUTHED FOR EVENTS TIED TO THAT USER

@bp.route('/events/<int:id>', methods=['GET'])
@token_auth.login_required
def get_event(id):
    return db.get_or_404(Event, id).to_dict()

@bp.route('/events', methods=['GET'])
@token_auth.login_required
def get_events():
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)
    return Event.to_collection_dict(sa.select(Event), page, per_page,
                                   'api.get_events')

@bp.route('/events', methods=['POST'])
@token_auth.login_required
def create_event():
    data = request.get_json()
    if 'title' not in data or 'start_date' not in data:
        return bad_request('must include title and start_date at minimum')
    event = Event()
    event.from_dict(data)
    db.session.add(event)
    db.session.commit()
    return event.to_dict(), 201, {'Location': url_for('api.get_event',
                                                     id=event.id)}

@bp.route('/events/<int:id>', methods=['PUT'])
@token_auth.login_required
def update_event(id):
    event = db.get_or_404(Event, id)
    data = request.get_json()
    event.from_dict(data)
    db.session.commit()
    return event.to_dict()