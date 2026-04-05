@echo off
REM This file installs the code-quality suite in your project folder

if not exist ".code-quality" mkdir ".code-quality"

curl -sL -o ".code_quality\code-quality.py" https://raw.githubusercontent.com/iddolev/code-quality/main/installation/cq_install.py

for %%a in (%*) do if "%%a"=="--fetch" (
    echo Fetched cq_install.py
    exit /b 0
)

pip install pyyaml
python ".code_quality\cq_install.py" %*
