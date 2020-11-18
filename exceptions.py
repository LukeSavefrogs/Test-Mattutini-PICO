class BrowserNotInstalledException(Exception):
    """Exception raised for errors in the browser load.

    Attributes:
        browser -- browser that is not installed
        message -- explanation of the error
    """

    def __init__(self, browser, message="Browser not installed"):
        self.browser = browser
        self.message = message
        super().__init__(self.message)

    def __str__(self):
        return f'Error while opening {self.browser} -> {self.message}'