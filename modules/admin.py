import os
OWNER_ID = int(os.getenv("OWNER_ID", "0"))

def is_owner(user_id: int) -> bool:
    return user_id == OWNER_ID
