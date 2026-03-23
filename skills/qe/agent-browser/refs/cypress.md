# Cypress

Cypress — a test-focused browser automation tool with excellent developer experience, real-time reloading, and built-in time-travel debugging. Best for end-to-end and component testing workflows.

## Installation

```bash
# Node.js
npm i -D cypress

# Verify installation
npx cypress --version

# Or with yarn/pnpm
yarn add -D cypress
pnpm add -D cypress
```

**Requirements**: Node.js 16+, supported OS (macOS, Linux, Windows).

## Key CLI Commands

```bash
# Open interactive test runner (GUI)
npx cypress open

# Run tests headlessly (CI mode)
npx cypress run

# Run a specific test file
npx cypress run --spec "cypress/e2e/login.cy.js"

# Run tests matching a pattern
npx cypress run --spec "cypress/e2e/**/*.cy.js"

# Run in a specific browser
npx cypress run --browser chrome
npx cypress run --browser firefox
npx cypress run --browser electron   # default

# Run specific test by title grep
npx cypress run --grep "login"

# Generate report
npx cypress run --reporter json --reporter-options "output=results.json"
```

## Project Structure

```
cypress/
├── e2e/               # End-to-end test specs
│   └── login.cy.js
├── component/         # Component test specs
│   └── Button.cy.jsx
├── fixtures/          # Static test data (JSON)
│   └── user.json
├── support/
│   ├── commands.js    # Custom commands
│   └── e2e.js         # Global setup/teardown
└── cypress.config.js  # Configuration
```

## Common Patterns

### Page Navigation

```javascript
// cypress/e2e/navigation.cy.js
describe('Navigation', () => {
  it('visits and checks the page', () => {
    cy.visit('https://example.com');

    // Assert URL
    cy.url().should('include', 'example.com');

    // Assert title
    cy.title().should('eq', 'Example Domain');

    // Navigate to another page
    cy.get('a').first().click();
    cy.url().should('not.include', 'example.com');

    // Go back
    cy.go('back');
  });
});
```

### Screenshots

```javascript
it('captures screenshots', () => {
  cy.visit('https://example.com');

  // Manual screenshot
  cy.screenshot('page-name');

  // Screenshot of specific element
  cy.get('h1').screenshot('heading');

  // Screenshots on failure are automatic when configured:
  // screenshotOnRunFailure: true (default in cypress.config.js)
});
```

### Form Filling

```javascript
it('fills and submits a form', () => {
  cy.visit('/login');

  // Type into fields
  cy.get('#email').type('user@example.com');
  cy.get('#password').type('secret123');

  // Or use data attributes (recommended)
  cy.get('[data-cy=email]').type('user@example.com');
  cy.get('[data-cy=password]').type('secret123');

  // Submit
  cy.get('button[type=submit]').click();

  // Assert success
  cy.url().should('include', '/dashboard');
  cy.get('.welcome').should('contain', 'Welcome');
});
```

### Waiting (Built-in)

```javascript
// Cypress automatically retries assertions until they pass (default 4s timeout)
it('waits for async content', () => {
  cy.visit('/dashboard');

  // This automatically waits for .data-table to exist and have content
  cy.get('.data-table').should('have.length.gt', 0);

  // Wait for API response
  cy.intercept('GET', '/api/users').as('getUsers');
  cy.visit('/users');
  cy.wait('@getUsers');
  cy.get('.user-list').should('be.visible');
});
```

### API Interception

```javascript
it('stubs API responses', () => {
  // Intercept and stub
  cy.intercept('GET', '/api/products', {
    statusCode: 200,
    body: [{ id: 1, name: 'Widget' }],
  }).as('getProducts');

  cy.visit('/products');
  cy.wait('@getProducts');
  cy.get('.product-card').should('have.length', 1);
});
```

### Custom Commands

```javascript
// cypress/support/commands.js
Cypress.Commands.add('login', (email, password) => {
  cy.visit('/login');
  cy.get('#email').type(email);
  cy.get('#password').type(password);
  cy.get('button[type=submit]').click();
  cy.url().should('include', '/dashboard');
});

// Usage in test
it('uses custom command', () => {
  cy.login('user@example.com', 'secret');
  cy.get('.welcome').should('be.visible');
});
```

## Configuration

```javascript
// cypress.config.js
const { defineConfig } = require('cypress');

module.exports = defineConfig({
  e2e: {
    baseUrl: 'https://example.com',
    viewportWidth: 1280,
    viewportHeight: 720,
    defaultCommandTimeout: 8000,
    requestTimeout: 10000,
    video: true,
    screenshotOnRunFailure: true,
    retries: { runMode: 2, openMode: 0 },
    setupNodeEvents(on, config) {
      // node event listeners
    },
  },
});
```

## CI Usage

```bash
# Run in CI (headless, exit code reflects test results)
npx cypress run --headless

# With parallel flag (requires Cypress Cloud)
npx cypress run --parallel --record --key $CYPRESS_RECORD_KEY

# JUnit reporter for CI systems
npx cypress run --reporter junit --reporter-options "mochaFile=results/[hash].xml"
```
