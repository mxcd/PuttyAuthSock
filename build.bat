python3 -m venv venv
venv/Scripts/activate.bat
pip install -r requirements.txt
pyinstaller --onefile --icon=icon.ico --add-data "icon.png;files" --add-data "icon_green.png;files" --noconsole -n PuttyAuthSock main.py