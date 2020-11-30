#!/bin/sh

# Hot/live reload - only works in debug mode

docker exec cheatdb_app_1 sh -c "cp -r /source/* ."
