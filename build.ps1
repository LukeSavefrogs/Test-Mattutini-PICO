pyinstaller `
	--clean `
	--name "Test_acquisto-PICO" `
	--log-level=WARN `
	--onefile `
	--noconfirm `
	--add-data="./conf/;./conf/" .\pico_tests.py;

pyinstaller `
	--clean `
	--name "Test_acquisto-C2C" `
	--log-level=WARN `
	--onefile `
	--noconfirm `
	--add-data="./conf/;./conf/" .\pico_tests.py;

if ($?) { 
	Copy-Item .\dist\Test_acquisto-* "\\172.30.62.6\gts\sharedScripts\Test di Acquisto";
}