import sys, os
import re, inspect
import ctypes

def executable_run_directly():
	"""Checks wether an executable file was launched by double-clicking on the icon

	Raises:
		Exception: Only if there was an exep

	Returns:
		[type]: [description]
	"""
	try:
		# Load kernel32.dll
		kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
		# Create an array to store the processes in.  This doesn't actually need to
		# be large enough to store the whole process list since GetConsoleProcessList()
		# just returns the number of processes if the array is too small.
		process_array = (ctypes.c_uint * 1)()
		num_processes = kernel32.GetConsoleProcessList(process_array, 1)
		# num_processes may be 1 if your compiled program doesn't have a launcher/wrapper.

		return num_processes <= 2
	except Exception as e:
		raise Exception("Method not supported by your OS")




def getCorrectPath(filePath):
	"""Returns the correct path (relative/absolute) wether is a frozen app or a script 

	Args:
		filePath (str): The path to the resource you need

	Returns:
		str: Final resolved path
	"""
	# Se il percorso specificato è assoluto non fare nulla
	if os.path.isabs(filePath):
		return filePath


	# Se è un'applicazione PyInstaller e il percorso è relativo
	if hasattr(sys, "_MEIPASS"):
		file = os.path.join(sys._MEIPASS, filePath)
	
	# Se è uno script e il percorso è relativo
	else:
		# Scopro il percorso del file chiamante
		frame = inspect.stack()[1]
		caller_filename = frame[0].f_code.co_filename

		# Prendo la cartella parent del file chiamante
		caller_working_directory = os.path.dirname(os.path.realpath(caller_filename))

		# Risolvo i percorsi relativi alla cartella in cui è presente lo script chiamante
		file = os.path.abspath(os.path.join(caller_working_directory, filePath))


		# print(f"Caller: {caller_filename}")
		# print(f"Caller WD: {caller_working_directory}")
		# print(f"Final path: {file}\n")

	return file







def compareVersions(vA, vB):
	"""
		@deprecated: USE https://stackoverflow.com/a/28485211/8965861
		
		Compares two version number strings
		@param vA: first version string to compare
		@param vB: second version string to compare
		@author <a href="http_stream://sebthom.de/136-comparing-version-numbers-in-jython-pytho/">Sebastian Thomschke</a>
		@return negative if vA < vB, zero if vA == vB, positive if vA > vB.
	"""
	def cmp(a, b):
		return (a > b) - (a < b) 

	def num(s):
		if s.isdigit(): return int(s)
		return s

	if vA == vB: return 0


	seqA = list(map(num, re.findall('\d+|\w+', vA.replace('-SNAPSHOT', ''))))
	seqB = list(map(num, re.findall('\d+|\w+', vB.replace('-SNAPSHOT', ''))))

	# this is to ensure that 1.0 == 1.0.0 in cmp(..)
	lenA, lenB = len(seqA), len(seqB)
	for i in range(lenA, lenB): seqA += (0,)
	for i in range(lenB, lenA): seqB += (0,)

	rc = cmp(seqA, seqB)

	if rc == 0:
		if vA.endswith('-SNAPSHOT'): return -1
		if vB.endswith('-SNAPSHOT'): return 1
	return rc