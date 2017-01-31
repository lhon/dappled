@ECHO OFF

TITLE Dappled installer

IF NOT EXIST %LOCALAPPDATA%\dappled\Scripts\conda.exe (

    ECHO Downloading miniconda...
    powershell -Command "(New-Object Net.WebClient).DownloadFile('https://repo.continuum.io/miniconda/Miniconda2-latest-Windows-x86_64.exe', '%UserProfile%\miniconda.exe')"

    ECHO Installing miniconda...
    start /wait "" %UserProfile%\miniconda.exe /NoRegistry=1 /RegisterPython=0 /AddToPath=1 /S /D=%LOCALAPPDATA%\dappled

    ECHO Installing dappled...

) ELSE (
    ECHO Updating dappled...
)

%LOCALAPPDATA%\dappled\Scripts\conda install -y --no-update-deps dappled -c http://conda.dappled.io

ECHO(
ECHO Dappled has been installed. At a new prompt, type:
ECHO(
ECHO   dappled -h
ECHO(
ECHO to display the help text.
ECHO(

PAUSE