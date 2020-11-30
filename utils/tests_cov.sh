#!/bin/sh

docker exec cheatdb_app_1 sh -c "FLASK_CONFIG=../config.cfg FLASK_APP=app/__init__.py python -m pytest app/tests/ --cov=app --disable-warnings"
