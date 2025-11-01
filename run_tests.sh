#!/bin/bash
# Comprehensive test runner script

set -e

echo "=============================================="
echo "DATATHON 2025 - TEST RUNNER"
echo "=============================================="
echo ""

# Check if environment is activated
if [ -z "$CONDA_DEFAULT_ENV" ] || [ "$CONDA_DEFAULT_ENV" = "base" ]; then
    echo "[WARN] Conda environment not activated"
    echo "[INFO] Activating datathon-local..."
    eval "$(conda shell.bash hook)"
    conda activate datathon-local 2>/dev/null || {
        echo "[ERROR] Could not activate environment"
        echo "[INFO] Please run: conda env create -f environment-local.yml"
        exit 1
    }
fi

echo "[INFO] Environment: $CONDA_DEFAULT_ENV"
echo ""

# Parse arguments
RUN_MANUAL=false
RUN_UNIT=false
RUN_COVERAGE=false
RUN_ALL=false

if [ $# -eq 0 ]; then
    RUN_ALL=true
else
    for arg in "$@"; do
        case $arg in
            --manual)
                RUN_MANUAL=true
                ;;
            --unit)
                RUN_UNIT=true
                ;;
            --coverage)
                RUN_COVERAGE=true
                ;;
            --all)
                RUN_ALL=true
                ;;
            --help)
                echo "Usage: ./run_tests.sh [OPTIONS]"
                echo ""
                echo "Options:"
                echo "  --manual      Run manual tests (no pytest)"
                echo "  --unit        Run unit tests with pytest"
                echo "  --coverage    Run tests with coverage report"
                echo "  --all         Run all tests (default)"
                echo "  --help        Show this help"
                exit 0
                ;;
            *)
                echo "[ERROR] Unknown option: $arg"
                echo "Run './run_tests.sh --help' for usage"
                exit 1
                ;;
        esac
    done
fi

# If --all is set, run everything
if [ "$RUN_ALL" = true ]; then
    RUN_MANUAL=true
    RUN_UNIT=true
fi

# Run manual tests
if [ "$RUN_MANUAL" = true ]; then
    echo "=============================================="
    echo "MANUAL TESTS (No pytest required)"
    echo "=============================================="
    echo ""
    
    echo "[INFO] Running manual parser tests..."
    python test_parsers_manual.py
    
    echo ""
fi

# Run unit tests
if [ "$RUN_UNIT" = true ]; then
    echo "=============================================="
    echo "UNIT TESTS (pytest)"
    echo "=============================================="
    echo ""
    
    # Check if pytest is available
    if ! command -v pytest &> /dev/null; then
        echo "[ERROR] pytest not found"
        echo "[INFO] Installing pytest..."
        conda install -y pytest pytest-cov
    fi
    
    echo "[INFO] Running unit tests..."
    pytest tests/unit/ -v --tb=short
    
    echo ""
fi

# Run coverage tests
if [ "$RUN_COVERAGE" = true ]; then
    echo "=============================================="
    echo "COVERAGE REPORT"
    echo "=============================================="
    echo ""
    
    echo "[INFO] Running tests with coverage..."
    pytest tests/unit/ --cov=src --cov-report=term-missing --cov-report=html
    
    echo ""
    echo "[INFO] HTML coverage report generated: htmlcov/index.html"
    echo ""
fi

echo "=============================================="
echo "TEST SUMMARY"
echo "=============================================="
echo ""

if [ "$RUN_MANUAL" = true ]; then
    echo "[OK] Manual tests completed"
fi

if [ "$RUN_UNIT" = true ]; then
    echo "[OK] Unit tests completed"
fi

if [ "$RUN_COVERAGE" = true ]; then
    echo "[OK] Coverage report generated"
fi

echo ""
echo "All tests completed successfully!"
echo ""

