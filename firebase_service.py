import json
import os

import firebase_admin
from firebase_admin import credentials, firestore


class FirebaseConfigurationError(RuntimeError):
    pass


def get_firebase_app():
    if firebase_admin._apps:
        return firebase_admin.get_app()

    raw = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_FILE", "firebase-service-account.json")

    if raw:
        try:
            service_account = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise FirebaseConfigurationError(
                "FIREBASE_SERVICE_ACCOUNT_JSON is not valid JSON."
            ) from exc
        return firebase_admin.initialize_app(credentials.Certificate(service_account))

    if os.path.isfile(path):
        return firebase_admin.initialize_app(credentials.Certificate(path))

    raise FirebaseConfigurationError(
        "Firebase Admin credentials are missing. In Codespaces, set "
        "FIREBASE_SERVICE_ACCOUNT_JSON as a Codespaces secret, or set "
        "FIREBASE_SERVICE_ACCOUNT_FILE to the path of your downloaded Firebase "
        "service-account JSON. Do not commit the service-account JSON to GitHub."
    )


firebase_app = get_firebase_app()
db = firestore.client(app=firebase_app)
