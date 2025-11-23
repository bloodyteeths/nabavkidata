# Vercel Environment Variables Setup

Please add these environment variables to your Vercel project:

## Production Environment Variables

Go to your Vercel project settings → Environment Variables and add:

### Required Variables

| Variable Name | Value | Environment |
|---------------|-------|-------------|
| `NEXT_PUBLIC_API_URL` | `https://api.nabavkidata.com` | Production |
| `NEXT_PUBLIC_ENV` | `production` | Production |

## How to Add

1. Go to https://vercel.com/dashboard
2. Select your nabavkidata project
3. Go to Settings → Environment Variables
4. Add each variable with the value above
5. Select "Production" environment
6. Click "Save"
7. Trigger a new deployment from the Deployments tab

## Automatic Deployment

Once these variables are set, Vercel will automatically rebuild your frontend with the correct API URL pointing to:

**https://api.nabavkidata.com**

The frontend will then be able to communicate with the backend API via HTTPS.
