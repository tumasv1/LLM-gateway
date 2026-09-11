#!/bin/sh
# Тот же gunicorn, что в апстриме, но приложение — с RU-recognizers.
exec gunicorn -w "$WORKERS" -b "0.0.0.0:$PORT" "ru_pdn.bootstrap_app:create_app()"
