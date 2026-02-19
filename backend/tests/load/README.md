# Load Testing Suite

Comprehensive load testing suite for the Nabavki Data Platform using multiple load testing tools.

## Overview

This suite provides load testing capabilities using three popular tools:
- **Locust** - Python-based, scriptable load testing
- **K6** - Modern JavaScript-based load testing with powerful scripting
- **Artillery** - YAML-based configuration with ease of use

## Directory Structure

```
tests/load/
├── locustfile.py          # Main Locust load testing file
├── k6-script.js           # K6 load testing script
├── artillery.yml          # Artillery configuration
├── scenarios/             # Modular scenario files
│   ├── browse_tenders.py
│   ├── search_tenders.py
│   ├── auth_flow.py
│   ├── rag_queries.py
│   └── admin_operations.py
└── README.md             # This file
```

## Prerequisites

Install the required tools:

```bash
# Locust (Python)
pip install locust

# K6 (macOS)
brew install k6

# Artillery (Node.js)
npm install -g artillery
```

## Test Scenarios

### 1. Browse Tenders
Simulates users browsing tender listings with pagination and filtering.
- Homepage browsing
- Pagination navigation
- View tender details
- Apply filters (status, value, date)
- Sort results

### 2. Search Tenders
Tests search functionality with various queries and filters.
- Simple keyword search
- Advanced search with multiple filters
- Autocomplete/suggestions
- Search result pagination
- Organization-based search

### 3. Authentication Flow
Tests user authentication and profile management.
- User registration
- Login/logout
- Token refresh
- Profile updates
- Password changes
- Favorites management

### 4. RAG Chat Queries
Tests the RAG (Retrieval-Augmented Generation) system.
- General analytics queries
- Follow-up questions
- Context-based queries
- Conversation history
- Response ratings

### 5. Admin Operations
Tests administrative functions.
- Data synchronization
- Cache management
- User management
- Report generation
- System monitoring
- Audit logs

## Running Load Tests

### Locust

#### Smoke Test (Minimal Load)
```bash
locust -f locustfile.py \
  --host http://localhost:8000 \
  --users 10 \
  --spawn-rate 2 \
  --run-time 2m \
  --tags smoke \
  --headless
```

#### Load Test (Average Load)
```bash
locust -f locustfile.py \
  --host http://localhost:8000 \
  --users 100 \
  --spawn-rate 10 \
  --run-time 10m \
  --tags load \
  --headless
```

#### Stress Test (High Load)
```bash
locust -f locustfile.py \
  --host http://localhost:8000 \
  --users 500 \
  --spawn-rate 50 \
  --run-time 15m \
  --tags stress \
  --headless
```

#### Spike Test (Sudden Traffic Spike)
```bash
locust -f locustfile.py \
  --host http://localhost:8000 \
  --users 1000 \
  --spawn-rate 100 \
  --run-time 5m \
  --tags spike \
  --headless
```

#### Web UI Mode
```bash
locust -f locustfile.py --host http://localhost:8000
# Open browser to http://localhost:8089
```

### K6

#### Smoke Test
```bash
k6 run --vus 1 --duration 1m k6-script.js
```

#### Load Test
```bash
BASE_URL=http://localhost:8000 k6 run k6-script.js
```

#### Stress Test
```bash
k6 run --vus 500 --duration 15m k6-script.js
```

#### With Custom Thresholds
```bash
k6 run \
  --vus 100 \
  --duration 10m \
  --threshold http_req_duration=p95<500 \
  --threshold http_req_failed=rate<0.01 \
  k6-script.js
```

#### Output to InfluxDB
```bash
k6 run --out influxdb=http://localhost:8086/k6 k6-script.js
```

### Artillery

#### Quick Test
```bash
artillery quick --count 10 --num 100 http://localhost:8000
```

#### Run Full Suite
```bash
artillery run artillery.yml
```

#### With Custom Target
```bash
artillery run --target http://production.nabavki.si artillery.yml
```

#### Generate Report
```bash
artillery run --output report.json artillery.yml
artillery report report.json
```

## Performance Targets

### Response Time Targets
- **p50 (median)**: < 200ms
- **p95**: < 500ms
- **p99**: < 1000ms
- **Maximum**: < 2000ms

### Throughput Targets
- **Minimum**: 100 req/s
- **Target**: 500 req/s
- **Peak**: 1000 req/s

### Error Rate Targets
- **Maximum**: 1%
- **Target**: 0.1%

### Concurrent Users
- **Normal Load**: 100 users
- **Peak Load**: 500 users
- **Stress Test**: 1000 users

## Interpreting Results

### Locust Metrics
- **RPS (Requests Per Second)**: Total throughput
- **Response Time**: p50, p95, p99 percentiles
- **Failure Rate**: Percentage of failed requests
- **Active Users**: Number of concurrent users

### K6 Metrics
- **http_req_duration**: Request duration statistics
- **http_req_failed**: Failed request rate
- **http_reqs**: Total requests per second
- **vus**: Virtual users
- **iteration_duration**: Full iteration time

### Artillery Metrics
- **Response time**: min, max, median, p95, p99
- **Scenarios**: Completed scenarios
- **Request rate**: Requests per second
- **Errors**: Error count and types

## Tools Comparison

| Feature | Locust | K6 | Artillery |
|---------|--------|-------|-----------|
| Language | Python | JavaScript | YAML/JS |
| UI | Web UI | CLI/Web | CLI |
| Scripting | Full Python | JavaScript | Limited |
| Learning Curve | Medium | Medium | Easy |
| Scenarios | Custom classes | Scenarios | Phases |
| Metrics | Basic | Advanced | Good |
| Distributed | Yes | Yes | Limited |
| Best For | Custom logic | Performance | Quick tests |

## Best Practices

### 1. Start Small
Always start with smoke tests before running full load tests.

### 2. Gradual Ramp-Up
Increase load gradually to identify breaking points.

### 3. Monitor Resources
Monitor server resources (CPU, memory, disk) during tests.

### 4. Test Realistic Scenarios
Use realistic user behaviors and think times.

### 5. Test During Off-Peak
Run major load tests during off-peak hours.

### 6. Document Results
Keep records of test results for comparison.

### 7. Set Baselines
Establish baseline performance metrics.

### 8. Test Regularly
Include load tests in CI/CD pipeline.

## Troubleshooting

### High Error Rates
- Check server logs
- Verify database connections
- Check resource limits
- Review error types

### Slow Response Times
- Check database query performance
- Review cache hit rates
- Check network latency
- Profile slow endpoints

### Connection Errors
- Increase connection pool size
- Check firewall settings
- Verify DNS resolution
- Check load balancer config

## Integration with Monitoring

### Prometheus + Grafana
```bash
# K6 with Prometheus Remote Write
k6 run --out experimental-prometheus-rw k6-script.js
```

### InfluxDB + Grafana
```bash
# K6 with InfluxDB
k6 run --out influxdb=http://localhost:8086/k6 k6-script.js
```

### Cloud Monitoring
```bash
# Locust with statsD
locust --master --expect-workers=4 --statsd-host=localhost --statsd-port=8125
```

## CI/CD Integration

### GitHub Actions Example
```yaml
name: Load Test
on:
  schedule:
    - cron: '0 2 * * *'  # Daily at 2 AM

jobs:
  load-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Run K6 Load Test
        uses: k6io/action@v0.1
        with:
          filename: tests/load/k6-script.js
```

## Resources

- [Locust Documentation](https://docs.locust.io/)
- [K6 Documentation](https://k6.io/docs/)
- [Artillery Documentation](https://www.artillery.io/docs)
- [Load Testing Best Practices](https://k6.io/docs/testing-guides/load-testing/)

## Support

For issues or questions:
- Review server logs: `docker-compose logs -f backend`
- Check metrics: http://localhost:3000 (Grafana)
- Review traces: http://localhost:16686 (Jaeger)
