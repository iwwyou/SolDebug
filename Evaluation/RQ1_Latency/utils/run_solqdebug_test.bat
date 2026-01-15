@echo off
cd /d "C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\Evaluation\RQ1_Latency"

set PYTHON=C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\.venv\Scripts\python.exe

echo ============================================================
echo SolQDebug Benchmark - TEST (interval=0, run=1)
echo ============================================================
echo.

%PYTHON% solqdebug_benchmark.py --interval 0 --run-id 1

echo.
echo ============================================================
echo Test completed!
echo ============================================================
pause
