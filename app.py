"""Development entry point — run with: python app.py"""

from app import create_app

application = create_app()

if __name__ == '__main__':
    import os
    application.run(debug=os.getenv('FLASK_DEBUG', '0') == '1', host='0.0.0.0', port=5000)
