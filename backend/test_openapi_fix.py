import warnings
warnings.simplefilter('always')

# Test without intervention router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Test", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Test openapi generation
try:
    schema = app.openapi()
    print("SUCCESS: OpenAPI schema generated without error")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")