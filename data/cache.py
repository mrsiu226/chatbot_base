# cache.py
import redis
import json
import hashlib
from datetime import timedelta

r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# Cache context (history/session)
def get_context(session_id):
    cached = r.get(f"context:{session_id}")
    if cached:
        return json.loads(cached)
    return None

def save_context(session_id, context, ttl_minutes=10):
    r.setex(f"context:{session_id}", timedelta(minutes=ttl_minutes), json.dumps(context))

# Cache RAG (vector search)
def hash_question(question):
    return hashlib.md5(question.encode()).hexdigest()

def get_rag_cache(question):
    key = f"rag:{hash_question(question)}"
    cached = r.get(key)
    if cached:
        return json.loads(cached)
    return None

def save_rag_cache(question, docs, ttl_minutes=10):
    key = f"rag:{hash_question(question)}"
    r.setex(key, timedelta(minutes=ttl_minutes), json.dumps(docs))

def clear_context_cache(session_id):
    r.delete(f"context:{session_id}")

def clear_rag_cache(question):
    r.delete(f"rag:{hash_question(question)}")
