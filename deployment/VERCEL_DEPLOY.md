# Vercel Deployment Guide
# nabavkidata.com Frontend

## Prerequisites
- GitHub repository: https://github.com/bloodyteeths/nabavkidata.git
- Vercel account
- Backend API deployed on Lightsail
- SSL configured for api.nabavkidata.com

## Step 1: Push Code to GitHub

```bash
cd /path/to/nabavkidata
git add .
git commit -m "Production deployment setup"
git push origin main
```

## Step 2: Import Project to Vercel

1. Go to https://vercel.com/new
2. Click "Import Git Repository"
3. Select your GitHub repository: `bloodyteeths/nabavkidata`
4. Select "frontend" as root directory
5. Framework Preset: Next.js (auto-detected)

## Step 3: Configure Environment Variables

Add these environment variables in Vercel dashboard:

### Production Environment Variables

```
NEXT_PUBLIC_API_URL=https://api.nabavkidata.com
NEXT_PUBLIC_APP_URL=https://nabavkidata.com
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_KEY_HERE
```

## Step 4: Configure Domain

1. Go to Project Settings ’ Domains
2. Add custom domain: `nabavkidata.com`
3. Add www alias: `www.nabavkidata.com`
4. Vercel will provide DNS records

### DNS Configuration

Add these records to your domain registrar:

```
Type    Name    Value
A       @       76.76.21.21
CNAME   www     cname.vercel-dns.com
```

## Step 5: Deploy

1. Click "Deploy"
2. Wait for build to complete (~2-3 minutes)
3. Vercel will auto-deploy on every push to main

## Step 6: Verify Deployment

Visit:
- https://nabavkidata.com
- https://nabavkidata.com/auth/login
- Check browser console for errors
- Test API connection

## Step 7: Configure CI/CD

### Automatic Deployments
- Push to `main` ’ Production deployment
- Push to `develop` ’ Preview deployment
- Pull requests ’ Preview deployments

### Branch Protection
```bash
# In GitHub repo settings
Settings ’ Branches ’ Add rule
Branch name pattern: main
 Require pull request reviews before merging
 Require status checks to pass before merging
```

## Step 8: Performance Optimization

### Vercel Settings
1. Analytics: Enable Web Analytics
2. Speed Insights: Enable
3. Image Optimization: Enabled by default
4. Edge Functions: Already configured

### Build Settings
```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "installCommand": "npm install"
}
```

## Step 9: Monitoring

### Vercel Dashboard
- Real-time logs
- Deployment history
- Analytics
- Performance metrics

### Error Tracking (Optional)
Add Sentry:
```bash
npm install @sentry/nextjs
```

## Troubleshooting

### Build Fails
```bash
# Check build logs in Vercel dashboard
# Common issues:
- Missing environment variables
- TypeScript errors
- Missing dependencies
```

### API Connection Issues
```bash
# Verify CORS headers on backend
# Check NEXT_PUBLIC_API_URL is correct
# Verify SSL certificate on api.nabavkidata.com
```

### Domain Not Resolving
```bash
# Check DNS propagation
dig nabavkidata.com

# Wait 24-48 hours for full propagation
```

## Production Checklist

- [ ] Backend API deployed on Lightsail
- [ ] SSL configured (api.nabavkidata.com)
- [ ] Database running on RDS
- [ ] S3 bucket configured
- [ ] Stripe keys added
- [ ] DNS records configured
- [ ] Vercel deployment successful
- [ ] Domain resolves correctly
- [ ] API endpoints working
- [ ] Authentication flow tested
- [ ] Payment flow tested
- [ ] Analytics enabled

## Environment Variables Reference

### Required
```
NEXT_PUBLIC_API_URL=https://api.nabavkidata.com
NEXT_PUBLIC_APP_URL=https://nabavkidata.com
```

### Payment Integration
```
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...
```

### Optional
```
NEXT_PUBLIC_SENTRY_DSN=https://...
NEXT_PUBLIC_GA_ID=G-...
```

## Deployment Commands

### Manual Deploy (if needed)
```bash
cd frontend
vercel --prod
```

### Preview Deploy
```bash
vercel
```

### Check Status
```bash
vercel ls
```

## Support

- Vercel Docs: https://vercel.com/docs
- Next.js Docs: https://nextjs.org/docs
- Project Issues: https://github.com/bloodyteeths/nabavkidata/issues
