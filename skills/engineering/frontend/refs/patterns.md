# Frontend Code Patterns

## Component Structure Pattern

```jsx
interface Props {
  title: string;
  items: Item[];
  onSelect: (item: Item) => void;
}

export const ItemList = ({ title, items, onSelect }: Props) => {
  return (
    <section aria-labelledby="list-title">
      <h2 id="list-title">{title}</h2>
      <ul role="list">
        {items.map(item => (
          <li key={item.id}>
            <button onClick={() => onSelect(item)}>
              {item.name}
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
};
```

## Custom Hook Pattern

```jsx
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debouncedValue;
}
```

## React Best Practices

### Hook Dependencies
- Always include all dependencies in useEffect/useMemo/useCallback
- Avoid stale closures

### Effect Cleanup
```jsx
useEffect(() => {
  const subscription = api.subscribe(data => {
    setData(data);
  });

  // Cleanup to prevent memory leaks
  return () => subscription.unsubscribe();
}, []);
```

### Keys in Lists
- Use stable unique IDs, not array indexes
- Index as key only for static lists

### Performance Optimization
```jsx
// Memoize expensive computations
const sorted = useMemo(() =>
  items.sort((a, b) => a.name.localeCompare(b.name)),
  [items]
);

// Memoize callbacks to prevent re-renders
const handleClick = useCallback(() => {
  doSomething(id);
}, [id]);
```

## CSS Patterns

### Responsive Design
```css
/* Mobile-first approach */
.container {
  padding: 1rem;
  display: flex;
  flex-direction: column;
}

/* Tablet and up */
@media (min-width: 768px) {
  .container {
    flex-direction: row;
    padding: 2rem;
  }
}
```

### Modern CSS Features
```css
/* Custom properties for theming */
:root {
  --color-primary: #007bff;
  --spacing-unit: 8px;
}

/* Container queries */
@container (min-width: 400px) {
  .card {
    display: grid;
    grid-template-columns: 1fr 2fr;
  }
}
```

### GPU-Accelerated Animations
```css
/* Use transform and opacity for smooth animations */
.fade-in {
  animation: fadeIn 0.3s ease-in;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

## Accessibility Patterns

### Semantic HTML
```jsx
// Good
<button onClick={handleClick}>Submit</button>

// Bad
<div onClick={handleClick}>Submit</div>
```

### ARIA Labels
```jsx
<button aria-label="Close dialog" onClick={onClose}>
  <CloseIcon />
</button>
```

### Keyboard Navigation
```jsx
const handleKeyDown = (e: React.KeyboardEvent) => {
  if (e.key === 'Enter' || e.key === ' ') {
    e.preventDefault();
    handleClick();
  }
};
```
