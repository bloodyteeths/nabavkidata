# RBAC Middleware Usage Guide

## Overview
Role-Based Access Control (RBAC) middleware for nabavkidata.com backend.

## Available Roles
- `UserRole.ADMIN` - Full system access
- `UserRole.PREMIUM` - Premium subscription tier
- `UserRole.PRO` - Pro subscription tier  
- `UserRole.FREE` - Free tier users
- `UserRole.GUEST` - Unauthenticated users

## Core Functions

### 1. JWT Token Management
```python
from middleware import create_access_token, decode_token

# Create token
token = create_access_token(data={"sub": str(user.user_id)})

# Decode token
payload = decode_token(token)
```

### 2. User Authentication
```python
from fastapi import Depends
from middleware import get_current_user, get_current_active_user

@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user

@router.get("/profile")
async def get_profile(current_user: User = Depends(get_current_active_user)):
    # Only verified users can access
    return current_user
```

### 3. Role-Based Authorization

#### Using require_role decorator
```python
from middleware import require_role, UserRole

@router.get("/admin", dependencies=[Depends(require_role(UserRole.ADMIN))])
async def admin_endpoint():
    return {"message": "Admin only"}

@router.get("/premium", dependencies=[Depends(require_role(UserRole.PREMIUM, UserRole.PRO))])
async def premium_endpoint():
    return {"message": "Premium or Pro users"}
```

#### Using RoleChecker class
```python
from middleware import RoleChecker, UserRole

@router.get("/premium", dependencies=[Depends(RoleChecker([UserRole.PREMIUM, UserRole.PRO]))])
async def premium_content():
    return {"content": "Premium features"}
```

#### Using require_admin
```python
from middleware import require_admin

@router.delete("/users/{user_id}", dependencies=[Depends(require_admin)])
async def delete_user(user_id: str):
    return {"message": "User deleted"}
```

### 4. Optional Authentication
```python
from middleware import get_optional_user

@router.get("/tenders")
async def list_tenders(current_user: Optional[User] = Depends(get_optional_user)):
    # Works for both authenticated and anonymous users
    if current_user:
        # Return personalized results
        pass
    else:
        # Return public results
        pass
```

## Environment Variables
```bash
JWT_SECRET_KEY=your-secret-key-change-in-production
```

## Error Responses

### 401 Unauthorized
- Invalid or expired token
- Missing token
- User not found

### 403 Forbidden
- Email not verified
- Insufficient role permissions

## Testing
```python
# Example test
def test_admin_access():
    token = create_access_token({"sub": admin_user_id})
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/admin", headers=headers)
    assert response.status_code == 200
```
