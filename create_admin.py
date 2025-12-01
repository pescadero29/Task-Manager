from app import app, db, User

with app.app_context():
    db.create_all()

    # Create admin user
    admin = User(email='admin@test.com', name='Admin User', is_admin=True)
    db.session.add(admin)

    # Create regular user
    user = User(email='user@test.com', name='Regular User')
    db.session.add(user)

    # Create facilitator user
    facilitator = User(email='facilitator@test.com', name='Facilitator User', is_facilitator=True)
    db.session.add(facilitator)

    db.session.commit()
    print("Test users created:")
    print("- Admin: admin@test.com")
    print("- User: user@test.com")
    print("- Facilitator: facilitator@test.com")
