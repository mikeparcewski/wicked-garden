# Selenium WebDriver

Selenium WebDriver — the original browser automation standard. Multi-language support (Python, JavaScript, Java, C#, Ruby). Best for legacy projects or when language choice matters.

## Installation

### Python

```bash
# Install selenium
pip install selenium

# Or with uv
uv add selenium

# Install browser drivers
pip install webdriver-manager   # auto-manages ChromeDriver

# With playwright's browser (alternative driver source)
pip install selenium webdriver-manager
```

### Node.js

```bash
npm i selenium-webdriver

# Install ChromeDriver (or use webdriver-manager)
npm i chromedriver
# Or: npm i -D @wdio/cli  (WebdriverIO, higher-level wrapper)
```

### Browser Driver Setup

Selenium requires a browser driver binary. Modern approach uses WebDriverManager to auto-download:

```python
# Python — auto-managed ChromeDriver
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
```

```javascript
// Node.js — auto-managed ChromeDriver
const { Builder } = require('selenium-webdriver');
const chrome = require('selenium-webdriver/chrome');
const chromedriver = require('chromedriver');

const driver = await new Builder()
  .forBrowser('chrome')
  .setChromeOptions(new chrome.Options().addArguments('--headless=new'))
  .build();
```

## Common Patterns (Python)

### Page Navigation and Screenshots

```python
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

options = Options()
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--window-size=1280,720')

driver = webdriver.Chrome(
    service=Service(ChromeDriverManager().install()),
    options=options
)

try:
    # Navigate
    driver.get('https://example.com')

    # Get page title
    print(driver.title)

    # Take screenshot
    driver.save_screenshot('screenshot.png')

    # Get page source
    html = driver.page_source

finally:
    driver.quit()
```

### Form Filling

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys

driver.get('https://example.com/login')

# Find elements and interact
email_field = driver.find_element(By.ID, 'email')
email_field.clear()
email_field.send_keys('user@example.com')

password_field = driver.find_element(By.ID, 'password')
password_field.send_keys('secret123')
password_field.send_keys(Keys.RETURN)   # press Enter

# Or find and click submit button
submit = driver.find_element(By.CSS_SELECTOR, 'button[type=submit]')
submit.click()
```

### Waiting Strategies

```python
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

# Explicit wait (recommended)
wait = WebDriverWait(driver, timeout=10)

# Wait for element to be clickable
button = wait.until(EC.element_to_be_clickable((By.ID, 'submit')))
button.click()

# Wait for element to be visible
element = wait.until(EC.visibility_of_element_located((By.CLASS_NAME, 'loaded')))

# Wait for URL to change
wait.until(EC.url_contains('/dashboard'))

# Wait for text to appear in element
wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, 'h1'), 'Welcome'))
```

### Content Extraction

```python
from selenium.webdriver.common.by import By

driver.get('https://example.com')

# Single element text
heading = driver.find_element(By.TAG_NAME, 'h1').text

# Multiple elements
items = driver.find_elements(By.CSS_SELECTOR, '.item')
for item in items:
    title = item.find_element(By.TAG_NAME, 'h2').text
    print(title)

# Execute JavaScript for complex extraction
data = driver.execute_script("""
  return Array.from(document.querySelectorAll('.product')).map(el => ({
    name: el.querySelector('h2')?.textContent,
    price: el.querySelector('.price')?.textContent,
  }));
""")
```

## Common Patterns (Node.js)

```javascript
const { Builder, By, until } = require('selenium-webdriver');
const chrome = require('selenium-webdriver/chrome');

(async function run() {
  const driver = await new Builder()
    .forBrowser('chrome')
    .setChromeOptions(new chrome.Options().addArguments('--headless=new'))
    .build();

  try {
    await driver.get('https://example.com');

    // Wait for element
    const el = await driver.wait(
      until.elementLocated(By.css('.content')),
      10000
    );

    // Get text
    const text = await el.getText();
    console.log(text);

    // Take screenshot (returns base64 PNG)
    const screenshot = await driver.takeScreenshot();
    require('fs').writeFileSync('shot.png', screenshot, 'base64');

  } finally {
    await driver.quit();
  }
})();
```

## Locator Strategies

```python
from selenium.webdriver.common.by import By

# By ID (fastest, most reliable)
driver.find_element(By.ID, 'email')

# By CSS Selector (flexible)
driver.find_element(By.CSS_SELECTOR, 'button.submit')
driver.find_element(By.CSS_SELECTOR, '[data-testid="submit"]')

# By XPath (powerful but brittle)
driver.find_element(By.XPATH, '//button[text()="Login"]')

# By Name
driver.find_element(By.NAME, 'username')

# By Class Name
driver.find_element(By.CLASS_NAME, 'submit-btn')

# By Link Text
driver.find_element(By.LINK_TEXT, 'Click here')
```

## CI Usage

```bash
# Python CI (headless Chrome)
pip install selenium webdriver-manager
python -m pytest tests/selenium/

# Docker-friendly flags
options.add_argument('--headless=new')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--disable-gpu')
```

## When to Use Selenium

- Legacy projects already using Selenium
- Need Python-native browser automation
- Require multi-language test suite (mix of Python + Java + etc.)
- Grid/parallel execution across different machines (Selenium Grid)
- Migrating from Selenium to Playwright — use as reference

**Prefer Playwright** for new projects: better auto-waiting, simpler API, built-in test runner.
