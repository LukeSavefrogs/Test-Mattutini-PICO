import traceback
from portalePICO.main import PortalePicoGTS
from os.path import expanduser, join, exists
from datetime import datetime
import time

import json
import yaml


class Trenitalia(object):
	@staticmethod
	def getInfrastructure():
		nodi = {}
		
		# --------------------------------------------------------------------------
		#							Scrape data
		# --------------------------------------------------------------------------
		print ("<PortalePicoGTS-PyScraper>")
		try:
			gts = PortalePicoGTS()
			gts.login("ictsmoperator", "Pico.GTS")

			nodi = gts.getNodes()
			gts.close()
		except Exception as e:
			print("ERRORE - " + str(e))
			print("Stacktrace:")
			traceback.print_stack()

		finally:
			print()
			print("</PortalePicoGTS-PyScraper>")

		return nodi
