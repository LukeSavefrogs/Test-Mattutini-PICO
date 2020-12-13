<p align="center">
	<h1 align="center">Test Mattutini - PICO ICTSM</h1>
	<p align="center">
		<strong><i>- "Not your regular monkey" -</i></strong>
		<br>
		<br>
		<img alt="GitHub release (latest by date)" src="https://img.shields.io/github/v/release/LukeSavefrogs/Test-Mattutini-PICO">
		<img alt="GitHub last commit" src="https://img.shields.io/github/last-commit/LukeSavefrogs/Test-Mattutini-PICO">
		<a href="https://github.com/LukeSavefrogs/Test-Mattutini-PICO/issues"><img alt="GitHub issues" src="https://img.shields.io/github/issues/LukeSavefrogs/Test-Mattutini-PICO?color=important"></a>
	</p>
</p>


## Table of Contents
- [Table of Contents](#table-of-contents)
- [Introduzione](#introduzione)
	- [A cosa serve?](#a-cosa-serve)
	- [Come si usa?](#come-si-usa)
- [Configurazione](#configurazione)
	- [Esempio file di configurazione](#esempio-file-di-configurazione)
- [Consigli e altre informazioni](#consigli-e-altre-informazioni)
- [Importante](#importante)
- [Sviluppo](#sviluppo)
	- [Per utilizzare i file sorgenti](#per-utilizzare-i-file-sorgenti)
	- [Per compilare il progetto](#per-compilare-il-progetto)

## Introduzione
### A cosa serve?
Questo script si occupa di effettuare il **test di acquisto** sui nodi infrastrutturali **No-Production** del progetto **PICO**.

### Come si usa?
1. **Scarica** l'eseguibile da [questo link](https://github.com/LukeSavefrogs/PICO-Tests/raw/master/dist/Test_acquisto-PICO.exe) e salvalo in una cartella di tua scelta.

2. Ora puoi lanciarlo semplicemente facendo **doppio click**. 
   
   In automatico partiranno i Test mattutini nell'ordine di comparsa all'interno della mail (Certificazione, Formazione, Integrazione, Training)!



## Configurazione
<table>
	<thead>
		<tr>
			<th>
				Parametro
			</th>
			<th>
				Descrizione
			</th>
		</th>
	</thead>
	<tbody>
		<tr>
			<td>
				<code>-h</code>
			</td>
			<td>
				Mostra una <strong>guida</strong> su come utilizzare lo script
			</td>
		</tr>
		<tr>
			<td>
				<code>-P</code>
			</td>
			<td>
				Specifica la stazione di <strong>partenza</strong>
			</td>
		</tr>
		<tr>
			<td>
				<code>-A</code>
			</td>
			<td>
				Specifica la stazione di <strong>arrivo</strong>
			</td>
		</tr>
		<tr>
			<td>
				<code>-G</code>
			</td>
			<td>
				Specifica la <strong>data</strong> di <strong>partenza</strong>
			</td>
		</tr>
		<tr>
			<td>
				<code>-O</code>
			</td>
			<td>
				Specifica l'<strong>ora</strong> di <strong>partenza</strong>
			</td>
		</tr>
		<tr>
			<td>
				<code>-f</code>
			</td>
			<td>
				<strong>Forza</strong> l'aggiornamento della <strong>configurazione</strong> dal PortalePicoGTS
			</td>
		</tr>
		<tr>
			<td colspan="2">
				<i>Altre informazioni e opzioni avanzate nel display di aiuto attivabile con <code>-h</code>...</i>
			</td>
		</tr>
	</tbody>
</table>

### Esempio file di configurazione
```yaml
---
# Configurazione carta (per pagamento sulla pagina di N&TS)
card:
  firstName:  Bruce
  lastName:   Lee
  number:     4539999999999993
  exp_date:   12/2022
  csc:        111


# Configurazione dati passeggero da inserire in fase di prenotazione
passenger:
  firstName:  Bruce
  lastName:   Qui
  email:      test.email@test.com
  tel_number: 0123456789
  birth_date: 11/09/2001


# E' possibile personalizzare la tratta del viaggio come di seguito
travel:
  departure:  Mantova
  arrival:    Torino
```

## Consigli e altre informazioni
- Per **evitare** uscite inaspettate dal programma a causa di **errori non gestiti** (si tratta ancora di una versione di sviluppo) consiglio di lanciare il programma da una **finestra Powershell**.
  - Su Windows 10 è possibile aprire una finestra Powershell all'interno della cartella del programma cliccando in un punto bianco della cartella e poi facendo <kbd><kbd>Shift</kbd> + <kbd>Click Destro</kbd></kbd>. Altrimenti basta spostarcisi utilizzando il comando `cd`.
  - Dopo aver aperto la finestra Powershell nella cartella corretta basterà digitare il nome dell'eseguibile e dare <kbd>Invio</kbd>.

- Al momento lo script supporta **unicamente** Google Chrome. Se non è installato andrà in errore.

- Al momento la guida qui su GitHub **non è completa**, a differenza del display di aiuto incluso nel programma (e visualizzabile in ogni momento lanciando `Test_acquisto-PICO.exe -h` oppure `Test_acquisto-PICO.exe --help`) :smile:. 


## Importante
Al **primo avvio** del programma, esso cercherà di contattare il **Portale Pico GTS** per scaricare le **definizioni aggiornate** dei nodi su cui effettuare i test mattutini. Se esso risulterà **irraggiungibile** la procedura verrà **interrotta** forzatamente.

Queste definizioni (salvate in un file nella *cartella home* dell'utente) verranno **aggiornate ogni settimana**. Se invece durante questi successivi aggiornamenti il Portale dovesse risultare inaccessibile, il programma **non si bloccherà**, ma utilizzerà la **configurazione obsoleta**, rimandando l'aggiornamento all'**avvio successivo**.

## Sviluppo
### Per utilizzare i file sorgenti
  1. **Clonare** o **scaricare** il repository
   ```PowerShell
   git clone https://github.com/LukeSavefrogs/Test-Mattutini-PICO.git
   ```
  2. **Installare** `python` e `pipenv`  (se già non li si possiede)
  3. **Aggiornare le dipendenze** con il comando `pipenv install` 

### Per compilare il progetto
```PowerShell
pyinstaller --clean --name "Test_acquisto-PICO" --log-level=WARN --onefile --noconfirm --add-data="./conf/;./conf/" .\pico_tests.py
```
