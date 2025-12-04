from app import app, db, User, Task, Inquiry, Log
import unittest

class AdminTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

            # Create test users with unique emails for testing
            self.admin = User(email='test_admin@test.com', name='Test Admin User', is_admin=True, password_hash='test')
            self.user = User(email='test_user@test.com', name='Test Regular User', password_hash='test')
            self.facilitator = User(email='test_facilitator@test.com', name='Test Facilitator User', is_facilitator=True, password_hash='test')
            db.session.add_all([self.admin, self.user, self.facilitator])
            db.session.commit()

            # Store IDs for use in tests
            self.admin_id = self.admin.id

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def test_user_creation(self):
        """Test that users are created correctly"""
        with app.app_context():
            admin = User.query.filter_by(email='test_admin@test.com').first()
            self.assertIsNotNone(admin)
            self.assertTrue(admin.is_admin)
            self.assertEqual(admin.name, 'Test Admin User')

    def test_task_creation(self):
        """Test that tasks can be created"""
        with app.app_context():
            task = Task(title='Test Task', description='Test Description', created_by=self.admin_id)
            db.session.add(task)
            db.session.commit()

            saved_task = Task.query.filter_by(title='Test Task').first()
            self.assertIsNotNone(saved_task)
            self.assertEqual(saved_task.description, 'Test Description')

    def test_inquiry_creation(self):
        """Test that inquiries can be created"""
        with app.app_context():
            inquiry = Inquiry(sender_email='test@example.com', subject='Test Subject', message='Test Message')
            db.session.add(inquiry)
            db.session.commit()

            saved_inquiry = Inquiry.query.filter_by(subject='Test Subject').first()
            self.assertIsNotNone(saved_inquiry)
            self.assertEqual(saved_inquiry.sender_email, 'test@example.com')

    def test_log_creation(self):
        """Test that logs can be created"""
        with app.app_context():
            log = Log(user_id=self.admin_id, action='test_action', details='Test details')
            db.session.add(log)
            db.session.commit()

            saved_log = Log.query.filter_by(action='test_action').first()
            self.assertIsNotNone(saved_log)
            self.assertEqual(saved_log.details, 'Test details')

    def test_user_count(self):
        """Test that user count is correct"""
        with app.app_context():
            count = User.query.count()
            self.assertEqual(count, 3)  # admin, user, facilitator

    def test_admin_routes_exist(self):
        """Test that admin routes return responses (even if redirects)"""
        # Test admin login page
        response = self.app.get('/admin/login')
        self.assertEqual(response.status_code, 200)

        # Test regular login page
        response = self.app.get('/login')
        self.assertEqual(response.status_code, 200)

        # Test registration page
        response = self.app.get('/register')
        self.assertEqual(response.status_code, 200)

if __name__ == '__main__':
    unittest.main()
