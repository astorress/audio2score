#!/bin/bash
# Git runs on the host (pushes use the host's credentials); inside the
# container it only needs to trust the mounted folder.
git config --global --add safe.directory /app
