from app import app, db, User, Task, Inquiry, Log
import unittest
from flask import url_for
from flask_login import login_user

class AdminTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        self.app = app.test_client()
        with app.app_context():
            db.create_all()

            # Create test users with unique emails for testing
            self.admin = User(email='test_admin@test.com', name='Test Admin User', is_admin=True)
            self.user = User(email='test_user@test.com', name='Test Regular User')
            self.facilitator = User(email='test_facilitator@test.com', name='Test Facilitator User', is_facilitator=True)
            db.session.add_all([self.admin, self.user, self.facilitator])
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def login_admin(self):
        with self.app:
            login_user(self.admin)
            return self.app

    def test_admin_dashboard_access(self):
        """Test that admin can access dashboard"""
        with self.login_admin() as client:
            response = client.get('/admin/dashboard')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Admin Dashboard', response.data)

    def test_admin_users_access(self):
        """Test that admin can access users page"""
        with self.login_admin() as client:
            response = client.get('/admin/users')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Manage Users', response.data)

    def test_admin_tasks_access(self):
        """Test that admin can access tasks page"""
        with self.login_admin() as client:
            response = client.get('/admin/tasks')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'All Tasks', response.data)

    def test_admin_logs_access(self):
        """Test that admin can access logs page"""
        with self.login_admin() as client:
            response = client.get('/admin/logs')
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'System Logs', response.data)

    def test_non_admin_cannot_access_admin(self):
        """Test that non-admin users cannot access admin pages"""
        with self.app:
            login_user(self.user)
            response = self.app.get('/admin/dashboard')
            self.assertEqual(response.status_code, 302)  # Should redirect

    def test_admin_user_count(self):
        """Test that admin dashboard shows correct user count"""
        with self.login_admin() as client:
            response = client.get('/admin/dashboard')
            # Should show 3 users
            self.assertIn(b'3', response.data)

if __name__ == '__main__':
    unittest.main()
