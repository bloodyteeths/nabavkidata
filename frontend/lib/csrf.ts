/**
 * CSRF Protection Utilities
 * Generates and validates CSRF tokens for form submissions
 */

const CSRF_TOKEN_KEY = 'csrf_token';
const CSRF_TOKEN_EXPIRY_MS = 60 * 60 * 1000; // 1 hour

interface CSRFToken {
  token: string;
  expiry: number;
}

/**
 * Generate a cryptographically secure random token
 */
export function generateCSRFToken(): string {
  // Generate random bytes
  const array = new Uint8Array(32);
  crypto.getRandomValues(array);

  // Convert to hex string
  return Array.from(array, byte => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Get current CSRF token from sessionStorage
 * Creates a new one if expired or doesn't exist
 */
export function getCSRFToken(): string {
  if (typeof window === 'undefined') {
    return '';
  }

  try {
    const stored = sessionStorage.getItem(CSRF_TOKEN_KEY);

    if (stored) {
      const parsed: CSRFToken = JSON.parse(stored);

      // Check if token is still valid
      if (Date.now() < parsed.expiry) {
        return parsed.token;
      }
    }
  } catch (e) {
    console.error('Error reading CSRF token:', e);
  }

  // Generate new token
  const newToken = generateCSRFToken();
  const tokenData: CSRFToken = {
    token: newToken,
    expiry: Date.now() + CSRF_TOKEN_EXPIRY_MS,
  };

  sessionStorage.setItem(CSRF_TOKEN_KEY, JSON.stringify(tokenData));
  return newToken;
}

/**
 * Validate CSRF token
 */
export function validateCSRFToken(token: string): boolean {
  if (!token || typeof window === 'undefined') {
    return false;
  }

  try {
    const stored = sessionStorage.getItem(CSRF_TOKEN_KEY);

    if (!stored) {
      return false;
    }

    const parsed: CSRFToken = JSON.parse(stored);

    // Check token match and expiry
    return parsed.token === token && Date.now() < parsed.expiry;
  } catch (e) {
    console.error('Error validating CSRF token:', e);
    return false;
  }
}

/**
 * Clear CSRF token
 */
export function clearCSRFToken(): void {
  if (typeof window === 'undefined') {
    return;
  }

  sessionStorage.removeItem(CSRF_TOKEN_KEY);
}

/**
 * Add CSRF token to form data
 */
export function addCSRFToFormData(formData: FormData): FormData {
  const token = getCSRFToken();
  formData.append('csrf_token', token);
  return formData;
}

/**
 * Add CSRF token to request headers
 */
export function addCSRFToHeaders(headers: HeadersInit = {}): HeadersInit {
  const token = getCSRFToken();
  return {
    ...headers,
    'X-CSRF-Token': token,
  };
}

/**
 * Hook for React components to use CSRF protection
 */
export function useCSRF() {
  const getToken = () => getCSRFToken();
  const validateToken = (token: string) => validateCSRFToken(token);
  const clearToken = () => clearCSRFToken();

  return {
    getToken,
    validateToken,
    clearToken,
    addToFormData: addCSRFToFormData,
    addToHeaders: addCSRFToHeaders,
  };
}
