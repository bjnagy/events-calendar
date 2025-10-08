from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone
from typing import Optional
import sqlalchemy as sa
import sqlalchemy.orm as so
from app import db, login
from flask_login import UserMixin
from hashlib import md5
from time import time
import jwt
from app import app

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

class User(UserMixin, db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    username: so.Mapped[str] = so.mapped_column(sa.String(64), index=True,
                                                unique=True)
    email: so.Mapped[str] = so.mapped_column(sa.String(120), index=True,
                                             unique=True)
    password_hash: so.Mapped[Optional[str]] = so.mapped_column(sa.String(256))
    about_me: so.Mapped[Optional[str]] = so.mapped_column(sa.String(140))
    last_seen: so.Mapped[Optional[datetime]] = so.mapped_column(
        default=lambda: datetime.now(timezone.utc))

    events: so.WriteOnlyMapped['Event'] = so.relationship(
        back_populates='author')
    
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

    def __repr__(self):
        return '<User {}>'.format(self.username)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def avatar(self, size):
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
            .join(Event.author.of_type(Source))
            .join(Source.followers.of_type(Follower), isouter=True)
            .where(sa.or_(
                Follower.id == self.id,
                Source.id == self.id,
            ))
            .group_by(Event)
            .order_by(Event.timestamp.desc())
        )
        
    def get_reset_password_token(self, expires_in=600):
        return jwt.encode(
            {'reset_password': self.id, 'exp': time() + expires_in},
            app.config['SECRET_KEY'], algorithm='HS256')

    @staticmethod
    def verify_reset_password_token(token):
        try:
            id = jwt.decode(token, app.config['SECRET_KEY'],
                            algorithms=['HS256'])['reset_password']
        except:
            return
        return db.session.get(User, id)



    def __repr__(self):
        return '<Event {}>'.format(self.title)
    
class Event(db.Model):
    id: so.Mapped[int] = so.mapped_column(primary_key=True)
    title: so.Mapped[str] = so.mapped_column(sa.String(140))
    description: so.Mapped[str] = so.mapped_column(sa.String(), nullable=True)
    start_date: so.Mapped[datetime] = so.mapped_column(sa.Date(), nullable=False)
    start_time: so.Mapped[datetime] = so.mapped_column(sa.Time(), nullable=True)
    end_date: so.Mapped[datetime] = so.mapped_column(sa.Date(), nullable=True)
    end_time: so.Mapped[datetime] = so.mapped_column(sa.Time(), nullable=True)
    timestamp: so.Mapped[datetime] = so.mapped_column(
        index=True, default=lambda: datetime.now(timezone.utc))
    user_id: so.Mapped[int] = so.mapped_column(sa.ForeignKey(User.id),
                                               index=True)
    author: so.Mapped[User] = so.relationship(back_populates='events')

    in_collection: so.WriteOnlyMapped['Collection'] = so.relationship(
        secondary=collections, 
        primaryjoin=("collections.c.event_id == Event.id"),
        secondaryjoin=("collections.c.collection_id == Collection.id"),
        back_populates='events')
    
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
        return '<Event {}>'.format(self.title)
    
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
