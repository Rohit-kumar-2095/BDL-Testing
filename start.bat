@echo off
setlocal

echo ============================================
echo  TenderCheck -- BDL Compliance Analyzer
echo ============================================
echo.
echo  Open this URL in your browser after the server starts:
echo.
echo    http://127.0.0.1:8000/app/index.html
echo.
echo  Default accounts:
echo    bdl.admin    / BDL@2024
echo    procurement1 / Tender@123
echo    procurement2 / Tender@123
echo.
echo  API docs: http://127.0.0.1:8000/docs
echo.
echo Press Ctrl+C to stop the server.
echo ============================================
echo.

C:\Python314\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
pause
