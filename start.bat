@echo off
cd /d %~dp0
set PYTHONUTF8=1
call .venv\Scripts\activate
start "" http://localhost:5000
python app.py
