from app.main import app
from fastapi.openapi.utils import get_openapi
import json

openapi = get_openapi(title='KESHAV', version='1.0.0', routes=app.routes)
with open('openapi.json', 'w') as f:
    json.dump(openapi, f, indent=2)
print('OpenAPI JSON written successfully')
print('Keys:', list(openapi.keys()))