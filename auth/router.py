from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
import jwt
from jwt import PyJWTError
import bcrypt
import secrets
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from .oauth import GoogleOAuth
from .passkeys import WebAuthnPasskey
from .challenge_store import get_challenge_store_instance
from database import get_db
from models import User

load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])
security = HTTPBearer()

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Challenge store for passkey authentication
challenge_store = get_challenge_store_instance()
CHALLENGE_EXPIRE_MINUTES = 5


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: Optional[str] = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    user: dict  # Changed from User to dict to avoid conflict


class GoogleAuthRequest(BaseModel):
    token: str


class GoogleAuthCallback(BaseModel):
    code: str
    state: Optional[str] = None


class PasskeyRegistrationRequest(BaseModel):
    email: EmailStr
    credential_id: str
    public_key: str


class PasskeyAuthRequest(BaseModel):
    email: EmailStr
    credential_id: str
    authenticator_data: str
    client_data_json: str
    signature: str


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except PyJWTError:
        return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    return user


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


async def cleanup_expired_challenges():
    """Remove expired challenges from the store"""
    return await challenge_store.cleanup_expired()


@router.post("/register", response_model=Token)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    user_id = secrets.token_urlsafe(16)
    hashed_password = hash_password(user_data.password)

    user = User(
        id=user_id,
        email=user_data.email,
        name=user_data.name,
        password_hash=hashed_password,
    )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user_id}, expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.post("/login", response_model=Token)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    # Find user by email
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Verify password
    if not user.password_hash or not verify_password(
        user_data.password, user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.post("/google", response_model=Token)
async def google_auth(auth_request: GoogleAuthRequest, db: Session = Depends(get_db)):
    # Verify Google OAuth token
    google_user = await GoogleOAuth.verify_token(auth_request.token)

    if not google_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google token"
        )

    email = google_user.get("email")
    google_id = google_user.get("sub")
    name = google_user.get("name")

    if not email or not google_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Google user data"
        )

    # Check if user exists
    user = db.query(User).filter(User.google_id == google_id).first()

    if not user:
        # Create new user
        user_id = secrets.token_urlsafe(16)
        user = User(id=user_id, email=email, name=name, google_id=google_id)
        db.add(user)
        db.commit()
        db.refresh(user)

    # Create access token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.id}, expires_delta=access_token_expires
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user={"id": user.id, "email": user.email, "name": user.name},
    )


@router.get("/google/url")
async def get_google_auth_url():
    """Get Google OAuth authorization URL"""
    try:
        auth_url = GoogleOAuth.get_authorization_url()
        return {"authorization_url": auth_url}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e)
        )


@router.post("/google/callback", response_model=Token)
async def google_auth_callback(
    callback_data: GoogleAuthCallback, db: Session = Depends(get_db)
):
    """Handle Google OAuth callback"""
    try:
        # Exchange code for token
        token_data = await GoogleOAuth.exchange_code_for_token(callback_data.code)

        if not token_data or "access_token" not in token_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to exchange code for token",
            )

        access_token = token_data["access_token"]

        # Get user info
        google_user = await GoogleOAuth.get_user_info(access_token)

        if not google_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Failed to get user info from Google",
            )

        email = google_user.get("email")
        google_id = google_user.get("sub")
        name = google_user.get("name")

        if not email or not google_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid Google user data",
            )

        # Check if user exists
        user = db.query(User).filter(User.google_id == google_id).first()

        if not user:
            # Create new user
            user_id = secrets.token_urlsafe(16)
            user = User(id=user_id, email=email, name=name, google_id=google_id)
            db.add(user)
            db.commit()
            db.refresh(user)

        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.id}, expires_delta=access_token_expires
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            user={"id": user.id, "email": user.email, "name": user.name},
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google authentication failed: {str(e)}",
        )


@router.post("/passkey/challenge")
async def get_passkey_challenge(email: EmailStr = None):
    """
    Get a challenge for passkey registration/authentication
    Optionally provide email to store challenge for later verification
    """
    challenge = WebAuthnPasskey.generate_challenge()

    # Store challenge with expiration if email provided
    if email:
        await challenge_store.set_challenge(email, challenge, CHALLENGE_EXPIRE_MINUTES)

    return {"challenge": challenge}


@router.post("/passkey/register")
async def register_passkey(
    request: PasskeyRegistrationRequest, db: Session = Depends(get_db)
):
    """Register a passkey for a user with validation"""
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Validate the credential_id and public_key format
    try:
        # Ensure credential_id is base64url encoded
        if not request.credential_id or len(request.credential_id) < 16:
            raise ValueError("Invalid credential ID format")

        # Ensure public_key is base64url encoded
        if not request.public_key or len(request.public_key) < 32:
            raise ValueError("Invalid public key format")

        # Try to decode to verify they're valid base64url
        WebAuthnPasskey.decode_base64url(request.credential_id)
        WebAuthnPasskey.decode_base64url(request.public_key)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid passkey data: {str(e)}",
        )

    # Update user with passkey info
    user.passkey_credential_id = request.credential_id
    user.passkey_public_key = request.public_key
    db.commit()

    return {"message": "Passkey registered successfully"}


@router.post("/passkey/auth", response_model=Token)
async def authenticate_passkey(
    request: PasskeyAuthRequest, db: Session = Depends(get_db)
):
    # Find user by email
    user = db.query(User).filter(User.email == request.email).first()
    if not user or not user.passkey_credential_id or not user.passkey_public_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Passkey not registered for this user",
        )

    # Verify credential ID matches
    if request.credential_id != user.passkey_credential_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credential ID"
        )

    # Perform full WebAuthn passkey verification
    try:
        # Get the origin from environment or use default
        origin = os.getenv("FRONTEND_URL", "http://localhost:5173")

        # Retrieve and validate stored challenge
        challenge = await challenge_store.get_challenge(request.email)
        if not challenge:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="No challenge found or challenge expired. Please request a new challenge first.",
            )

        # Remove used challenge (one-time use)
        await challenge_store.delete_challenge(request.email)

        # Verify the complete WebAuthn assertion
        is_valid = await WebAuthnPasskey.verify_passkey_authentication(
            credential_id=request.credential_id,
            stored_public_key=user.passkey_public_key,
            authenticator_data_b64=request.authenticator_data,
            client_data_json_b64=request.client_data_json,
            signature_b64=request.signature,
            challenge=challenge,
            origin=origin,
        )

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Passkey verification failed",
            )

        # Create access token
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.id}, expires_delta=access_token_expires
        )

        return Token(
            access_token=access_token,
            token_type="bearer",
            user={"id": user.id, "email": user.email, "name": user.name},
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Passkey authentication failed: {str(e)}",
        )


@router.get("/me")
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    return {
        "id": current_user.id,
        "email": current_user.email,
        "name": current_user.name,
    }


@router.post("/logout")
async def logout():
    """Logout user (client-side token removal)"""
    return {"message": "Logged out successfully"}


class TokenValidationRequest(BaseModel):
    token: str


@router.post("/validate")
async def validate_token(
    request: TokenValidationRequest, db: Session = Depends(get_db)
):
    """Validate JWT token"""
    payload = verify_token(request.token)
    if not payload:
        return {"valid": False}

    user_id = payload.get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return {"valid": False}

    return {
        "valid": True,
        "user": {"id": user.id, "email": user.email, "name": user.name},
    }
