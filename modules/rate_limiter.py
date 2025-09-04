import time

# basic per-user rate limit: max 2 requests per 60 seconds
REQUESTS = {}
LIMIT = 2
WINDOW = 60

def check_rate_limit(user_id: int) -> bool:
    now = time.time()
    user = REQUESTS.get(user_id, [])
    # drop old
    user = [t for t in user if now - t < WINDOW]
    if len(user) >= LIMIT:
        REQUESTS[user_id] = user
        return False
    user.append(now)
    REQUESTS[user_id] = user
    return True
