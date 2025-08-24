import os
from flask import Flask
from flask_login import LoginManager
from .routes import main_bp
from .auth import auth_bp, user_loader, SimpleUser
from .startup import initial_run


def create_app():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    app = Flask(
        __name__,
        template_folder=os.path.join(base_dir, 'templates'),
        static_folder=os.path.join(base_dir, 'static')
    )
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
    app.config['OPENAI_API_KEY'] = os.getenv('OPENAI_API_KEY', '')

    # Login
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return user_loader(user_id)

    # Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)

    # Optional first run at startup (disabled by default)
    if os.getenv('RUN_ON_STARTUP', '0') == '1':
        try:
            initial_run(app.root_path)
        except Exception:
            pass

    return app
