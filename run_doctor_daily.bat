@echo off
REM Doctor Daemon — nightly self-learning report (schedule me in Windows Task
REM Scheduler: Action = start this file; Trigger = daily 02:00).
cd /d "D:\3D React Viewer\server"
call venv\Scripts\activate.bat
python doctor_daemon.py >> ..\docs\doctor_daemon.log 2>&1
