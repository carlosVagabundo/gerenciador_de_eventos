"""Ponto de entrada. O Render/gunicorn usam `app:app` e o PythonAnywhere importa `app`."""
from eventmanager import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
