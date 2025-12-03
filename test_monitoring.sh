#!/bin/bash
# Quick test script for production monitoring features

set -e

echo "🧪 Testing Production Monitoring Features"
echo "=========================================="
echo ""

# Check if backend is running
if ! curl -s http://localhost:8001/health > /dev/null 2>&1; then
    echo "❌ Backend not running on port 8001"
    echo "   Start it with: cd backend && uvicorn main:app --host 0.0.0.0 --port 8001"
    exit 1
fi

echo "✅ Backend is running"
echo ""

# Test 1: Basic health check
echo "1️⃣  Testing basic health check..."
RESPONSE=$(curl -s http://localhost:8001/health)
if echo "$RESPONSE" | grep -q "healthy"; then
    echo "   ✅ Health check passed"
else
    echo "   ❌ Health check failed"
fi
echo ""

# Test 2: Prometheus metrics endpoint
echo "2️⃣  Testing Prometheus metrics..."
METRICS=$(curl -s http://localhost:8001/metrics)
if echo "$METRICS" | grep -q "http_requests_total"; then
    echo "   ✅ Metrics endpoint working"
    echo "   Sample metrics:"
    echo "$METRICS" | grep "http_requests_total" | head -3 | sed 's/^/      /'
else
    echo "   ❌ Metrics endpoint failed"
fi
echo ""

# Test 3: Rate limiting (auth endpoint - 10/minute)
echo "3️⃣  Testing rate limiting (auth endpoint: 10/min)..."
SUCCESS_COUNT=0
RATE_LIMITED=false

for i in {1..12}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X POST http://localhost:8001/auth/login \
        -H "Content-Type: application/json" \
        -d '{"email":"test@test.com","password":"test"}')
    
    if [ "$HTTP_CODE" = "429" ]; then
        RATE_LIMITED=true
        echo "   ✅ Rate limit triggered after $SUCCESS_COUNT requests"
        break
    else
        SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
    fi
done

if [ "$RATE_LIMITED" = false ]; then
    echo "   ⚠️  Rate limit not triggered (might be set too high or disabled)"
fi
echo ""

# Test 4: CORS headers
echo "4️⃣  Testing CORS configuration..."
CORS_HEADER=$(curl -s -I http://localhost:8001/health | grep -i "access-control-allow-origin" || echo "")
if [ -n "$CORS_HEADER" ]; then
    echo "   ✅ CORS headers present"
    echo "      $CORS_HEADER" | tr -d '\r'
else
    echo "   ❌ CORS headers missing"
fi
echo ""

# Test 5: Check for structured logging (if backend logs to stdout)
echo "5️⃣  Logging check..."
echo "   ℹ️  Logs should be in JSON format with fields:"
echo "      - timestamp, level, logger, message"
echo "      - correlation_id (for request tracing)"
echo "      Check backend terminal output for JSON logs"
echo ""

# Test 6: Performance test
echo "6️⃣  Quick performance test (10 concurrent requests)..."
START=$(date +%s%N)
for i in {1..10}; do
    curl -s http://localhost:8001/health > /dev/null &
done
wait
END=$(date +%s%N)
DURATION=$((($END - $START) / 1000000)) # Convert to ms

echo "   ✅ 10 requests completed in ${DURATION}ms"
if [ $DURATION -lt 1000 ]; then
    echo "      Performance: EXCELLENT (< 1s)"
elif [ $DURATION -lt 2000 ]; then
    echo "      Performance: GOOD (< 2s)"
else
    echo "      Performance: NEEDS IMPROVEMENT (> 2s)"
fi
echo ""

# Summary
echo "=========================================="
echo "✅ All basic tests completed!"
echo ""
echo "Next steps:"
echo "  1. Check backend logs for JSON formatted output"
echo "  2. View metrics: curl http://localhost:8001/metrics"
echo "  3. Run load test: locust -f backend/tests/load_test.py --host=http://localhost:8001"
echo "  4. Set CORS_ORIGINS env var to production domains"
echo "  5. Configure Prometheus + Grafana for production monitoring"
echo ""
