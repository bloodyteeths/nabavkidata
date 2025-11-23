# nabavkidata Branding Assets

This folder contains all brand identity assets for nabavkidata.com.

## Contents

- **logo.png** - Primary brand logo (AI-themed minimalist design)
- **favicon.png** - Favicon source file (512x512px)
- **grid.svg** - Background grid pattern for hero sections
- **brand-guide.md** - Comprehensive brand identity guidelines

## Quick Start

### Using the Logo
```tsx
<img src="/logo.png" alt="nabavkidata" className="h-8" />
```

### Using the Favicon
The favicon has been copied to `frontend/public/`. To convert to .ico format:

```bash
# Option 1: Using ImageMagick (if installed)
convert favicon.png -define icon:auto-resize=16,32,48,64,256 favicon.ico

# Option 2: Use online converter
# Visit: https://favicon.io/favicon-converter/
# Upload: branding/favicon.png
```

### Using the Grid Pattern
```tsx
<div className="bg-[url('/grid.svg')] bg-center [mask-image:linear-gradient(180deg,white,rgba(255,255,255,0))]" />
```

## Color Palette

- **Primary Blue**: `#1e40af`
- **Accent Cyan**: `#06b6d4`
- **Slate Gray**: `#64748b`
- **Light Gray**: `#f1f5f9`

## Deployment

Assets have been automatically copied to:
- `frontend/public/logo.png`
- `frontend/public/favicon.png`
- `frontend/public/grid.svg`

After converting favicon.png to favicon.ico, place it in `frontend/public/favicon.ico`.

## Design Philosophy

The nabavkidata brand embodies:
- **Minimalism** - Clean, focused design
- **Intelligence** - AI-powered insights
- **Professionalism** - Trustworthy and reliable
- **Modernity** - Cutting-edge technology

## More Information

See [brand-guide.md](./brand-guide.md) for complete brand guidelines including:
- Logo usage rules
- Typography standards
- Color specifications
- Accessibility guidelines
- Implementation examples

---

**Created**: 2025-11-23  
**Design**: AI-generated minimalist branding
