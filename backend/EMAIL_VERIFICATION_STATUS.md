# Email Verification Workflow - Status & Documentation

## Current Status: **DISABLED FOR TESTING**

Email verification is currently **disabled** in production due to AWS SES being in sandbox mode. The infrastructure is in place but checks are commented out.

## Architecture Overview

### Database Schema

1. **users table** - Main user model
   - `email_verified` (BOOLEAN) - Tracks verification status

2. **users_auth table** - Extended auth model
   - `is_verified` (BOOLEAN) - Additional verification flag
   - Relationships to email_verifications table

3. **email_verifications table**
   - `verification_id` (UUID, PK)
   - `user_id` (UUID, FK to users_auth)
   - `email` (VARCHAR)
   - `token` (VARCHAR, unique)
   - `is_used` (BOOLEAN)
   - `expires_at` (TIMESTAMP)
   - `used_at` (TIMESTAMP)
   - `ip_address` (INET)
   - `created_at` (TIMESTAMP)

### Backend Components

#### 1. Services
- **`services/auth_service.py`**
  - `generate_verification_token()` - Creates secure tokens
  - `verify_email_token()` - Validates and marks email as verified
  - Token storage in memory (verification_tokens dict)
  - 24-hour token expiry

- **`services/email_service.py`**
  - `send_verification_email()` - Sends verification link via AWS SES
  - Email template with branding
  - Verification URL: `{FRONTEND_URL}/auth/verify-email?token={token}`

#### 2. API Endpoints (`api/auth.py`)
- `POST /api/auth/register` - Creates user, generates token, sends email
- `POST /api/auth/verify-email` - Verifies token and marks email as verified
- `POST /api/auth/resend-verification` - Resends verification email

#### 3. Middleware (`middleware/rbac.py`)
- `get_current_active_user()` - **Currently disabled** email verification check
```python
# TEMPORARY: Email verification disabled for testing (AWS SES in sandbox mode)
# if not current_user.email_verified:
#     raise HTTPException(
#         status_code=status.HTTP_403_FORBIDDEN,
#         detail="Email not verified. Please verify your email to access this resource.",
#     )
```

### Frontend Components

#### 1. Auth Context (`frontend/lib/auth.tsx`)
- `verifyEmail(token)` - Calls backend to verify token
- `resendVerification()` - Requests new verification email
- Stores verification status in user state

#### 2. Pages
- `frontend/app/auth/verify-email/page.tsx` - Email verification landing page
- Shows loading, success, or error states

#### 3. User Interface
- User model includes `email_verified` field
- Displayed in settings/profile pages

## Email Verification Flow

### 1. Registration Flow
```
User submits registration
    ↓
Backend creates user account (email_verified=False)
    ↓
Generate verification token (24h expiry)
    ↓
Send verification email via AWS SES
    ↓
Return access token (user can login but with limited access)
```

### 2. Verification Flow
```
User clicks verification link
    ↓
Frontend extracts token from URL
    ↓
POST /api/auth/verify-email with token
    ↓
Backend validates token
    ↓
Update user.email_verified = True
    ↓
Return success response
    ↓
Frontend redirects to dashboard
```

### 3. Resend Flow
```
User clicks "Resend verification email"
    ↓
POST /api/auth/resend-verification (requires auth)
    ↓
Generate new token
    ↓
Send new email
    ↓
Return success message
```

## Security Considerations

### Token Security
- **Generation**: Cryptographically secure random tokens
- **Storage**: In-memory dictionary (should migrate to database or Redis)
- **Expiry**: 24 hours from creation
- **One-time use**: Token invalidated after successful verification
- **Rate limiting**: Should be implemented on resend endpoint

### Current Vulnerabilities
1. **Tokens stored in memory** - Lost on server restart
   - *Solution*: Use email_verifications table or Redis
2. **No rate limiting** on resend endpoint
   - *Solution*: Add rate limiting middleware
3. **Token in URL** - Can leak via referrer headers
   - *Acceptable*: Common practice, tokens expire quickly

## AWS SES Configuration

### Current Status: SANDBOX MODE

**Limitations:**
- Can only send to verified email addresses
- 200 emails per 24 hours
- 1 email per second

**Verified Addresses:**
- (List production verified sender emails here)

### Moving to Production

To enable email verification in production:

1. **Request SES Production Access**
   ```bash
   # Submit production access request in AWS Console
   # Typical approval time: 24-48 hours
   ```

2. **Update Environment Variables**
   ```bash
   AWS_SES_REGION=us-east-1
   AWS_ACCESS_KEY_ID=your_key
   AWS_SECRET_ACCESS_KEY=your_secret
   SES_SENDER_EMAIL=noreply@nabavkidata.com
   FRONTEND_URL=https://nabavkidata.com
   ```

3. **Enable Verification Checks**
   - Uncomment check in `middleware/rbac.py`
   - Test thoroughly before deploying

4. **Migrate Token Storage**
   ```python
   # Option 1: Use database (email_verifications table)
   # Option 2: Use Redis for better performance
   ```

## Testing

### Local Testing
```bash
# Set AWS credentials
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test

# Add test email to verified list in SES
# Or use email service mock
```

### Test Endpoints
```bash
# Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Test123!","full_name":"Test User"}'

# Verify email (get token from email/logs)
curl -X POST http://localhost:8000/api/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"token":"verification_token_here"}'

# Resend verification
curl -X POST http://localhost:8000/api/auth/resend-verification \
  -H "Authorization: Bearer your_access_token"
```

## Monitoring

### Metrics to Track
- Verification rate (verified users / total users)
- Time to verification (registration → verification)
- Resend requests per user
- Failed verification attempts
- Bounce rate from SES

### Logging
```python
# Key events to log:
- Email verification sent (user_id, email)
- Email verification success (user_id, email, time_since_registration)
- Email verification failed (user_id, token, reason)
- Resend requests (user_id, count)
```

## Roadmap

### Phase 1: Database Token Storage
- [ ] Migrate from in-memory to email_verifications table
- [ ] Add token cleanup job (delete expired tokens)
- [ ] Add indexes for performance

### Phase 2: Production SES
- [ ] Request and obtain production SES access
- [ ] Configure SPF, DKIM, DMARC records
- [ ] Test with real email addresses
- [ ] Monitor deliverability rates

### Phase 3: Re-enable Verification
- [ ] Uncomment verification checks in middleware
- [ ] Add grace period (e.g., 7 days to verify)
- [ ] Implement reminder emails
- [ ] Add verification status UI warnings

### Phase 4: Enhanced Features
- [ ] Magic link authentication (passwordless)
- [ ] Email change verification
- [ ] Rate limiting on resend
- [ ] Verification analytics dashboard

## Troubleshooting

### Common Issues

**Issue**: User doesn't receive verification email
- Check SES sandbox mode status
- Verify sender email is configured
- Check spam folder
- Review CloudWatch logs for SES errors

**Issue**: Token expired
- Tokens expire after 24 hours
- User can request resend
- Consider extending expiry time

**Issue**: Token invalid
- May have been used already
- May be malformed
- Check logs for token generation

### Debug Commands

```python
# Check user verification status
SELECT user_id, email, email_verified FROM users WHERE email = 'user@example.com';

# Check pending verifications
SELECT * FROM email_verifications WHERE is_used = false AND expires_at > NOW();

# Check verification history
SELECT user_id, email, is_used, created_at, used_at
FROM email_verifications
WHERE user_id = 'user_uuid_here'
ORDER BY created_at DESC;
```

## References

- AWS SES Documentation: https://docs.aws.amazon.com/ses/
- FastAPI Security: https://fastapi.tiangolo.com/tutorial/security/
- Email Verification Best Practices: https://www.twilio.com/blog/email-verification-best-practices

---

**Last Updated**: November 23, 2025
**Status**: Email verification infrastructure complete but disabled pending AWS SES production access
**Owner**: Security & Auth Team
