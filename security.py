import bcrypt

def get_pin_hash(pin: str) -> str:
    """Genera un hash bcrypt a partir de un PIN de texto plano."""
    pin_bytes = pin.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pin_bytes, salt).decode('utf-8')

def verify_pin(plain_pin: str, hashed_pin: str) -> bool:
    """Verifica si el PIN coincide con el hash almacenado."""
    try:
        return bcrypt.checkpw(
            plain_pin.encode('utf-8'),
            hashed_pin.encode('utf-8')
        )
    except Exception:
        return False