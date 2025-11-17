from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Table, MetaData
from sqlalchemy.orm import declarative_base, sessionmaker
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'user'
    
    id = Column(Integer, primary_key=True)
    fullname = Column(String, nullable=True)
    email = Column(String, nullable=False, unique=True)
    password_hash = Column(String, nullable=False)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

# --- Connect to existing database ---
engine = create_engine("sqlite:///site.db")
metadata = MetaData(bind=engine)
metadata.reflect(engine)
user_table = Table('user', metadata, autoload_with=engine)

# --- Add 'fullname' column if missing ---
if 'fullname' not in user_table.c:
    with engine.connect() as conn:
        conn.execute('ALTER TABLE user ADD COLUMN fullname TEXT')
        print("Added missing 'fullname' column.")

# --- Create session ---
Session = sessionmaker(bind=engine)
session = Session()

# --- Optional: populate fullname for existing users ---
users_without_fullname = session.query(User).filter(User.fullname == None).all()
for user in users_without_fullname:
    user.fullname = "Unknown Name"  # or combine first_name/last_name if available
session.commit()
print(f"Updated {len(users_without_fullname)} users with a default fullname.")

# --- Test query ---
admins = session.query(User).filter(User.is_admin == True).all()
for admin in admins:
    print(f"Admin found: {admin.fullname}, {admin.email}")
