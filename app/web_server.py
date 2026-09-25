"""Serve desktop assets and archived images through the same local origin."""

import os
import re

from bottle import Bottle, HTTPError, static_file


def create_app(web_dir, state_dir):
    app = Bottle()

    @app.get("/task-images/<task_id>/images/<image:path>")
    def task_image(task_id, image):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
            raise HTTPError(404)
        root = os.path.realpath(os.path.join(state_dir(), task_id, "images"))
        target = os.path.realpath(os.path.join(root, image))
        try:
            if os.path.commonpath((root, target)) != root or not os.path.isfile(target):
                raise HTTPError(404)
        except ValueError:
            raise HTTPError(404)
        return static_file(os.path.relpath(target, root), root=root)

    @app.get("/")
    def index():
        return static_file("index.html", root=web_dir)

    @app.get("/<asset:path>")
    def web_asset(asset):
        return static_file(asset, root=web_dir)

    return app
