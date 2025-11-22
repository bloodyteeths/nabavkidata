/**
 * K6 Load Testing Script for Nabavki Data Platform
 *
 * This script provides comprehensive performance testing scenarios with thresholds,
 * custom metrics, and realistic user behaviors.
 *
 * Usage:
 *   # Smoke test (minimal load)
 *   k6 run --vus 1 --duration 1m k6-script.js
 *
 *   # Load test (average expected load)
 *   k6 run --vus 100 --duration 10m k6-script.js
 *
 *   # Stress test (beyond normal capacity)
 *   k6 run --vus 500 --duration 15m k6-script.js
 *
 *   # Spike test (sudden traffic spike)
 *   k6 run --stage 0s:10,10s:1000,1m:1000,10s:10,1m:10 k6-script.js
 */

import http from 'k6/http';
import { check, group, sleep } from 'k6';
import { Rate, Trend, Counter, Gauge } from 'k6/metrics';
import { randomItem, randomIntBetween } from 'https://jslib.k6.io/k6-utils/1.2.0/index.js';

// Configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const API_BASE = `${BASE_URL}/api/v1`;

// Custom metrics
const tenderViewDuration = new Trend('tender_view_duration');
const searchDuration = new Trend('search_duration');
const ragQueryDuration = new Trend('rag_query_duration');
const authSuccessRate = new Rate('auth_success_rate');
const apiErrorRate = new Rate('api_error_rate');
const activeUsers = new Gauge('active_users');
const totalRequests = new Counter('total_requests');

// Performance thresholds
export const options = {
    // Define test scenarios
    scenarios: {
        // Smoke test - verify basic functionality
        smoke: {
            executor: 'constant-vus',
            vus: 1,
            duration: '1m',
            tags: { test_type: 'smoke' },
            exec: 'smokeTest',
        },

        // Load test - simulate average load
        load: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '2m', target: 50 },   // Ramp up to 50 users
                { duration: '5m', target: 100 },  // Ramp up to 100 users
                { duration: '10m', target: 100 }, // Stay at 100 users
                { duration: '2m', target: 50 },   // Ramp down to 50
                { duration: '1m', target: 0 },    // Ramp down to 0
            ],
            tags: { test_type: 'load' },
            exec: 'loadTest',
        },

        // Stress test - push beyond normal capacity
        stress: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '2m', target: 100 },
                { duration: '5m', target: 300 },
                { duration: '5m', target: 500 },
                { duration: '3m', target: 500 },
                { duration: '2m', target: 300 },
                { duration: '2m', target: 100 },
                { duration: '1m', target: 0 },
            ],
            tags: { test_type: 'stress' },
            exec: 'stressTest',
        },

        // Spike test - sudden traffic spike
        spike: {
            executor: 'ramping-vus',
            startVUs: 0,
            stages: [
                { duration: '10s', target: 10 },
                { duration: '10s', target: 1000 }, // Sudden spike
                { duration: '1m', target: 1000 },  // Sustain spike
                { duration: '10s', target: 10 },   // Drop
                { duration: '1m', target: 10 },
                { duration: '10s', target: 0 },
            ],
            tags: { test_type: 'spike' },
            exec: 'spikeTest',
        },
    },

    // Performance thresholds
    thresholds: {
        // HTTP request duration
        'http_req_duration': ['p(95)<500', 'p(99)<1000'], // 95% < 500ms, 99% < 1000ms

        // HTTP request failed
        'http_req_failed': ['rate<0.01'], // Error rate < 1%

        // Custom metrics thresholds
        'tender_view_duration': ['p(95)<300'],
        'search_duration': ['p(95)<500'],
        'rag_query_duration': ['p(95)<2000'],
        'auth_success_rate': ['rate>0.95'],
        'api_error_rate': ['rate<0.05'],
    },
};

// Test data
const searchTerms = [
    'računalniki', 'medicinska oprema', 'storitve čiščenja',
    'pisarniški material', 'avtomobili', 'gradbena dela',
    'IT storitve', 'svetovanje', 'vzdrževanje', 'energija'
];

const ragQueries = [
    'Katere so največje javne naročilnice v zadnjem letu?',
    'Pokaži trende v IT naročilih',
    'Kdo so najpogostejši dobavitelji?',
    'Kakšna je povprečna vrednost naročil za medicino?',
    'Prikaži statistiko po regijah',
];

// Helper functions
function makeRequest(method, url, body = null, params = {}) {
    totalRequests.add(1);

    const options = {
        headers: {
            'Content-Type': 'application/json',
            ...params.headers,
        },
        tags: params.tags || {},
    };

    let response;
    if (method === 'GET') {
        response = http.get(url, options);
    } else if (method === 'POST') {
        response = http.post(url, body ? JSON.stringify(body) : null, options);
    }

    // Track errors
    if (response.status >= 400) {
        apiErrorRate.add(1);
    } else {
        apiErrorRate.add(0);
    }

    return response;
}

function login(email, password) {
    const response = makeRequest('POST', `${API_BASE}/auth/login`, {
        email: email,
        password: password,
    }, { tags: { name: 'login' } });

    const success = check(response, {
        'login status is 200': (r) => r.status === 200,
        'login returns token': (r) => r.json('access_token') !== undefined,
    });

    authSuccessRate.add(success ? 1 : 0);

    if (success) {
        return response.json('access_token');
    }
    return null;
}

// Smoke test scenario
export function smokeTest() {
    group('Smoke Test - Basic Functionality', function () {
        // Homepage
        const homepage = makeRequest('GET', BASE_URL, null, { tags: { name: 'homepage' } });
        check(homepage, {
            'homepage is 200': (r) => r.status === 200,
        });

        sleep(1);

        // API health check
        const health = makeRequest('GET', `${API_BASE}/health`, null, { tags: { name: 'health' } });
        check(health, {
            'health check is 200': (r) => r.status === 200,
        });

        sleep(1);

        // List tenders
        const tenders = makeRequest('GET', `${API_BASE}/tenders?page=1&limit=10`, null, {
            tags: { name: 'tenders_list' }
        });
        check(tenders, {
            'tenders list is 200': (r) => r.status === 200,
            'tenders has items': (r) => r.json('items') !== undefined,
        });
    });
}

// Load test scenario
export function loadTest() {
    activeUsers.add(1);

    group('Browse Tenders', function () {
        // List tenders
        const startTime = new Date();
        const page = randomIntBetween(1, 50);
        const limit = randomItem([10, 20, 50]);

        const response = makeRequest('GET', `${API_BASE}/tenders?page=${page}&limit=${limit}`, null, {
            tags: { name: 'browse_tenders' }
        });

        check(response, {
            'status is 200': (r) => r.status === 200,
            'has items array': (r) => Array.isArray(r.json('items')),
            'has pagination': (r) => r.json('total') !== undefined,
        });

        sleep(randomIntBetween(2, 5));

        // View tender details
        if (response.status === 200) {
            const items = response.json('items');
            if (items && items.length > 0) {
                const tenderId = items[0].id;
                const detailStart = new Date();

                const detailResponse = makeRequest('GET', `${API_BASE}/tenders/${tenderId}`, null, {
                    tags: { name: 'tender_details' }
                });

                const detailDuration = new Date() - detailStart;
                tenderViewDuration.add(detailDuration);

                check(detailResponse, {
                    'detail status is 200': (r) => r.status === 200,
                    'has tender data': (r) => r.json('id') !== undefined,
                });
            }
        }
    });

    sleep(randomIntBetween(3, 8));

    group('Search Tenders', function () {
        const searchStart = new Date();
        const term = randomItem(searchTerms);

        const response = makeRequest('GET', `${API_BASE}/tenders/search?q=${term}&limit=20`, null, {
            tags: { name: 'search' }
        });

        const searchDur = new Date() - searchStart;
        searchDuration.add(searchDur);

        check(response, {
            'search status is 200': (r) => r.status === 200,
            'search has results': (r) => r.json('results') !== undefined || r.json('items') !== undefined,
        });
    });

    activeUsers.add(-1);
    sleep(randomIntBetween(1, 3));
}

// Stress test scenario
export function stressTest() {
    activeUsers.add(1);

    // Rapid fire requests
    group('Stress - Rapid Requests', function () {
        for (let i = 0; i < 5; i++) {
            const page = randomIntBetween(1, 100);
            makeRequest('GET', `${API_BASE}/tenders?page=${page}&limit=20`, null, {
                tags: { name: 'stress_browse' }
            });
            sleep(0.5);
        }
    });

    // Search stress
    group('Stress - Search', function () {
        for (let i = 0; i < 3; i++) {
            const term = randomItem(searchTerms);
            makeRequest('GET', `${API_BASE}/tenders/search?q=${term}`, null, {
                tags: { name: 'stress_search' }
            });
            sleep(0.3);
        }
    });

    // Authenticated operations
    group('Stress - Auth Operations', function () {
        const token = login(`test_user_${randomIntBetween(1, 100)}@example.com`, 'test_password');

        if (token) {
            const ragStart = new Date();
            const query = randomItem(ragQueries);

            const ragResponse = makeRequest('POST', `${API_BASE}/rag/query`,
                { query: query },
                {
                    tags: { name: 'stress_rag' },
                    headers: { 'Authorization': `Bearer ${token}` }
                }
            );

            const ragDur = new Date() - ragStart;
            ragQueryDuration.add(ragDur);

            check(ragResponse, {
                'RAG query status is 200': (r) => r.status === 200,
            });
        }
    });

    activeUsers.add(-1);
    sleep(randomIntBetween(1, 2));
}

// Spike test scenario
export function spikeTest() {
    activeUsers.add(1);

    group('Spike - Mixed Load', function () {
        // Random operation
        const operation = randomIntBetween(1, 4);

        switch (operation) {
            case 1:
                // Browse
                makeRequest('GET', `${API_BASE}/tenders?page=${randomIntBetween(1, 20)}&limit=10`, null, {
                    tags: { name: 'spike_browse' }
                });
                break;

            case 2:
                // Search
                const term = randomItem(searchTerms);
                makeRequest('GET', `${API_BASE}/tenders/search?q=${term}`, null, {
                    tags: { name: 'spike_search' }
                });
                break;

            case 3:
                // Statistics
                makeRequest('GET', `${API_BASE}/statistics`, null, {
                    tags: { name: 'spike_stats' }
                });
                break;

            case 4:
                // Organizations
                makeRequest('GET', `${API_BASE}/organizations?limit=50`, null, {
                    tags: { name: 'spike_orgs' }
                });
                break;
        }
    });

    activeUsers.add(-1);
    sleep(randomIntBetween(0.5, 2));
}

// Default function for simple runs
export default function () {
    loadTest();
}

// Teardown
export function teardown(data) {
    console.log('Load test completed');
    console.log(`Total requests: ${totalRequests.value}`);
}
