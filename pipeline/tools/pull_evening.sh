#!/bin/bash
# METHUSELAH — Evening pull wrapper
# Called by iOS Shortcut via SSH
# Works at any hour — no fixed time assumption

cd /Users/brydenvaniderstine/Desktop/METHUSELAH
/usr/bin/python3 pipeline/tools/oura_gen3_morning_pull.py >> pipeline/data/logs/evening_pull.log 2>> pipeline/data/logs/evening_pull_error.log
