#!/bin/bash

while true; do
    inotifywait -r -e modify data
    git add data
    git commit -m "Data folder updated."
    git push
done
