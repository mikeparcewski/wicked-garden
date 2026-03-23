# Puppeteer

Google Puppeteer — mature headless Chrome automation library. Strong ecosystem, widely adopted for scraping, PDF generation, and screenshot workflows.

## Installation

```bash
# Node.js (installs bundled Chrome)
npm i puppeteer

# Lightweight version (no bundled Chrome, uses system Chrome)
npm i puppeteer-core

# Verify installation
node -e "require('puppeteer'); console.log('ok')"
```

**Note**: Puppeteer v21+ ships with Chrome for Testing (bundled). For `puppeteer-core`, point `executablePath` to your system Chrome.

## Key APIs

### Browser and Page Lifecycle

```javascript
const puppeteer = require('puppeteer');

async function run() {
  // Launch browser
  const browser = await puppeteer.launch({
    headless: 'new',      // new headless mode (recommended)
    slowMo: 50,           // slow down by 50ms (useful for debugging)
    args: ['--no-sandbox'],
  });

  // Open a new page (tab)
  const page = await browser.newPage();

  // Set viewport
  await page.setViewport({ width: 1280, height: 720 });

  // Navigate
  await page.goto('https://example.com', {
    waitUntil: 'networkidle2',  // wait until < 2 network connections for 500ms
  });

  // ... do work ...

  // Close browser
  await browser.close();
}

run();
```

## Common Patterns

### Screenshots

```javascript
const puppeteer = require('puppeteer');

(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();

  await page.goto('https://example.com');

  // Viewport screenshot
  await page.screenshot({ path: 'screenshot.png' });

  // Full page screenshot
  await page.screenshot({ path: 'fullpage.png', fullPage: true });

  // Clip region
  await page.screenshot({
    path: 'clip.png',
    clip: { x: 0, y: 0, width: 400, height: 300 },
  });

  // Screenshot of a specific element
  const element = await page.$('h1');
  await element.screenshot({ path: 'element.png' });

  await browser.close();
})();
```

### PDF Generation

```javascript
(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();

  await page.goto('https://example.com', { waitUntil: 'networkidle2' });

  await page.pdf({
    path: 'output.pdf',
    format: 'A4',
    printBackground: true,
    margin: { top: '1cm', bottom: '1cm', left: '1cm', right: '1cm' },
  });

  await browser.close();
})();
```

### Form Interaction

```javascript
(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();

  await page.goto('https://example.com/login');

  // Type into inputs
  await page.type('#email', 'user@example.com', { delay: 50 });
  await page.type('#password', 'secret', { delay: 50 });

  // Click submit
  await page.click('button[type=submit]');

  // Wait for navigation
  await page.waitForNavigation({ waitUntil: 'networkidle2' });

  console.log('Logged in, URL:', page.url());

  await browser.close();
})();
```

### Content Extraction / Scraping

```javascript
(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();

  await page.goto('https://example.com');

  // Evaluate JavaScript in page context — extract data
  const data = await page.evaluate(() => {
    const items = [];
    document.querySelectorAll('.item').forEach(el => {
      items.push({
        title: el.querySelector('h2')?.textContent?.trim(),
        link: el.querySelector('a')?.href,
        description: el.querySelector('p')?.textContent?.trim(),
      });
    });
    return items;
  });

  console.log(JSON.stringify(data, null, 2));

  await browser.close();
})();
```

### Waiting Strategies

```javascript
(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();

  await page.goto('https://example.com');

  // Wait for selector to appear
  await page.waitForSelector('.loaded');

  // Wait for selector to disappear
  await page.waitForSelector('.loading', { hidden: true });

  // Wait for navigation
  await Promise.all([
    page.waitForNavigation(),
    page.click('a'),
  ]);

  // Wait for a function to return truthy
  await page.waitForFunction(() => document.readyState === 'complete');

  // Wait for specific request
  const [response] = await Promise.all([
    page.waitForResponse(r => r.url().includes('/api/data') && r.status() === 200),
    page.click('#load'),
  ]);
  const json = await response.json();

  await browser.close();
})();
```

### Network Interception

```javascript
(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();

  // Enable request interception
  await page.setRequestInterception(true);

  page.on('request', request => {
    if (request.resourceType() === 'image') {
      // Block image loading for faster scraping
      request.abort();
    } else {
      request.continue();
    }
  });

  page.on('response', response => {
    if (response.url().includes('/api/')) {
      console.log('API response:', response.status(), response.url());
    }
  });

  await page.goto('https://example.com');

  await browser.close();
})();
```

### Multiple Tabs / Pages

```javascript
(async () => {
  const browser = await puppeteer.launch({ headless: 'new' });

  // Open multiple pages in parallel
  const [page1, page2] = await Promise.all([
    browser.newPage(),
    browser.newPage(),
  ]);

  await Promise.all([
    page1.goto('https://example.com'),
    page2.goto('https://example.org'),
  ]);

  const [title1, title2] = await Promise.all([
    page1.title(),
    page2.title(),
  ]);

  console.log(title1, title2);

  await browser.close();
})();
```

## Configuration Options

```javascript
const browser = await puppeteer.launch({
  headless: 'new',          // 'new' (default), false (headed), true (legacy)
  slowMo: 0,                // ms delay between actions (debugging)
  devtools: false,          // open DevTools automatically
  args: [
    '--no-sandbox',         // required in Docker/CI
    '--disable-setuid-sandbox',
    '--disable-dev-shm-usage',   // avoid /dev/shm issues in Docker
    '--window-size=1920,1080',
  ],
  defaultViewport: { width: 1280, height: 720 },
  timeout: 30000,           // navigation timeout ms
  executablePath: '/usr/bin/google-chrome',  // puppeteer-core only
});
```

## Debugging

```bash
# Run headed to see the browser
PUPPETEER_HEADLESS=false node script.js

# Slow down for observation
# (set slowMo in launch options)

# Connect Chrome DevTools to running browser
# Set devtools: true in launch options
```

## AI Agent Usage Tips

- Use `page.evaluate()` to extract structured data as JSON — avoids HTML parsing
- Set `waitUntil: 'networkidle2'` on SPAs to ensure content is rendered
- Block images and fonts via request interception for faster scraping
- `page.content()` returns the full rendered HTML after JavaScript execution
