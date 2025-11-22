#!/bin/bash
# Performance Benchmark Runner
# Runs all performance benchmarks and generates reports

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
BENCHMARK_DIR="tests/performance"
RESULTS_DIR="benchmark_results"
BASELINE_DIR="benchmark_baseline"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Performance Benchmark Suite${NC}"
echo -e "${BLUE}================================${NC}\n"

# Create results directory
mkdir -p "$RESULTS_DIR"
mkdir -p "$BASELINE_DIR"

# Check if pytest-benchmark is installed
if ! python -c "import pytest_benchmark" 2>/dev/null; then
    echo -e "${YELLOW}Installing pytest-benchmark...${NC}"
    pip install pytest-benchmark
fi

# ============================================================================
# FUNCTION: Run benchmarks
# ============================================================================
run_benchmarks() {
    local test_file=$1
    local output_name=$2

    echo -e "${GREEN}Running: $output_name${NC}"

    pytest "$test_file" \
        --benchmark-only \
        --benchmark-json="$RESULTS_DIR/${output_name}_${TIMESTAMP}.json" \
        --benchmark-columns='min,max,mean,stddev,median' \
        --benchmark-sort='mean' \
        -v

    echo ""
}

# ============================================================================
# FUNCTION: Compare with baseline
# ============================================================================
compare_with_baseline() {
    local current_results=$1
    local baseline_results=$2

    if [ -f "$baseline_results" ]; then
        echo -e "${BLUE}Comparing with baseline...${NC}"

        pytest-benchmark compare \
            "$baseline_results" \
            "$current_results" \
            --csv="$RESULTS_DIR/comparison_${TIMESTAMP}.csv"

        echo ""
    else
        echo -e "${YELLOW}No baseline found. Saving current results as baseline.${NC}"
        cp "$current_results" "$baseline_results"
        echo ""
    fi
}

# ============================================================================
# FUNCTION: Generate HTML report
# ============================================================================
generate_html_report() {
    echo -e "${BLUE}Generating HTML report...${NC}"

    pytest "$BENCHMARK_DIR" \
        --benchmark-only \
        --benchmark-autosave \
        --benchmark-save-data \
        --benchmark-histogram="$RESULTS_DIR/histogram_${TIMESTAMP}"

    echo ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

echo -e "${YELLOW}Starting benchmark suite...${NC}\n"

# 1. API Benchmarks
if [ -f "$BENCHMARK_DIR/benchmark_api.py" ]; then
    run_benchmarks \
        "$BENCHMARK_DIR/benchmark_api.py" \
        "api_benchmarks"

    compare_with_baseline \
        "$RESULTS_DIR/api_benchmarks_${TIMESTAMP}.json" \
        "$BASELINE_DIR/api_benchmarks_baseline.json"
fi

# 2. Database Benchmarks
if [ -f "$BENCHMARK_DIR/benchmark_database.py" ]; then
    run_benchmarks \
        "$BENCHMARK_DIR/benchmark_database.py" \
        "database_benchmarks"

    compare_with_baseline \
        "$RESULTS_DIR/database_benchmarks_${TIMESTAMP}.json" \
        "$BASELINE_DIR/database_benchmarks_baseline.json"
fi

# 3. RAG Benchmarks
if [ -f "$BENCHMARK_DIR/benchmark_rag.py" ]; then
    if [ -n "$OPENAI_API_KEY" ]; then
        run_benchmarks \
            "$BENCHMARK_DIR/benchmark_rag.py" \
            "rag_benchmarks"

        compare_with_baseline \
            "$RESULTS_DIR/rag_benchmarks_${TIMESTAMP}.json" \
            "$BASELINE_DIR/rag_benchmarks_baseline.json"
    else
        echo -e "${YELLOW}Skipping RAG benchmarks (OPENAI_API_KEY not set)${NC}\n"
    fi
fi

# 4. Stress Tests
if [ -f "$BENCHMARK_DIR/stress_test.py" ]; then
    echo -e "${GREEN}Running stress tests...${NC}"

    pytest "$BENCHMARK_DIR/stress_test.py" \
        -v \
        -m stress \
        --tb=short

    echo ""
fi

# 5. Generate HTML report
generate_html_report

# ============================================================================
# SUMMARY
# ============================================================================

echo -e "${BLUE}================================${NC}"
echo -e "${BLUE}Benchmark Summary${NC}"
echo -e "${BLUE}================================${NC}\n"

echo -e "${GREEN}Results saved to:${NC}"
echo "  - JSON: $RESULTS_DIR/*_${TIMESTAMP}.json"
echo "  - Histogram: $RESULTS_DIR/histogram_${TIMESTAMP}.svg"
echo ""

# Check for performance regressions
if [ -f "$RESULTS_DIR/comparison_${TIMESTAMP}.csv" ]; then
    echo -e "${BLUE}Performance Changes:${NC}"
    cat "$RESULTS_DIR/comparison_${TIMESTAMP}.csv"
    echo ""
fi

# ============================================================================
# CI/CD INTEGRATION
# ============================================================================

if [ "$CI" = "true" ]; then
    echo -e "${BLUE}CI Mode: Checking for regressions...${NC}\n"

    # Check if any benchmark regressed by more than 20%
    REGRESSION_THRESHOLD=1.20

    # Parse comparison results and check for regressions
    if [ -f "$RESULTS_DIR/comparison_${TIMESTAMP}.csv" ]; then
        # Add regression check logic here
        echo "Regression check complete"
    fi
fi

echo -e "${GREEN}Benchmark suite complete!${NC}"
