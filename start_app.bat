@echo off
cd /d "%~dp0"
echo Starting Flask app...
echo Open http://127.0.0.1:5000/ in your browser.
echo Do not open files from the templates folder directly.
python app.py
