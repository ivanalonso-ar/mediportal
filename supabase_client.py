from functools import lru_cache

from config import settings


@lru_cache(maxsize=1)
def get_supabase_client():
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        return None
    from supabase import create_client

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
