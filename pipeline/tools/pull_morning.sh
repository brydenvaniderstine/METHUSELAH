#!/bin/bash
# METHUSELAH — Morning pull wrapper
# Triggered via iOS Shortcut over SSH using osascript
# Uses absolute paths throughout — relative paths and ~ fail via osascript

REPO="/Users/brydenvaniderstine/Desktop/METHUSELAH"
LOG="$REPO/pipeline/data/logs/morning_pull.log"
ERR="$REPO/pipeline/data/logs/morning_pull_error.log"

cd "$REPO"
/usr/bin/python3 "$REPO/pipeline/tools/oura_gen3_morning_pull.py" >> "$LOG" 2>> "$ERR"
