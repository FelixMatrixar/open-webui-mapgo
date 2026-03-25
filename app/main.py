from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware  
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api import tools

app = FastAPI(title="MapGO Backend API")

# ==========================================
# 🛡️ CORS MIDDLEWARE 
# ==========================================
# This allows external websites (like Open WebUI on port 8080) 
# to securely request data from this API on port 8000.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, change "*" to ["http://localhost:8080"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register the slowapi exception handler
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(tools.router, prefix="/tools", tags=["Tools"])

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # 🛡️ The Corrected CSP
    csp = (
        "default-src 'self'; "
        "frame-src https://www.google.com http://googleusercontent.com; "
        "style-src 'self' 'unsafe-inline'; "
        "script-src 'self' 'unsafe-inline' https://unpkg.com;"
    )
    
    response.headers["Content-Security-Policy"] = csp
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    return response