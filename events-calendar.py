import sqlalchemy as sa
import sqlalchemy.orm as so
from app import create_app, db
from app.models import User, Event, Feed, Collection

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'sa': sa, 'so': so, 'db': db, 'User': User, 'Event': Event, 'Feed': Feed, 'Collection': Collection}
