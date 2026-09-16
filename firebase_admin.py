import json
import os

import firebase_admin
from firebase_admin import credentials, firestore


def get_firebase_app():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON")
    if raw:
        return firebase_admin.initialize_app(credentials.Certificate(json.loads(raw)))

    path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_FILE", "firebase-service-account.json")
    if os.path.exists(path):
        return firebase_admin.initialize_app(credentials.Certificate(path))

    return firebase_admin.initialize_app()


firebase_app = get_firebase_app()
db = firestore.client(app=firebase_app)
