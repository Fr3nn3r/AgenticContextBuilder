# Adding a New Theme

Quick guide to add a new color theme to the UI.

## Steps

### 1. Define CSS Variables in `ui/src/index.css`

Add both light and dark variants:

```css
/* Light mode */
.theme-mytheme {
  --background: oklch(0.98 0.01 250);
  --foreground: oklch(0.15 0.02 250);
  --card: oklch(0.97 0.015 250);
  --card-foreground: oklch(0.15 0.02 250);
  --primary: oklch(0.55 0.2 250);
  --primary-foreground: oklch(0.98 0.01 250);
  /* ... copy all variables from existing theme */
}

/* Dark mode */
.theme-mytheme.dark {
  --background: oklch(0.12 0.02 250);
  --foreground: oklch(0.95 0.01 250);
  /* ... all dark variants */
}
```

### 2. Safelist in `ui/tailwind.config.js`

Add theme class to prevent Tailwind from purging it:

```js
safelist: [
  "theme-northern-lights",
  "theme-default",
  "theme-pink",
  "theme-mytheme",  // <-- add here
  "dark",
],
```

### 3. Register in Provider (`ui/src/main.tsx`)

Add to the `colorThemes` array:

```tsx
<SpacemanThemeProvider
  colorThemes={['northern-lights', 'default', 'pink', 'mytheme']}
  // ...
>
```

### 4. Add UI Control in `ui/src/components/Sidebar.tsx`

Add a button in the color theme section:

```tsx
<button
  onClick={() => setColorTheme("mytheme")}
  className={cn(
    "...",
    colorTheme === "mytheme" && "ring-2 ring-primary"
  )}
  title="My Theme"
>
  <div className="w-3 h-3 rounded-full bg-[oklch(0.55_0.2_250)]" />
</button>
```

## CSS Variable Reference

| Variable | Usage |
|----------|-------|
| `--background` | Page background |
| `--foreground` | Default text |
| `--card` | Card/panel backgrounds |
| `--primary` | Buttons, links, active states |
| `--secondary` | Secondary buttons, muted actions |
| `--muted` | Subtle backgrounds |
| `--muted-foreground` | Secondary text |
| `--accent` | Highlights, hover states |
| `--border` | All borders |
| `--destructive` | Delete/error actions |
| `--success` | Success states |
| `--warning` | Warning states |

## Tips

- Use oklch color space for perceptually uniform colors
- Keep lightness ~0.95-0.98 for light backgrounds, ~0.10-0.15 for dark
- Test both light and dark modes
- Restart dev server after modifying tailwind.config.js
