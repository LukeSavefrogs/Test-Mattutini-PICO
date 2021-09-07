$spacer = "`n`n`n"

function Submit-Script () {
	param (
		[Parameter(Mandatory)] $OutputName, 
		[Parameter(Mandatory)] $InputPath, 
		[switch] $CopyToRemote = $false,
		[string] $RemoteDirectory = "\\172.30.62.27\SharedMonitor\Test di Acquisto"
	)

	Write-Host -ForegroundColor DarkCyan "Compilazione iniziata ($InputPath -> $OutputName)"
	pyinstaller `
		--clean `
		--name "$OutputName" `
		--log-level=WARN `
		--onefile `
		--noconfirm `
		--specpath "specs" `
		--add-data="../src/conf/;./conf/" "$InputPath";
		# --debug=imports `
		# --hidden-import=jinxed.terminfo.vtwin10 `
		# --hidden-import=jinxed.terminfo.ansicon `

	if ($?) { 
		Write-Host -ForegroundColor Green "${spacer}Compilazione terminata con successo${spacer}"
	} else {
		Write-Error "${spacer}Compilazione terminata in errore${spacer}"
	}

	if ($CopyToRemote) {
		Write-Host -ForegroundColor DarkCyan "Procedo alla copia..."

		Copy-Item -Force ".\dist\${OutputName}.exe" "$RemoteDirectory";
		if ($?) { 
			Write-Host -ForegroundColor Green "${spacer}Copia terminata con successo${spacer}"
		} else {
			Write-Error "${spacer}Copia terminata in errore${spacer}"
		}
	}
}


Submit-Script -OutputName "Test_acquisto-C2C" -InputPath .\src\C2C_tests.py -CopyToRemote
# Submit-Script -OutputName "Test_acquisto-PICO" -InputPath .\src\pico_tests.py -CopyToRemote