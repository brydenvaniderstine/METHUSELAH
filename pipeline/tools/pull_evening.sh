#!/bin/bash
# METHUSELAH — Evening pull wrapper
# Triggered via iOS Shortcut over SSH
# Uses osascript to open Terminal with GUI context so CoreBluetooth has permission
# Direct python3 via SSH fails silently — osascript is the confirmed working method

osascript -e 'tell app "Terminal" to do script "cd ~/Desktop/METHUSELAH && python3 pipeline/tools/oura_gen3_morning_pull.py"'
