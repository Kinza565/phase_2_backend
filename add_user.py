from app.database import SessionLocal, create_tables
from app.models import User
from app.routers.auth import get_password_hash

# Create tables if not exist
create_tables()

# Create a session
db = SessionLocal()

# Check if user already exists
existing_user = db.query(User).filter(User.email == "test@example.com").first()
if existing_user:
    print("User already exists")
else:
    # Create a test user
    email = "test@example.com"
    password = "password"
    hashed_password = get_password_hash(password)
    user = User(email=email, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    print("Test user created: test@example.com / password")

db.close()
