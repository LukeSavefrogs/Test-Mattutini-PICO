from os import environ
import traceback
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager

import time

import requests
from urllib3.exceptions import InsecureRequestWarning

BASE_URL = "http://ngppgtsfe.pico.gts"

class PortalePicoGTS(object):
	def __init__(self):
		"""
		Starts the browser
		"""
		chrome_flags = [
			# "--disable-extensions",
			"start-maximized",
			"--disable-gpu",
			"--ignore-certificate-errors",
			"--ignore-ssl-errors",
			#"--no-sandbox # linux only,
			"--log-level=3",	# Start from CRITICAL
			"--headless",
		]
		chrome_options = Options()

		for flag in chrome_flags: chrome_options.add_argument(flag)

		# To remove '[WDM]' logs (https://github.com/SergeyPirogov/webdriver_manager#configuration)
		environ['WDM_LOG_LEVEL'] = '0'
		environ['WDM_PRINT_FIRST_LINE'] = 'False'
		
		# To remove "DevTools listening on ws:..." message (https://stackoverflow.com/a/56118790/8965861)
		chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])

		self.driver = webdriver.Chrome( ChromeDriverManager().install(), options=chrome_options )


	def waitUntilReady(self):
		time.sleep(0.5)
		WebDriverWait(self.driver, 30).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "div.pace-progress")))
		time.sleep(0.5)
		# print("Ready")


	def login(self, USERNAME, PASSWORD):
		"""
		docstring
		"""
		print("Logging in: \t", end="", flush=True)

		self.driver.get(f"{BASE_URL}/user/login")
		self.waitUntilReady()
		self.driver.find_element_by_id("loginform-login").send_keys(USERNAME)
		self.driver.find_element_by_id("loginform-password").send_keys(PASSWORD + Keys.ENTER)
		self.waitUntilReady()
		print("OK")


	def logout(self):
		self.driver.execute_script("""
			let logout_form = document.querySelector("form[action='/user/logout'][method='POST']")
			if (logout_form) {
				logout_form.submit()
				return true;
			}
			else return false;
		""")


	def close(self):
		# print("Logging out: \t", end="", flush=True)
		try:
			print("Logging out: \t", flush=True)
			self.logout()
			print("Waiting: \t", flush=True)
			self.waitUntilReady()
			print("Quitting: \t", flush=True)
			self.driver.quit()
		except Exception as e:
			print("ERRORE - " + str(e))
			print("Stacktrace:")
			traceback.print_stack()
		else:
			print("OK")


	def getNodes(self):
		"""
			Retrieves all nodes from 'PortalePicoGTS > Was > Link ai nodi' (http://ngppgtsfe.pico.gts/was/ng-nodes)
		"""
		self.driver.get(f"{BASE_URL}/was/ng-nodes")
		self.waitUntilReady()
		
		print("Scraping data: \t", end="", flush=True)

		mapping_all_nodes = self.driver.execute_script(r'''
			function getMapping () {
				let MAPPING = {};

				let progetti = document.querySelectorAll(".tabbable.boxed.parentTabs > ul.nav.nav-tabs > li > a");
				
				progetti.forEach(el => {
					let name = el.innerText.trim();
					
					MAPPING[name] = {}
					el.click();
					
					console.group(name);
					let active_tab = document.querySelector(".tabbable.boxed.parentTabs > div.tab-content > div.tab-pane.active");
					let ambienti = active_tab.querySelectorAll("ul.nav.nav-tabs > li > a");

					ambienti.forEach(amb => {
						let ambName = amb.innerText.trim();
						console.group(ambName);

						MAPPING[name][ambName] = {}
						amb.click();

						let active_amb = active_tab.querySelector("div.tab-content > .tab-pane.active");
						active_amb.querySelectorAll("div.dropdown").forEach(btn_container => {
							let dropdown = btn_container.querySelector("button");

							let dropdownName = dropdown.innerText.trim();
							let dropdownType = Array.from(dropdown.classList).find(className => !["btn", "btn-block", "dropdown-toggle"].includes(className));
							
							MAPPING[name][ambName][dropdownName] = {}
							MAPPING[name][ambName][dropdownName][dropdownType] = []
							console.group(`${dropdownType} - ${dropdownName}`);

							btn_container.querySelectorAll("ul.dropdown-menu > li").forEach(jvm => {
								let urls = Array.from(jvm.children).filter(child => child.tagName == "A");

								if (urls.length !== 0) {
									let macchina = jvm.title.trim() || "unknown";
									let jvm_name = Array.from(jvm.children).find(child => child.tagName == "B").innerText.trim() || "unknown";

									let http_url = urls.find(url => url.href.startsWith("http://")).href;
									let https_url = urls.find(url => url.href.startsWith("https://")).href;

									console.log("Macchina: %s\nJVM: %s\n\nHTTP: %s\nHTTPS: %s", macchina, jvm_name, http_url, https_url);
									MAPPING[name][ambName][dropdownName][dropdownType].push({
										"macchina": macchina,
										"jvm_name": jvm_name,
										"urls": {
											"http": http_url, 
											"https": https_url
										}
									});
								}
								else {
									console.warn("JVM with no details: ", jvm)
								}
							});
							console.groupEnd(`${dropdownType} - ${dropdownName}`);
						});
						
						console.groupEnd(ambName);
					});

					console.groupEnd(name);
				});
				
				return MAPPING;
			} 
			
			return getMapping();
		''')
		print("OK")

		
		return mapping_all_nodes


	@staticmethod
	def isReachable():
		return uri_exists_stream(BASE_URL)


	@staticmethod
	def getUrl():
		return BASE_URL




def uri_exists_stream(uri: str) -> bool:
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
    requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

    try:
        with requests.head(uri, stream=True, allow_redirects=True, headers=headers, verify=False) as response:
            try:
                response.raise_for_status()
                return True
            except requests.exceptions.HTTPError:
                return False
    except requests.exceptions.ConnectionError:
        return False
