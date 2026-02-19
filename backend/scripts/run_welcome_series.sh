#!/bin/bash
# Welcome Series Cron Job
# Runs every hour to send onboarding emails to new users

cd /home/ubuntu/nabavkidata/backend
# venv removed - using system python

python3 crons/welcome_series.py 2>&1
