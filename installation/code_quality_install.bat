@echo off
REM This file installs the code-quality suite in your project folder

if not exist ".code-quality\installation" mkdir ".code-quality\installation"

REM suddenly stopped working:
curl -sL -o ".code_quality\installation\code_quality_install.py" https://raw.githubusercontent.com/iddolev/code-quality/main/installation/cq_install.py
REM so doing this instead:
set "_skip_curl="
REM for %%a in (%*) do if "%%a"=="--run" set "_skip_curl=1"
if not defined _skip_curl (
    copy C:\Code\code-quality\installation\code_quality_install.py .code-quality\installation\code_quality_install.py
)
for %%a in (%*) do if "%%a"=="--fetch" (
    echo Fetched cq_install.py
    exit /b 0
)

setlocal enabledelayedexpansion
set "_args="
for %%a in (%*) do if "%%a" NEQ "--run" set "_args=!_args! %%a"

pip install pyyaml
python ".code-quality\installation\code_quality_install.py" !_args!
endlocal
