from attendance import create_app
from attendance.db import init_db

app = create_app()

with app.app_context():
    init_db()
    print("Database initialized from schema.sql")
