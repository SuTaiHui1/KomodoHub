from passlib.context import CryptContext


# Use pbkdf2_sha256 to avoid bcrypt backend issues on Windows/Py3.11
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)
