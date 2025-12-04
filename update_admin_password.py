from app import app, db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    admin = User.query.filter_by(email='admin@test.com').first()
    if admin:
        admin.password_hash = generate_password_hash('admin1234')
        db.session.commit()
        print('Admin password updated to admin1234.')
    else:
        print('Admin user not found.')
