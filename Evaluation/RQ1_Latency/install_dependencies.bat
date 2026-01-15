@echo off
echo ================================================
echo SolQDebug Benchmark - Installing Dependencies
echo ================================================
echo.

pip install antlr4-python3-runtime
pip install py-solc-x
pip install networkx

echo.
echo ================================================
echo Installation complete!
echo ================================================
echo.
echo You can now run the benchmark:
echo   python solqdebug_benchmark.py
echo.
pause
