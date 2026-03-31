"""File upload handling."""

import os

from flask import current_app, send_from_directory


def get_upload_dir():
    """Get the configured upload directory."""
    return current_app.config['UPLOAD_DIR']


def get_avatar_dir():
    """Get the avatars subdirectory."""
    return os.path.join(get_upload_dir(), 'avatars')


def serve_avatar(filename):
    """Serve an avatar file from the upload directory."""
    return send_from_directory(
        get_avatar_dir(),
        filename,
        mimetype='image/webp',
    )
