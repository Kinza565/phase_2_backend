from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from jose import JWTError, jwt
import bcrypt
from sqlalchemy.orm import Session

from ..config import ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY
from ..database import get_db
from ..models import User
from ..schemas.user import AuthResponse, TokenData, User as UserSchema, UserCreate

router = APIRouter()

ALGORITHM = "HS256"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    password_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8') if isinstance(hashed_password, str) else hashed_password
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt directly."""
    password_bytes = password.encode('utf-8')[:72]  # Truncate to 72 bytes (bcrypt limit)
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def authenticate_user(db: Session, email: str, password: str) -> Optional[User]:
    """Authenticate a user."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not verify_password(password, user.hashed_password):
        return None
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _get_token_from_request(request: Request) -> Optional[str]:
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        return auth_header.split(" ", 1)[1].strip()
    return request.cookies.get("token")


def _decode_token(token: str) -> Optional[TokenData]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if not email:
            return None
        return TokenData(email=email)
    except JWTError:
        return None


def _build_user_payload(user: User) -> dict:
    return {
        "id": str(user.id),
        "email": user.email,
        "createdAt": user.created_at.isoformat(),
        "updatedAt": user.updated_at.isoformat(),
    }


async def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
) -> User:
    """Get current user from JWT token."""
    token = _get_token_from_request(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token_data = _decode_token(token)
    if not token_data or not token_data.email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


@router.post("/signup", response_model=AuthResponse)
def signup(
    user: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """Create a new user account."""
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(user.password)
    db_user = User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    access_token = create_access_token(data={"sub": db_user.email})
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": db_user,
    }


@router.post("/signin", response_model=AuthResponse)
def signin(
    user: UserCreate,
    response: Response,
    db: Session = Depends(get_db),
):
    """Sign in and get JWT token."""
    db_user = authenticate_user(db, user.email, user.password)
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(data={"sub": db_user.email})
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,
        secure=False,  # Set to True in production with HTTPS
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": db_user,
    }


@router.post("/signout")
async def signout(response: Response):
    """Sign out and clear session cookie."""
    response.delete_cookie(key="token")
    return {"success": True}


@router.get("/session")
async def get_session(request: Request, db: Session = Depends(get_db)):
    """Get current session from JWT."""
    token = _get_token_from_request(request)
    if not token:
        return {"session": None, "user": None}

    token_data = _decode_token(token)
    if not token_data or not token_data.email:
        return {"session": None, "user": None}

    user = db.query(User).filter(User.email == token_data.email).first()
    if not user:
        return {"session": None, "user": None}

    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    return {
        "session": {
            "id": token,
            "expiresAt": datetime.fromtimestamp(payload.get("exp")).isoformat(),
            "userId": str(user.id),
        },
        "user": _build_user_payload(user),
    }


@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information."""
    return current_user


# Better-auth compatibility endpoints (optional)

@router.post("/sign-in/email")
async def sign_in_email(request: Request, response: Response, db: Session = Depends(get_db)):
    """Sign in with email and password (better-auth compatible)."""
    data = await request.json()
    email = data.get("email")
    password = data.get("password")

    user = authenticate_user(db, email, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    access_token = create_access_token(data={"sub": user.email})
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {
        "user": _build_user_payload(user),
        "session": {
            "id": access_token,
            "expiresAt": (datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).isoformat(),
            "userId": str(user.id),
        },
    }


@router.post("/sign-up/email")
async def sign_up_email(request: Request, response: Response, db: Session = Depends(get_db)):
    """Sign up with email and password (better-auth compatible)."""
    data = await request.json()
    email = data.get("email")
    password = data.get("password")

    db_user = db.query(User).filter(User.email == email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_password = get_password_hash(password)
    db_user = User(email=email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    access_token = create_access_token(data={"sub": db_user.email})
    response.set_cookie(
        key="token",
        value=access_token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

    return {
        "user": _build_user_payload(db_user),
        "session": {
            "id": access_token,
            "expiresAt": (datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).isoformat(),
            "userId": str(db_user.id),
        },
    }


@router.post("/sign-out")
async def sign_out(response: Response):
    """Sign out (better-auth compatible)."""
    response.delete_cookie(key="token")
    return {"success": True}
