import os
from flask import Flask, render_template

import config
from database import seed_db

from blueprints.admin.routes import admin_bp
from blueprints.manager.routes import manager_bp
from blueprints.customer.routes import customer_bp


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)

    app.register_blueprint(customer_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")
    app.register_blueprint(manager_bp, url_prefix="/manager")

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    return app


app = create_app()

if not os.path.exists(config.DATABASE_PATH):
    seed_db()
    print("Database seeded with Bangalore mock data.")

if __name__ == "__main__":
    app.run(debug=True, port=5000)
