@echo off
cd /d "%~dp0"
start "SOFI ADMIN BOT" cmd /k python admin_bot.py
start "SOFI BOSS BOT" cmd /k python boss.py
