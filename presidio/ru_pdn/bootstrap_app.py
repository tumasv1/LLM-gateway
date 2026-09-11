"""Gunicorn-цель: штатный Presidio Server + наши RU-recognizers после старта."""
from __future__ import annotations

import app as presidio_app
from ru_pdn.recognizers import register_ru_recognizers

_orig_init = presidio_app.Server.__init__


def _patched_init(self, *args, **kwargs):
    _orig_init(self, *args, **kwargs)
    register_ru_recognizers(self.engine)
    self.logger.info("ru_pdn: подключены ИНН/СНИЛС/паспорт/ФИО (en+ru)")


presidio_app.Server.__init__ = _patched_init


def create_app():
    return presidio_app.create_app()
