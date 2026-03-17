from __future__ import annotations

from flask import Flask
from flask_cors import CORS

from .config import Config


def create_app(config_overrides: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if config_overrides:
        app.config.update(config_overrides)

    from .db import db
    from .schema import ensure_runtime_schema
    from .services.crypto import get_platform_public_key_pem, load_or_create_platform_signing_key

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    db.init_app(app)

    platform_signing_key = load_or_create_platform_signing_key(app.config["PLATFORM_SIGNING_KEY_PATH"])
    app.platform_signing_key = platform_signing_key
    app.platform_public_key_pem = get_platform_public_key_pem(platform_signing_key)

    from .routes.web import web_bp
    from .routes.api import api_bp

    app.register_blueprint(api_bp)
    app.register_blueprint(web_bp)

    with app.app_context():
        db.create_all()
        ensure_runtime_schema()

    return app
