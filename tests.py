from datetime import datetime, timezone, timedelta
import unittest
from app import create_app, db
from app.models import User, Event, Collection, Organization
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    ELASTICSEARCH_URL = None

class UserModelCase(unittest.TestCase):

    users = []
    orgs = []

    def setUp(self):
        self.app = create_app(TestConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        self.create_users()
        self.create_orgs()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def create_users(self):
        new_users = []
        new_users.append(User(username='john', email='john@example.com'))
        new_users.append(User(username='susan', email='susan@example.com'))
        new_users.append(User(username='mary', email='mary@example.com'))
        new_users.append(User(username='david', email='david@example.com'))
        db.session.add_all(new_users)
        db.session.commit()
        self.users = new_users

    def create_orgs(self):
        new_orgs = []
        new_orgs.append(Organization(name='Org A'))
        new_orgs.append(Organization(name='Org B'))
        new_orgs.append(Organization(name='Org C'))
        new_orgs.append(Organization(name='Org D'))
        db.session.add_all(new_orgs)
        db.session.commit()
        self.orgs = new_orgs

    # def test_01_users(self):
    #     self.create_users()

    # def test_02_orgs(self):
    #     self.create_orgs()

    def test_03_user_password_hashing(self):
        #u = User(username='susan', email='susan@example.com')
        u = self.users[0]

        u.set_password('cat')
        self.assertFalse(u.check_password('dog'))
        self.assertTrue(u.check_password('cat'))

    def test_04_user_avatar(self):
        #u = User(username='john', email='john@example.com')
        u = self.users[0]
        self.assertEqual(u.avatar(128), ('https://www.gravatar.com/avatar/'
                                         'd4c74594d841139328695756648b6bd6'
                                         '?d=identicon&s=128'))

    def test_05_users_follow(self):
        # u1 = User(username='john', email='john@example.com')
        # u2 = User(username='susan', email='susan@example.com')
        # db.session.add(u1)
        # db.session.add(u2)
        # db.session.commit()
        u1, u2, *_ = self.users
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

    def test_06a_eventhash(self):
        o1 = self.orgs[0]
        now = datetime.now(timezone.utc)
        e1 = Event(starts_at=now + timedelta(days=30), title="event from Org A", description="test event description", organization_id=o1.id)
        db.session.add_all([e1])
        db.session.commit()
        self.assertTrue(e1.check_hash(e1.to_dict()))

    def test_06b_eventupdate(self):
        o1 = self.orgs[0]
        now = datetime.now(timezone.utc)
        e1 = Event(starts_at=now + timedelta(days=30), title="event from Org A", description="test event description", organization_id=o1.id)
        db.session.add_all([e1])
        db.session.commit()


    def test_06c_event(self):
        u1, u2, u3, u4 = self.users
        o1, o2, o3, o4 = self.orgs

        # create event
        now = datetime.now(timezone.utc)
        e1 = Event(starts_at=now + timedelta(days=30), title="event from Org A", description="test event description", organizer=o1,
                  timestamp=now + timedelta(seconds=1))
        e2 = Event(starts_at=now + timedelta(days=4), title="event from Org B", description="test event description", organizer=o2,
                  timestamp=now + timedelta(seconds=4))
        e3 = Event(starts_at=now + timedelta(days=365), title="event from Org C", description="test event description", organizer=o3,
                  timestamp=now + timedelta(seconds=3))
        e4 = Event(starts_at=now + timedelta(days=56), title="event from Org D", description="test event description", organizer=o4,
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

    def test_07_feed(self):
        print("test")

    
    # def test_07_collection(self):
    #     #add event to self
    #     #remove event from self
    #     return

    # def test_08_follow_events(self):
    #     #DOESN'T WORK/NOT NECESSARY IN NEW MODEL - users do not follow other users' events
    #     # create four users
    #     # u1 = User(username='john', email='john@example.com')
    #     # u2 = User(username='susan', email='susan@example.com')
    #     # u3 = User(username='mary', email='mary@example.com')
    #     # u4 = User(username='david', email='david@example.com')
    #     # db.session.add_all([u1, u2, u3, u4])
    #     u1, u2, u3, u4 = self.users
    #     o1, o2, o3, o4 = self.orgs

    #     # create event
    #     now = datetime.now(timezone.utc)
    #     e1 = Event(starts_at=now + timedelta(days=30), title="event from Org A", description="test event description", organizer=o1,
    #               timestamp=now + timedelta(seconds=1))
    #     e2 = Event(starts_at=now + timedelta(days=4), title="event from Org B", description="test event description", organizer=o2,
    #               timestamp=now + timedelta(seconds=4))
    #     e3 = Event(starts_at=now + timedelta(days=365), title="event from Org C", description="test event description", organizer=o3,
    #               timestamp=now + timedelta(seconds=3))
    #     e4 = Event(starts_at=now + timedelta(days=56), title="event from Org D", description="test event description", organizer=o4,
    #               timestamp=now + timedelta(seconds=2))
    #     db.session.add_all([e1, e2, e3, e4])
    #     db.session.commit()

    #     # setup the followers
    #     u1.follow(u2)  # john follows susan
    #     u1.follow(u4)  # john follows david
    #     u2.follow(u3)  # susan follows mary
    #     u3.follow(u4)  # mary follows david
    #     db.session.commit()

    #     # check the following events of each user
    #     f1 = db.session.scalars(u1.following_events()).all()
    #     f2 = db.session.scalars(u2.following_events()).all()
    #     f3 = db.session.scalars(u3.following_events()).all()
    #     f4 = db.session.scalars(u4.following_events()).all()
    #     self.assertEqual(f1, [e2, e4, e1])
    #     self.assertEqual(f2, [e2, e3])
    #     self.assertEqual(f3, [e3, e4])
    #     self.assertEqual(f4, [e4])

if __name__ == '__main__':
    unittest.main(verbosity=2)