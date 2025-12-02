from app import app, db, User

with app.app_context():
    db.create_all()

    # Check and create admin user
    if not User.query.filter_by(email='admin@test.com').first():
        admin = User(email='admin@test.com', name='Admin User', is_admin=True)
        db.session.add(admin)
        print("Admin user created: admin@test.com")
    else:
        print("Admin user already exists: admin@test.com")

    # Check and create regular user
    if not User.query.filter_by(email='user@test.com').first():
        user = User(email='user@test.com', name='Regular User')
        db.session.add(user)
        print("Regular user created: user@test.com")
    else:
        print("Regular user already exists: user@test.com")

    # Check and create facilitator user
    if not User.query.filter_by(email='facilitator@test.com').first():
        facilitator = User(email='facilitator@test.com', name='Facilitator User', is_facilitator=True)
        db.session.add(facilitator)
        print("Facilitator user created: facilitator@test.com")
    else:
        print("Facilitator user already exists: facilitator@test.com")

    db.session.commit()
    print("Test users setup complete.")
