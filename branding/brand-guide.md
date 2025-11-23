# nabavkidata.com Brand Identity Guide

## Overview
nabavkidata is a Macedonian tender intelligence platform powered by AI. The brand identity reflects modern technology, data intelligence, and professional trustworthiness.

## Brand Essence
- **Modern**: Cutting-edge AI technology
- **Intelligent**: Data-driven insights
- **Trustworthy**: Professional and reliable
- **Minimalist**: Clean, focused design

---

## Logo

### Primary Logo
**File**: `logo.png`

**Design Concept**: Abstract geometric representation combining document/tender elements with AI neural network patterns. The design suggests data analysis, intelligence, and automation.

**Usage**:
- Primary brand mark for headers, marketing materials
- Works on light and dark backgrounds
- Minimum size: 32px height for digital, 0.5 inch for print

**Don'ts**:
- Don't stretch or distort
- Don't change colors
- Don't add effects or shadows
- Don't place on busy backgrounds

---

## Favicon

### Browser Icon
**File**: `favicon.png`

**Design**: Ultra-simplified version optimized for 16x16px display. Maintains brand recognition at tiny sizes.

**Usage**:
- Browser tabs
- Bookmarks
- Mobile home screen icons

---

## Color Palette

### Primary Colors

**Deep Blue** - Primary brand color
- Hex: `#1e40af`
- RGB: `30, 64, 175`
- Usage: Primary UI elements, headers, CTAs

**Cyan** - Accent color
- Hex: `#06b6d4`
- RGB: `6, 182, 212`
- Usage: Highlights, AI features, interactive elements

### Secondary Colors

**Slate Gray** - Text and backgrounds
- Hex: `#64748b`
- RGB: `100, 116, 139`
- Usage: Body text, secondary elements

**Light Gray** - Backgrounds
- Hex: `#f1f5f9`
- RGB: `241, 245, 249`
- Usage: Page backgrounds, cards

**White**
- Hex: `#ffffff`
- Usage: Primary backgrounds, text on dark

### Gradients

**Primary Gradient**
```css
background: linear-gradient(135deg, #1e40af 0%, #06b6d4 100%);
```

**Subtle Gradient** (for backgrounds)
```css
background: linear-gradient(180deg, #f1f5f9 0%, #ffffff 100%);
```

---

## Typography

### Primary Font
**Inter** - Modern, clean, highly legible
- Weights: 400 (Regular), 500 (Medium), 600 (Semibold), 700 (Bold)
- Usage: UI, body text, headings

### Fallback Stack
```css
font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', 
             'Roboto', 'Oxygen', 'Ubuntu', 'Cantarell', sans-serif;
```

### Type Scale
- **H1**: 2.5rem (40px) - Bold
- **H2**: 2rem (32px) - Semibold
- **H3**: 1.5rem (24px) - Semibold
- **H4**: 1.25rem (20px) - Medium
- **Body**: 1rem (16px) - Regular
- **Small**: 0.875rem (14px) - Regular

---

## Design Elements

### Grid Pattern
**File**: `grid.svg`

**Usage**: Subtle background pattern for hero sections and feature areas. Creates depth and tech aesthetic.

**Implementation**:
```css
background-image: url('/grid.svg');
background-position: center;
mask-image: linear-gradient(180deg, white, rgba(255,255,255,0));
```

---

## Asset Inventory

### Branding Folder Contents
```
/branding/
├── logo.png              # Primary logo (PNG)
├── favicon.png           # Favicon (PNG, 512x512)
├── grid.svg              # Background grid pattern
└── brand-guide.md        # This document
```

### Frontend Assets (to be deployed)
```
/frontend/public/
├── favicon.ico           # Convert from favicon.png
├── grid.svg              # Copy from branding/
└── logo.png              # Copy from branding/
```

---

## Implementation Notes

### Favicon Conversion
To create `favicon.ico` from `favicon.png`:
```bash
# Using ImageMagick
convert favicon.png -define icon:auto-resize=16,32,48,64,256 favicon.ico

# Or use online converter: https://favicon.io/favicon-converter/
```

### Next.js Metadata
```typescript
export const metadata = {
  title: 'nabavkidata.com - Македонска Платформа за Тендери',
  description: 'AI-powered tender intelligence platform for Macedonia',
  icons: {
    icon: '/favicon.ico',
    apple: '/logo.png',
  },
}
```

---

## Brand Voice

### Tone
- **Professional**: Expert, knowledgeable
- **Approachable**: Friendly, helpful
- **Confident**: Authoritative without arrogance
- **Clear**: Direct, jargon-free when possible

### Language
- **Macedonian**: Primary language for all user-facing content
- **English**: Secondary for technical documentation
- **Bilingual**: Privacy policy, terms of service

---

## Usage Examples

### Header Logo
```tsx
<img 
  src="/logo.png" 
  alt="nabavkidata" 
  className="h-8 w-auto"
/>
```

### Favicon
```html
<link rel="icon" href="/favicon.ico" />
<link rel="apple-touch-icon" href="/logo.png" />
```

### Brand Colors in Tailwind
```javascript
// tailwind.config.js
colors: {
  brand: {
    blue: '#1e40af',
    cyan: '#06b6d4',
  }
}
```

---

## Accessibility

### Color Contrast
All color combinations meet WCAG AA standards:
- Deep Blue (#1e40af) on White: 8.59:1 ✓
- Cyan (#06b6d4) on Deep Blue: 3.2:1 ✓
- Slate Gray (#64748b) on White: 4.54:1 ✓

### Logo Alt Text
- English: "nabavkidata logo"
- Macedonian: "nabavkidata лого"

---

**Version**: 1.0  
**Last Updated**: 2025-11-23  
**Maintained By**: nabavkidata Design Team
