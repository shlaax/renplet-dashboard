@echo off
cd /d D:\Ai agent renplet
start cmd /k ".\python.exe -m uvicorn main:app --reload"
