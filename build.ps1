$remote_dir = "\\172.30.62.6\gts\sharedScripts\Test di Acquisto"

pyinstaller `
	--clean `
	--name "Test_acquisto-PICO" `
	--log-level=WARN `
	--onefile `
	--noconfirm `
	--specpath "specs" `
	--add-data="../src/conf/;./conf/" .\src\pico_tests.py;

pyinstaller `
	--clean `
	--name "Test_acquisto-C2C" `
	--log-level=WARN `
	--onefile `
	--noconfirm `
	--specpath "specs" `
	--add-data="../src/conf/;./conf/" .\src\C2C_tests.py;

if ($?) { 
	Copy-Item .\dist\Test_acquisto-* "$remote_dir";
}