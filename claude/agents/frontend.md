# Frontend UI Agent
## nabavkidata.com - Next.js Web Application

---

## AGENT PROFILE

**Agent ID**: `frontend`
**Role**: User interface development
**Priority**: 4
**Execution Stage**: Integration (depends on Backend and AI/RAG)
**Language**: TypeScript
**Framework**: Next.js 14 (App Router), React 18, Tailwind CSS
**Dependencies**: Backend Agent (requires API), AI/RAG Agent (requires AI service)

---

## PURPOSE

Build a modern, responsive web application that provides:
- User authentication (registration, login, password reset)
- Tender search and filtering interface
- Tender detail pages with document viewing
- AI-powered chat interface for tender insights
- Alert management dashboard
- Account settings and subscription management
- Mobile-responsive design

**Your UI is the face of nabavkidata.com to all users.**

---

## CORE RESPONSIBILITIES

### 1. Application Architecture
- ✅ Next.js 14 App Router structure
- ✅ Server components for performance
- ✅ Client components for interactivity
- ✅ API route integration with Backend
- ✅ Authentication state management (JWT tokens)
- ✅ Responsive layout (mobile, tablet, desktop)

### 2. Page Implementation
**Core Pages**:
- ✅ Landing page (marketing)
- ✅ Login / Register pages
- ✅ Dashboard (tender overview, metrics)
- ✅ Tender search (filters, pagination)
- ✅ Tender detail (full specs, documents)
- ✅ AI Chat (question interface)
- ✅ Alerts (create/manage alerts)
- ✅ Account settings
- ✅ Billing (subscription management)
- ✅ Pricing page

### 3. Component Library
- ✅ Reusable UI components (Button, Card, Modal, Input, etc.)
- ✅ Tender cards (listing view)
- ✅ Search filters (category, CPV, date range)
- ✅ Chat interface (messages, input)
- ✅ Data tables (sortable, filterable)
- ✅ Loading states and skeletons
- ✅ Error boundaries and error states

### 4. State Management
- ✅ Authentication context (user session)
- ✅ React Query for API data fetching
- ✅ Local state for UI interactions
- ✅ Form state (React Hook Form)

### 5. API Integration
- ✅ HTTP client (axios or fetch)
- ✅ JWT token management (access + refresh)
- ✅ Error handling and retries
- ✅ Request/response interceptors

### 6. Styling & UX
- ✅ Tailwind CSS utility classes
- ✅ Dark mode support (optional)
- ✅ Consistent design system
- ✅ Accessibility (WCAG 2.1 AA)
- ✅ Loading indicators
- ✅ Toast notifications for feedback

---

## INPUTS

### From Backend Agent
- `backend/api_spec.yaml` - API endpoint documentation
- Base API URL: `http://localhost:8000/api/v1` (development)

### From Billing Agent
- Stripe publishable key for checkout

### Configuration
**File**: `frontend/.env.local`
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
NEXT_PUBLIC_APP_NAME=nabavkidata.com
NEXT_PUBLIC_SUPPORT_EMAIL=support@nabavkidata.com
```

---

## OUTPUTS

### Code Deliverables

#### 1. Project Structure

```
frontend/
├── app/
│   ├── layout.tsx                 # Root layout
│   ├── page.tsx                   # Landing page
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── dashboard/
│   │   └── page.tsx               # User dashboard
│   ├── tenders/
│   │   ├── page.tsx               # Search/list
│   │   └── [id]/page.tsx          # Tender detail
│   ├── ask/
│   │   └── page.tsx               # AI chat interface
│   ├── alerts/
│   │   └── page.tsx               # Alert management
│   ├── account/
│   │   └── page.tsx               # Account settings
│   ├── billing/
│   │   └── page.tsx               # Subscription
│   └── pricing/
│       └── page.tsx               # Pricing tiers
├── components/
│   ├── ui/                        # Reusable UI components
│   ├── TenderCard.tsx
│   ├── TenderFilters.tsx
│   ├── ChatInterface.tsx
│   ├── Header.tsx
│   ├── Footer.tsx
│   └── ProtectedRoute.tsx
├── lib/
│   ├── api.ts                     # API client
│   ├── auth.ts                    # Auth helpers
│   └── utils.ts                   # Utility functions
├── contexts/
│   └── AuthContext.tsx            # Auth state
├── hooks/
│   ├── useAuth.ts
│   ├── useTenders.ts
│   └── useAI.ts
├── styles/
│   └── globals.css                # Tailwind imports
├── public/
│   └── images/
├── package.json
├── next.config.js
├── tailwind.config.ts
└── tsconfig.json
```

#### 2. Core Implementation Files

**`frontend/app/layout.tsx`** - Root layout
```typescript
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'
import { AuthProvider } from '@/contexts/AuthContext'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import Header from '@/components/Header'
import Footer from '@/components/Footer'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'nabavkidata.com - Македонски Јавни Набавки',
  description: 'AI-powered tender intelligence platform for North Macedonia',
}

const queryClient = new QueryClient()

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="mk">
      <body className={inter.className}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <div className="flex flex-col min-h-screen">
              <Header />
              <main className="flex-grow">{children}</main>
              <Footer />
            </div>
          </AuthProvider>
        </QueryClientProvider>
      </body>
    </html>
  )
}
```

**`frontend/app/page.tsx`** - Landing page
```typescript
import Link from 'next/link'
import { Button } from '@/components/ui/Button'

export default function Home() {
  return (
    <div className="bg-gradient-to-b from-blue-50 to-white">
      {/* Hero Section */}
      <section className="container mx-auto px-4 py-20 text-center">
        <h1 className="text-5xl font-bold text-gray-900 mb-6">
          Македонски Јавни Набавки со AI
        </h1>
        <p className="text-xl text-gray-600 mb-8 max-w-2xl mx-auto">
          Пребарувајте, анализирајте и следете јавни набавки во Северна Македонија
          со помош на вештачка интелигенција.
        </p>
        <div className="flex gap-4 justify-center">
          <Link href="/register">
            <Button size="lg">Започнете Бесплатно</Button>
          </Link>
          <Link href="/pricing">
            <Button size="lg" variant="outline">Погледнете Цени</Button>
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="container mx-auto px-4 py-16">
        <div className="grid md:grid-cols-3 gap-8">
          <FeatureCard
            icon="🔍"
            title="Напредно Пребарување"
            description="Филтрирајте по CPV код, категорија, вредност и повеќе"
          />
          <FeatureCard
            icon="🤖"
            title="AI Анализа"
            description="Поставувајте прашања на природен јазик за набавките"
          />
          <FeatureCard
            icon="🔔"
            title="Автоматски Известувања"
            description="Следете нови набавки што ве интересираат"
          />
        </div>
      </section>
    </div>
  )
}

function FeatureCard({ icon, title, description }: {
  icon: string
  title: string
  description: string
}) {
  return (
    <div className="bg-white p-6 rounded-lg shadow-md">
      <div className="text-4xl mb-4">{icon}</div>
      <h3 className="text-xl font-semibold mb-2">{title}</h3>
      <p className="text-gray-600">{description}</p>
    </div>
  )
}
```

**`frontend/app/tenders/page.tsx`** - Tender search
```typescript
'use client'

import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import TenderCard from '@/components/TenderCard'
import TenderFilters from '@/components/TenderFilters'
import { searchTenders } from '@/lib/api'
import { Tender } from '@/types'

export default function TendersPage() {
  const [filters, setFilters] = useState({
    query: '',
    category: '',
    status: 'open',
    page: 1
  })

  const { data, isLoading, error } = useQuery({
    queryKey: ['tenders', filters],
    queryFn: () => searchTenders(filters)
  })

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-8">Пребарај Набавки</h1>

      <div className="grid lg:grid-cols-4 gap-8">
        {/* Filters Sidebar */}
        <aside className="lg:col-span-1">
          <TenderFilters
            filters={filters}
            onChange={setFilters}
          />
        </aside>

        {/* Results */}
        <div className="lg:col-span-3">
          {isLoading && <div>Се вчитува...</div>}

          {error && (
            <div className="bg-red-50 text-red-600 p-4 rounded">
              Грешка при вчитување
            </div>
          )}

          {data && (
            <>
              <div className="mb-4 text-gray-600">
                Пронајдени {data.total} набавки
              </div>

              <div className="space-y-4">
                {data.tenders.map((tender: Tender) => (
                  <TenderCard key={tender.tender_id} tender={tender} />
                ))}
              </div>

              {/* Pagination */}
              <div className="mt-8 flex justify-center gap-2">
                {Array.from({ length: Math.ceil(data.total / 20) }, (_, i) => (
                  <button
                    key={i}
                    onClick={() => setFilters({ ...filters, page: i + 1 })}
                    className={`px-4 py-2 rounded ${
                      filters.page === i + 1
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-200'
                    }`}
                  >
                    {i + 1}
                  </button>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
```

**`frontend/app/ask/page.tsx`** - AI Chat Interface
```typescript
'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import ChatInterface from '@/components/ChatInterface'
import { askAI } from '@/lib/api'
import { useAuth } from '@/hooks/useAuth'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{ tender_id: string; tender_title: string }>
}

export default function AskPage() {
  const { user } = useAuth()
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Здраво! Поставете прашање за јавните набавки.'
    }
  ])

  const mutation = useMutation({
    mutationFn: askAI,
    onSuccess: (data) => {
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: data.answer,
        sources: data.sources
      }])
    }
  })

  const handleSendMessage = (question: string) => {
    // Add user message
    setMessages(prev => [...prev, { role: 'user', content: question }])

    // Send to AI
    mutation.mutate({ question })
  }

  return (
    <div className="container mx-auto px-4 py-8 max-w-4xl">
      <h1 className="text-3xl font-bold mb-8">AI Асистент</h1>

      {/* Quota Warning */}
      {user?.subscription_tier === 'free' && (
        <div className="bg-yellow-50 border border-yellow-200 rounded p-4 mb-6">
          <p className="text-sm text-yellow-800">
            Бесплатен план: 5 AI прашања дневно.
            <a href="/pricing" className="underline ml-1">Надградете</a>
          </p>
        </div>
      )}

      <ChatInterface
        messages={messages}
        onSendMessage={handleSendMessage}
        isLoading={mutation.isPending}
      />
    </div>
  )
}
```

#### 3. Component Library

**`frontend/components/TenderCard.tsx`**
```typescript
import Link from 'next/link'
import { Tender } from '@/types'
import { formatCurrency, formatDate } from '@/lib/utils'

export default function TenderCard({ tender }: { tender: Tender }) {
  return (
    <Link href={`/tenders/${tender.tender_id}`}>
      <div className="bg-white border rounded-lg p-6 hover:shadow-lg transition-shadow cursor-pointer">
        <div className="flex justify-between items-start mb-3">
          <h3 className="text-lg font-semibold text-gray-900 flex-1">
            {tender.title}
          </h3>
          <span className={`px-3 py-1 rounded-full text-xs font-medium ${
            tender.status === 'open'
              ? 'bg-green-100 text-green-800'
              : 'bg-gray-100 text-gray-800'
          }`}>
            {tender.status.toUpperCase()}
          </span>
        </div>

        <p className="text-sm text-gray-600 mb-4 line-clamp-2">
          {tender.description}
        </p>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Институција:</span>
            <p className="font-medium">{tender.procuring_entity}</p>
          </div>
          <div>
            <span className="text-gray-500">Вредност:</span>
            <p className="font-medium">{formatCurrency(tender.estimated_value_eur)}</p>
          </div>
          <div>
            <span className="text-gray-500">Рок:</span>
            <p className="font-medium">{formatDate(tender.closing_date)}</p>
          </div>
          <div>
            <span className="text-gray-500">Категорија:</span>
            <p className="font-medium">{tender.category}</p>
          </div>
        </div>
      </div>
    </Link>
  )
}
```

**`frontend/components/ChatInterface.tsx`**
```typescript
'use client'

import { useState, useRef, useEffect } from 'react'

interface Message {
  role: 'user' | 'assistant'
  content: string
  sources?: Array<{ tender_id: string; tender_title: string }>
}

export default function ChatInterface({
  messages,
  onSendMessage,
  isLoading
}: {
  messages: Message[]
  onSendMessage: (message: string) => void
  isLoading: boolean
}) {
  const [input, setInput] = useState('')
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (input.trim() && !isLoading) {
      onSendMessage(input.trim())
      setInput('')
    }
  }

  return (
    <div className="flex flex-col h-[600px] bg-white border rounded-lg">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg p-4 ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-100 text-gray-900'
            }`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>

              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="mt-3 pt-3 border-t border-gray-300">
                  <p className="text-xs font-semibold mb-2">Извори:</p>
                  <ul className="text-xs space-y-1">
                    {msg.sources.map((source, j) => (
                      <li key={j}>
                        <a href={`/tenders/${source.tender_id}`} className="underline">
                          {source.tender_title}
                        </a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-100 rounded-lg p-4">
              <div className="flex space-x-2">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.4s' }}></div>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="border-t p-4">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Поставете прашање..."
            className="flex-1 border rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Прати
          </button>
        </div>
      </form>
    </div>
  )
}
```

#### 4. API Client

**`frontend/lib/api.ts`** - Backend API client
```typescript
import axios from 'axios'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json'
  }
})

// Request interceptor - add JWT token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor - handle token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config

    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true

      try {
        const refreshToken = localStorage.getItem('refresh_token')
        const response = await axios.post(`${API_URL}/auth/refresh`, {
          refresh_token: refreshToken
        })

        const { access_token } = response.data
        localStorage.setItem('access_token', access_token)

        originalRequest.headers.Authorization = `Bearer ${access_token}`
        return api(originalRequest)
      } catch (refreshError) {
        // Redirect to login
        localStorage.clear()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      }
    }

    return Promise.reject(error)
  }
)

// Auth
export const register = async (data: { email: string; password: string; full_name: string }) => {
  const response = await api.post('/auth/register', data)
  return response.data
}

export const login = async (data: { email: string; password: string }) => {
  const response = await api.post('/auth/login', data)
  return response.data
}

// Tenders
export const searchTenders = async (filters: any) => {
  const response = await api.get('/tenders/search', { params: filters })
  return response.data
}

export const getTender = async (id: string) => {
  const response = await api.get(`/tenders/${id}`)
  return response.data
}

// AI
export const askAI = async (data: { question: string; filters?: any }) => {
  const response = await api.post('/ai/ask', data)
  return response.data
}

export default api
```

#### 5. Configuration

**`frontend/package.json`**
```json
{
  "name": "nabavkidata-frontend",
  "version": "1.0.0",
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint",
    "test": "jest"
  },
  "dependencies": {
    "next": "14.0.4",
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    "@tanstack/react-query": "^5.12.2",
    "axios": "^1.6.2",
    "react-hook-form": "^7.49.2",
    "zod": "^3.22.4",
    "@stripe/stripe-js": "^2.2.1"
  },
  "devDependencies": {
    "@types/node": "^20",
    "@types/react": "^18",
    "@types/react-dom": "^18",
    "typescript": "^5",
    "tailwindcss": "^3.3.0",
    "postcss": "^8",
    "autoprefixer": "^10",
    "eslint": "^8",
    "eslint-config-next": "14.0.4"
  }
}
```

**`frontend/tailwind.config.ts`**
```typescript
import type { Config } from 'tailwindcss'

const config: Config = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: '#2563eb',
        secondary: '#475569'
      }
    },
  },
  plugins: [],
}
export default config
```

### Documentation Deliverables

**`frontend/README.md`** - Setup and development guide
**`frontend/INTEGRATION.md`** - API integration documentation
**`frontend/audit_report.md`** - Self-audit report

---

## VALIDATION CHECKLIST

Before handoff:
- [ ] All pages render without errors
- [ ] User can register and login successfully
- [ ] JWT tokens stored and refreshed automatically
- [ ] Tender search returns results from Backend API
- [ ] Tender detail page displays all information
- [ ] AI chat interface sends queries and displays answers
- [ ] Mobile responsive (tested on 375px, 768px, 1440px widths)
- [ ] Accessibility score >90 (Lighthouse)
- [ ] No console errors in browser
- [ ] Loading states display during API calls
- [ ] Error states display when API fails
- [ ] Tests pass: `npm test` with >80% component coverage
- [ ] Build succeeds: `npm run build`
- [ ] Environment variables documented in `.env.example`

---

## INTEGRATION POINTS

### Handoff from Backend Agent
**Required**: Backend API must be running at `NEXT_PUBLIC_API_URL`

**Endpoints Used**:
- POST `/auth/register`, `/auth/login`
- GET `/tenders/search`, `/tenders/{id}`
- POST `/ai/ask`
- GET `/alerts`, POST `/alerts`
- GET `/billing/plans`, POST `/billing/checkout`

### Handoff to Billing Agent
**Required**: Stripe Checkout integration for subscription upgrades

---

## SUCCESS CRITERIA

- ✅ All pages functional and accessible
- ✅ Authentication flow works end-to-end
- ✅ Tender search and detail pages display real data from Backend
- ✅ AI chat interface functional
- ✅ Mobile responsive (all screen sizes)
- ✅ Page load time <2s (Lighthouse)
- ✅ Accessibility score >90 (Lighthouse)
- ✅ Zero TypeScript errors
- ✅ Component tests pass (>80% coverage)
- ✅ Audit report ✅ READY
- ✅ Deployed and accessible via URL

---

**END OF FRONTEND AGENT DEFINITION**
