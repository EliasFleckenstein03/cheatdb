#!/bin/sh

# Open SQL console for the database

docker exec -it cheatdb_db_1 sh -c "psql contentdb contentdb"
