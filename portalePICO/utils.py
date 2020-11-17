from portalePICO.main import PortalePicoGTS
from os.path import expanduser, join, exists
from datetime import datetime
import time

import json
import yaml


class Trenitalia(object):
	@staticmethod
	def getInfrastructure():
		print ("<PortalePicoGTS-PyScraper>")

		# --------------------------------------------------------------------------
		#							Scrape data
		# --------------------------------------------------------------------------
		gts = PortalePicoGTS()
		gts.login("ictsmoperator", "Pico.GTS")

		nodi = gts.getNodes()
		gts.close()

		print()
		print("</PortalePicoGTS-PyScraper>")

		return nodi
