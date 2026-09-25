@echo off
cd /d "%~dp0"
start "ADMIN BOT" cmd /k python admin_bot.py
start "BOSS BOT" cmd /k python boss.py
