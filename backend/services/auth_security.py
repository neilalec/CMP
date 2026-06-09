import hmac

from werkzeug.security import check_password_hash, generate_password_hash


PASSWORD_HASH_PREFIXES = ('scrypt:', 'pbkdf2:', 'argon2:', 'bcrypt:')


def is_password_hash(value):
    return isinstance(value, str) and value.startswith(PASSWORD_HASH_PREFIXES)


def hash_password(password):
    return generate_password_hash(str(password or ''))


def verify_password(stored_password, candidate_password):
    stored_password = str(stored_password or '')
    candidate_password = str(candidate_password or '')

    if is_password_hash(stored_password):
        return check_password_hash(stored_password, candidate_password)

    # Legacy plaintext compatibility. Successful login upgrades the stored value.
    return hmac.compare_digest(stored_password, candidate_password)


def needs_password_rehash(stored_password):
    return not is_password_hash(stored_password)
