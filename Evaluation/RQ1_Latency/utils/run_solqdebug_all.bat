@echo off
setlocal enabledelayedexpansion

cd /d "C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\Evaluation\RQ1_Latency"

set PYTHON=C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\.venv\Scripts\python.exe

echo ============================================================
echo SolQDebug Benchmark - All Intervals and Runs
echo ============================================================
echo.

for %%i in (0 2 5 10) do (
    for %%r in (1 2 3 4 5 6 7 8 9 10) do (
        echo Running: interval=%%i, run=%%r
        %PYTHON% solqdebug_benchmark.py --interval %%i --run-id %%r
        if errorlevel 1 (
            echo ERROR: Failed at interval=%%i, run=%%r
            pause
            exit /b 1
        )
    )
)

echo.
echo ============================================================
echo All benchmarks completed!
echo ============================================================
pause
