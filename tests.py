import os
os.environ['DATABASE_URL'] = 'sqlite://'

from datetime import datetime, timezone, timedelta
import unittest
from app import app, db
from app.models import User, Event, Collection


class UserModelCase(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        u = User(username='susan', email='susan@example.com')
        u.set_password('cat')
        self.assertFalse(u.check_password('dog'))
        self.assertTrue(u.check_password('cat'))

    def test_avatar(self):
        u = User(username='john', email='john@example.com')
        self.assertEqual(u.avatar(128), ('https://www.gravatar.com/avatar/'
                                         'd4c74594d841139328695756648b6bd6'
                                         '?d=identicon&s=128'))

    def test_follow(self):
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        db.session.add(u1)
        db.session.add(u2)
        db.session.commit()
        following = db.session.scalars(u1.following.select()).all()
        followers = db.session.scalars(u2.followers.select()).all()
        self.assertEqual(following, [])
        self.assertEqual(followers, [])

        u1.follow(u2)
        db.session.commit()
        self.assertTrue(u1.is_following(u2))
        self.assertEqual(u1.following_count(), 1)
        self.assertEqual(u2.followers_count(), 1)
        u1_following = db.session.scalars(u1.following.select()).all()
        u2_followers = db.session.scalars(u2.followers.select()).all()
        self.assertEqual(u1_following[0].username, 'susan')
        self.assertEqual(u2_followers[0].username, 'john')

        u1.unfollow(u2)
        db.session.commit()
        self.assertFalse(u1.is_following(u2))
        self.assertEqual(u1.following_count(), 0)
        self.assertEqual(u2.followers_count(), 0)

    def test_follow_events(self):
        # create four users
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        u3 = User(username='mary', email='mary@example.com')
        u4 = User(username='david', email='david@example.com')
        db.session.add_all([u1, u2, u3, u4])

        # create event
        now = datetime.now(timezone.utc)
        e1 = Event(start_date=now + timedelta(days=30), title="event from john", description="test event description", author=u1,
                  timestamp=now + timedelta(seconds=1))
        e2 = Event(start_date=now + timedelta(days=4), title="event from susan", description="test event description", author=u2,
                  timestamp=now + timedelta(seconds=4))
        e3 = Event(start_date=now + timedelta(days=365), title="event from mary", description="test event description", author=u3,
                  timestamp=now + timedelta(seconds=3))
        e4 = Event(start_date=now + timedelta(days=56), title="event from david", description="test event description", author=u4,
                  timestamp=now + timedelta(seconds=2))
        db.session.add_all([e1, e2, e3, e4])
        db.session.commit()

        #start date, no time, no end date
        #start date, no time, end date, no end time
        #start date, no time, end date, end time
        #start date, time, no end date, no end time
        #start date, time, end date, no end time
        #start date, time, end date, end time
        #no start date, no time, no end date, no end time
        #no start date, time, no end date, no end time
        #no start date, no time, end date, no end time
        #no start date, no time, no end date, end time
        #no start date, no time, end date, end time

        # setup the followers
        u1.follow(u2)  # john follows susan
        u1.follow(u4)  # john follows david
        u2.follow(u3)  # susan follows mary
        u3.follow(u4)  # mary follows david
        db.session.commit()

        # check the following posts of each user
        f1 = db.session.scalars(u1.following_events()).all()
        f2 = db.session.scalars(u2.following_events()).all()
        f3 = db.session.scalars(u3.following_events()).all()
        f4 = db.session.scalars(u4.following_events()).all()
        self.assertEqual(f1, [e2, e4, e1])
        self.assertEqual(f2, [e2, e3])
        self.assertEqual(f3, [e3, e4])
        self.assertEqual(f4, [e4])

    
class EventCollectionModelCase(unittest.TestCase):
    def setUp(self):
        self.app_context = app.app_context()
        self.app_context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
    
    def test_event(self):
        # create users
        u1 = User(username='john', email='john@example.com')
        u2 = User(username='susan', email='susan@example.com')
        db.session.add_all([u1, u2])

        # create event
        now = datetime.now(timezone.utc)
        e1 = Event(start_date=now + timedelta(days=30), title="event from john", description="test event description", author=u1,
                  timestamp=now + timedelta(seconds=1))
        e2 = Event(start_date=now + timedelta(days=4), title="event from susan", description="test event description", author=u2,
                  timestamp=now + timedelta(seconds=4))
        e3 = Event(start_date=now + timedelta(days=365), title="event from mary", description="test event description", author=u1,
                  timestamp=now + timedelta(seconds=3))
        e4 = Event(start_date=now + timedelta(days=56), title="event from david", description="test event description", author=u2,
                  timestamp=now + timedelta(seconds=2))
        db.session.add_all([e1, e2, e3, e4])
        db.session.commit()

        # create collections
        c1 = Collection(title="Collection 1", description="Test description", owner=u1,
                        timestamp=now + timedelta(seconds=4))
        c2 = Collection(title="Collection 2", description="Test description", owner=u2,
                        timestamp=now + timedelta(seconds=4))
        db.session.add_all([c1, c2])
        db.session.commit()

        
        # add self to collection
        c1.add_event(e1)
        c2.add_event(e2)
        e3.add_to_collection(c1)
        e4.add_to_collection(c2)

        # remove self from collection
        c1.remove_event(e1)
        c1.remove_event(e2)
        c2.remove_event(e1)
        c2.remove_event(e2)
        e3.remove_from_collection(c1)
        e4.remove_from_collection(c2)

    
    def test_collection(self):
        #add event to self
        #remove event from self
        return

if __name__ == '__main__':
    unittest.main(verbosity=2)