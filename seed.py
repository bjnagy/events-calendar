from app import db
from app.models import User, Feed, Event

#Openlands
def grow():
    o1 = db.session.query(User).filter_by(username='Openlands').one_or_none()
    if not o1:
        o1 = User(username='Openlands', account_type='Organization')
        db.session.add(o1)
        db.session.commit()

    f1 = db.session.query(Feed).filter_by(name='Cervis').one_or_none()
    if not f1:
        f1 = Feed(name='Cervis', type='Openlands', owner=o1)
        db.session.add(f1)
        db.session.commit()

    f1.refresh()
    print("seed grow")