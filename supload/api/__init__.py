"""Lớp HTTP: mỗi file là một nhóm tài nguyên (Flask blueprint)."""
from __future__ import annotations

from flask import Flask, current_app, jsonify


def services():
    """Các dịch vụ của ứng dụng (store, publisher, scheduler…), xem supload.app.Services."""
    return current_app.extensions["supload"]


def error(message: str, status: int = 400, **extra):
    return jsonify(error=message, **extra), status


def register(app: Flask) -> None:
    from . import ai, comments, flows, imports, insights, library, pages, posts, settings, state, system

    for bp in (state.bp, posts.bp, flows.bp, settings.bp, pages.bp, imports.bp, library.bp, insights.bp, ai.bp, system.bp, comments.bp):
        app.register_blueprint(bp)
