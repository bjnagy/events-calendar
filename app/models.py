from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login
import app.location as location
from app.time import local_to_utc
from flask_login import UserMixin
from hashlib import md5
from time import time
import jwt
from flask import current_app, url_for
import secrets
import hashlib
import json
import feeds

def ordered(obj):
    if isinstance(obj, dict):
        return sorted((k, ordered(v)) for k, v in obj.items())
    if isinstance(obj, list):
        return sorted(ordered(x) for x in obj)
    else:
        return obj

def before_flush_listener(session, flust_context, instances):
    #print("before_flush event listener called")
    run_global_updates(session.dirty)
    run_global_updates(session.new)


def run_global_updates(records):
    for obj in records:
        # if hasattr(obj, 'update_timestamp'):
        #     obj.update_timestamp()
        #     print(f"Updating timestamp for {obj}")
        if callable(getattr(obj, 'set_hash', None)):
            obj.set_hash()
            #print(f"Setting hash for {obj}")

sa.event.listen(db.session, 'before_flush', before_flush_listener)

def create_hash(dict):
    dict.pop('id', None)
    dict.pop('timestamp', None)
    dict.pop('hash', None)
    ordered_dict = ordered(dict)
    to_hash = json.dumps(ordered_dict)
    return hashlib.sha256(to_hash.encode('utf-8')).hexdigest()

@login.user_loader
def load_user(id):
    return db.session.get(User, int(id))

followers = sa.Table(
    'followers',
    db.metadata,
    sa.Column('follower_id', sa.Integer, sa.ForeignKey('user.id'),
              primary_key=True),
    sa.Column('followed_id', sa.Integer, sa.ForeignKey('user.id'),
              primary_key=True)
)

collections = sa.Table(
    'collections',
    db.metadata,
    sa.Column('collection_id', sa.Integer, sa.ForeignKey('collection.id'),
              primary_key=True),
    sa.Column('event_id', sa.Integer, sa.ForeignKey('event.id'),
              primary_key=True)
)

class ValidationError(Exception):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

class PaginatedAPIMixin(object):
    @staticmethod
    def to_collection_dict(query, page, per_page, endpoint, **kwargs):
        resources = db.paginate(query, page=page, per_page=per_page,
                                error_out=False)
        data = {
            'items': [item.to_dict() for item in resources.items],
            '_meta': {
                'page': page,
                'per_page': per_page,
                'total_pages': resources.pages,
                'total_items': resources.total
            },
            '_links': {
                'self': url_for(endpoint, page=page, per_page=per_page,
                                **kwargs),
                'next': url_for(endpoint, page=page + 1, per_page=per_page,
                                **kwargs) if resources.has_next else None,
                'prev': url_for(endpoint, page=page - 1, per_page=per_page,
                                **kwargs) if resources.has_prev else None
            }
        }
        return data

class User(PaginatedAPIMixin, UserMixin, db.Model):
    #add profile_url to retrieve Org logo
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    email: so.Mapped[Optional[str]] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc))
    token: so.Mapped[Optional[str]] = so.mapped_column(sa.String(32), index=True, unique=True)
    token_expiration: so.Mapped[Optional[datetime]]
    account_type: so.Mapped[str] = so.mapped_column(sa.String(16), index=True)
    url: so.Mapped[Optional[str]] = so.mapped_column(sa.String(), nullable=True)

    feeds: so.WriteOnlyMapped['Feed'] = so.relationship(
        back_populates='owner')

    events: so.WriteOnlyMapped['Event'] = so.relationship(
        back_populates='owner')
    
    collections: so.WriteOnlyMapped['Collection'] = so.relationship(
        back_populates='owner')
    
    following: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.follower_id == id),
        secondaryjoin=(followers.c.followed_id == id),
        back_populates='followers')
    followers: so.WriteOnlyMapped['User'] = so.relationship(
        secondary=followers, primaryjoin=(followers.c.followed_id == id),
        secondaryjoin=(followers.c.follower_id == id),
        back_populates='following')

    def to_dict(self):
        data = {}
        for column in self.__table__.columns:
            col_val = getattr(self, column.name)
            if column.name in ['last_seen', 'token_expiration']:
                data[column.name] = col_val.replace(tzinfo=timezone.utc).isoformat() if col_val else None
            else:
                data[column.name] = col_val
        return data
    
    def from_dict(self, data):
        for field in data:
            setattr(self, field, data[field])
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def avatar(self, size):
        if self.email:
            digest = md5(self.email.lower().encode('utf-8')).hexdigest()
            return f'https://www.gravatar.com/avatar/{digest}?d=identicon&s={size}'
    
    def follow(self, user):
        if not self.is_following(user):
            self.following.add(user)

    def unfollow(self, user):
        if self.is_following(user):
            self.following.remove(user)

    def is_following(self, user):
        query = self.following.select().where(User.id == user.id)
        return db.session.scalar(query) is not None

    def followers_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.followers.select().subquery())
        return db.session.scalar(query)

    def following_count(self):
        query = sa.select(sa.func.count()).select_from(
            self.following.select().subquery())
        return db.session.scalar(query)
    
    def following_events(self):
        Source = so.aliased(User)
        Follower = so.aliased(User)
        return (
            sa.select(Event)
            .join(Event.owner.of_type(Source))
            .join(Source.followers.of_type(Follower), isouter=True)
            .where(sa.or_(
                Follower.id == self.id,
                Source.id == self.id,
            ))
            .group_by(Event)
            .order_by(Event.starts_at.asc())
        )
        
    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            current_app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, current_app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return db.session.get(User, id)
    
    def get_token(self, expires_in=3600):
        now = datetime.now(timezone.utc)
        if self.token and self.token_expiration.replace(
                tzinfo=timezone.utc) > now + timedelta(seconds=60):
            return self.token
        self.token = secrets.token_hex(16)
        self.token_expiration = now + timedelta(seconds=expires_in)
        db.session.add(self)
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.now(timezone.utc) - timedelta(
            seconds=1)

    @staticmethod
    def check_token(token):
        user = db.session.scalar(sa.select(User).where(User.token == token))
        if user is None or user.token_expiration.replace(
                tzinfo=timezone.utc) < datetime.now(timezone.utc):
            return None
        return user
        
    def __repr__(self):
        return f'<User {self.id} {self.username} {self.token} {self.token_expiration}>'

# class Organization(PaginatedAPIMixin, db.Model):
#     id: so.Mapped[int] = so.mapped_column(primary_key=True)
#     name: so.Mapped[str] = so.mapped_column(sa.String(140), index=True, unique=True)
#     description: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
#     url: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
#     timestamp: so.Mapped[datetime] = so.mapped_column(
#         index=True, default=lambda: datetime.now(timezone.utc))
#     events: so.WriteOnlyMapped['Event'] = so.relationship(
#         back_populates='organizer')
#     feeds: so.WriteOnlyMapped['Feed'] = so.relationship(
#         back_populates='organizer')
    
#     def to_dict(self):
#         data = {}
#         for column in self.__table__.columns:
#             col_val = getattr(self, column.name)
#             if column.name in ['timestamp']:
#                 data[column.name] = col_val.replace(tzinfo=timezone.utc).isoformat() if col_val else None
#             else:
#                 data[column.name] = col_val
#         return data
    
#     def from_dict(self, data):
#         for field in data:
#             val = data[field]
#             setattr(self, field, val)
    
#     def __repr__(self):
#         return f'<Organization {self.id} {self.name} {self.url}>'

class Feed(PaginatedAPIMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    name: so.Mapped[str] = so.mapped_column(sa.String(140))
    description: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    type: so.Mapped[str] = so.mapped_column(sa.String(10))
    uri: so.Mapped[Optional[str]] = so.mapped_column(sa.String())
    token: so.Mapped[Optional[str]] = so.mapped_column(sa.String())
    token_expiration: so.Mapped[Optional[datetime]]
    last_refresh: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id),
                                               index=True)
    owner: so.Mapped[User] = so.relationship(back_populates='feeds')
    events: so.WriteOnlyMapped['Event'] = so.relationship(
        back_populates='feed')
    
    def to_dict(self):
        data = {}
        for column in self.__table__.columns:
            col_val = getattr(self, column.name)
            if column.name in ['timestamp']:
                data[column.name] = col_val.replace(tzinfo=timezone.utc).isoformat() if col_val else None
            else:
                data[column.name] = col_val
        return data
    
    def from_dict(self, data):
        for field in data:
            val = data[field]
            setattr(self, field, val)

    def refresh(self):
        feed_class = getattr(feeds, self.type, None)
        if feed_class is not None:
            feed_instance = feed_class()
        else:
            raise ValidationError(f"Invalid feed '{self.type}'")
        #based on self.type and self.uri, create request url
            # if token and not now() > token_expiration then add to url
        #get new feed
        #apply data map (i.e. field name changes)
            #load as class based on self.type e.g. "Openlands", which has methods and field map for transforming resource for use by this app
        #query all existing events in current feed [in future?]
        events = feed_instance.get()
        #print(events)
        current_query = self.events.select().where(Event.feed_id == self.id)
        current_events = db.session.scalars(current_query).all()
        found_events = []
        for current_event in current_events:
            found_event = None
            for event in events:
                if current_event.original_event_id == event['original_event_id']:
                    if not current_event.check_hash(event):
                        found_event = event
                        found_events.append(found_event)
                        events.remove(event)
                        break
            if found_event:
                current_event.from_dict(event)
            else:
                db.session.delete(current_event)
        for event in events: #remaining events are new
            e1 = Event(owner=self.owner, feed=self)
            e1.from_dict(event)
            db.session.add(e1)
        self.last_refresh = datetime.now(timezone.utc)
        db.session.commit()
    
    def __repr__(self):
        return f'<Feed {self.id} {self.name} {self.description}>'
    
class Event(PaginatedAPIMixin, db.Model):
    #add url for event photo
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(140))
    description: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
    starts_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(), nullable=False)
    ends_at: so.Mapped[datetime] = so.mapped_column(sa.DateTime(), nullable=True)
    location: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
    location_desc: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
    location_lat: so.Mapped[float] = so.mapped_column(sa.Float(), nullable=True)
    location_lon: so.Mapped[float] = so.mapped_column(sa.Float(), nullable=True)
    location_geojson: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
    original_event_id: so.Mapped[str] = so.mapped_column(sa.String(50), index=True, nullable=True)
    original_event_url: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
    original_event_category: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    hash: so.Mapped[str] = so.mapped_column(sa.String(64), nullable=True)

    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id),
                                               index=True)
    owner: so.Mapped[User] = so.relationship(back_populates='events')

    feed_id: so.Mapped[Optional[int]] = so.mapped_column(sa.ForeignKey(Feed.id), index=True)
    feed: so.Mapped[Feed] = so.relationship(back_populates='events')

    in_collection: so.WriteOnlyMapped['Collection'] = so.relationship(
        secondary=collections, 
        primaryjoin=("collections.c.event_id == Event.id"),
        secondaryjoin=("collections.c.collection_id == Collection.id"),
        back_populates='events')
    
    def set_hash(self):
        dict = self.to_dict()
        #print(f'Start dict: {dict}')
        self.hash = create_hash(dict)
    
    def check_hash(self, dict):
        hash = create_hash(dict)
        #print(f'End dict: {dict}')
        return hash == self.hash
    
    def to_dict(self):
        data = {}
        for column in self.__table__.columns:
            col_val = getattr(self, column.name)
            if column.name in ['starts_at', 'ends_at', 'timestamp']:
                data[column.name] = col_val.replace(tzinfo=timezone.utc).isoformat() if col_val else None
            else:
                data[column.name] = col_val
        return data
    
    def from_dict(self, data):
        if 'starts_at_date' in data: #data is from web form
            if not data['starts_at_time']:
                data['starts_at_time'] = datetime.min.time()
            data['starts_at'] = local_to_utc(datetime.combine(data['starts_at_date'], data['starts_at_time']), data['timezone'])
            data.pop('starts_at_date')
            data.pop('starts_at_time')

            if data['ends_at_date']:
                if not data['ends_at_time']:
                    data['ends_at_time'] = datetime.max.time()
                data['ends_at'] = local_to_utc(datetime.combine(data['ends_at_date'], data['ends_at_time']), data['timezone'])
            data.pop('ends_at_date')
            data.pop('ends_at_time')
            data.pop('timezone')
        
        if 'location' in data:
            try:
                coords = location.parse_location(data['location'])
                data['location_lat'] = list(coords)[0]
                data['location_lon'] = list(coords)[1]
                data.pop('location')
            except Exception as e:
                #raise ValidationError(f"Location '{data['location']}'could not be parsed")
                pass #unparsed location will be added as 'location'
        if 'coords' in data:
            data['location_lat'] = list(data['coords'])[0]
            data['location_lon'] = list(data['coords'])[1]
            data.pop('coords')

        for field in data:
            val = data[field]
            if field in ['starts_at', 'ends_at'] and not isinstance(val, datetime):
                val = datetime.fromisoformat(val) if val else None
            setattr(self, field, val)
    
    def add_to_collection(self, collection):
        if not self.is_in_collection(collection):
            self.in_collection.add(collection)

    def remove_from_collection(self, collection):
        if self.is_in_collection(collection):
            self.in_collection.remove(collection)

    def is_in_collection(self, collection):
        query = self.in_collection.select().where(Collection.id == collection.id)
        return db.session.scalar(query) is not None
    
    def __repr__(self):
        return f'<Event {self.id} {self.title} {self.starts_at} {self.ends_at} {self.location_lat} {self.location_lon}>'
    
class Collection(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(140))
    description: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id),
                                               index=True)
    owner: so.Mapped[User] = so.relationship(back_populates='collections')

    events: so.WriteOnlyMapped['Event'] = so.relationship(
        secondary=collections, 
        primaryjoin=("collections.c.collection_id == Collection.id"),
        secondaryjoin=("collections.c.event_id == Event.id"),
        back_populates='in_collection')
    
    def add_event(self, event):
        if not self.contains_event(event):
            self.events.add(event)

    def remove_event(self, event):
        if self.contains_event(event):
            self.events.remove(event)

    def contains_event(self, event):
        query = self.events.select().where(Event.id == event.id)
        return db.session.scalar(query) is not None

    def __repr__(self):
        return '<Collection {}>'.format(self.title)
