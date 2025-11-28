#!/bin/bash
#
# Avatar Looks System Test Runner
# ================================
# Runs the comprehensive test suite for the avatar looks generation system.
#
# Usage:
#   ./tests/run_tests.sh              # Run all tests in dry-run mode
#   ./tests/run_tests.sh --live       # Run with live API calls (requires credentials)
#   ./tests/run_tests.sh --unit       # Run only unit tests
#   ./tests/run_tests.sh --integration # Run only integration tests
#   ./tests/run_tests.sh --quick      # Run quick validation tests only
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default settings
DRY_RUN="true"
TEST_FILTER=""
VERBOSE=""
COVERAGE=""
QUICK_MODE=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --live)
            DRY_RUN="false"
            shift
            ;;
        --unit)
            TEST_FILTER="-k 'Test' and not 'Integration'"
            shift
            ;;
        --integration)
            TEST_FILTER="-k 'Integration'"
            shift
            ;;
        --quick)
            QUICK_MODE="true"
            TEST_FILTER="-k 'test_all_10_looks or test_detect or test_get_avatar'"
            shift
            ;;
        -v|--verbose)
            VERBOSE="-vv"
            shift
            ;;
        --coverage)
            COVERAGE="--cov=social_media --cov-report=html"
            shift
            ;;
        -h|--help)
            echo "Avatar Looks System Test Runner"
            echo ""
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --live          Run with live API calls (requires credentials)"
            echo "  --unit          Run only unit tests"
            echo "  --integration   Run only integration tests"
            echo "  --quick         Run quick validation tests only"
            echo "  -v, --verbose   Verbose output"
            echo "  --coverage      Generate coverage report"
            echo "  -h, --help      Show this help message"
            echo ""
            echo "Environment Variables:"
            echo "  TEST_DRY_RUN          Set to 'false' for live testing"
            echo "  TEST_VERBOSE          Set to 'true' for verbose output"
            echo "  HEYGEN_API_KEY        Required for live API tests"
            echo "  SUPABASE_URL          Required for database tests"
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Print header
echo ""
echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}   Avatar Looks System - Test Suite Runner${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""

# Check Python environment
echo -e "${YELLOW}Checking environment...${NC}"

cd "$PROJECT_ROOT"

# Check if virtual environment exists
if [[ -d "venv" ]]; then
    echo "  Found virtual environment"
    source venv/bin/activate 2>/dev/null || true
elif [[ -d ".venv" ]]; then
    echo "  Found .venv environment"
    source .venv/bin/activate 2>/dev/null || true
fi

# Verify Python
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}Error: Python 3 is required but not found${NC}"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "  Python: $PYTHON_VERSION"

# Check pytest
if ! python3 -c "import pytest" 2>/dev/null; then
    echo -e "${YELLOW}Installing pytest...${NC}"
    pip install pytest pytest-cov 2>/dev/null || {
        echo -e "${RED}Error: Failed to install pytest${NC}"
        exit 1
    }
fi

PYTEST_VERSION=$(python3 -c "import pytest; print(pytest.__version__)")
echo "  Pytest: $PYTEST_VERSION"

# Set environment variables
export TEST_DRY_RUN="$DRY_RUN"
export PYTHONPATH="$PROJECT_ROOT:$PYTHONPATH"

# Check credentials for live mode
if [[ "$DRY_RUN" == "false" ]]; then
    echo ""
    echo -e "${YELLOW}Live mode enabled - checking credentials...${NC}"

    if [[ -z "$HEYGEN_API_KEY" ]]; then
        echo -e "${RED}Error: HEYGEN_API_KEY is required for live testing${NC}"
        exit 1
    fi
    echo "  HEYGEN_API_KEY: Set"

    if [[ -z "$HEYGEN_PHOTO_AVATAR_GROUP_ID" ]]; then
        echo -e "${RED}Error: HEYGEN_PHOTO_AVATAR_GROUP_ID is required for live testing${NC}"
        exit 1
    fi
    echo "  HEYGEN_PHOTO_AVATAR_GROUP_ID: Set"

    if [[ -z "$SUPABASE_URL" ]]; then
        echo -e "${YELLOW}Warning: SUPABASE_URL not set - database tests will be skipped${NC}"
    else
        echo "  SUPABASE_URL: Set"
    fi
else
    echo ""
    echo -e "${GREEN}Dry-run mode - using mocked API responses${NC}"
fi

# Run tests
echo ""
echo -e "${BLUE}Running tests...${NC}"
echo -e "${BLUE}----------------------------------------------------------------${NC}"
echo ""

# Build pytest command
PYTEST_CMD="python3 -m pytest tests/test_avatar_looks_system.py"

if [[ -n "$VERBOSE" ]]; then
    PYTEST_CMD="$PYTEST_CMD $VERBOSE"
else
    PYTEST_CMD="$PYTEST_CMD -v"
fi

if [[ -n "$TEST_FILTER" ]]; then
    PYTEST_CMD="$PYTEST_CMD $TEST_FILTER"
fi

if [[ -n "$COVERAGE" ]]; then
    PYTEST_CMD="$PYTEST_CMD $COVERAGE"
fi

# Add common options
PYTEST_CMD="$PYTEST_CMD --tb=short -x"

if [[ "$DRY_RUN" == "false" ]]; then
    PYTEST_CMD="$PYTEST_CMD --live"
fi

echo "Command: $PYTEST_CMD"
echo ""

# Run the tests
START_TIME=$(date +%s)

if eval "$PYTEST_CMD"; then
    TEST_RESULT="PASSED"
    RESULT_COLOR="$GREEN"
else
    TEST_RESULT="FAILED"
    RESULT_COLOR="$RED"
fi

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Print summary
echo ""
echo -e "${BLUE}================================================================${NC}"
echo -e "${BLUE}   Test Results Summary${NC}"
echo -e "${BLUE}================================================================${NC}"
echo ""
echo -e "  Status:    ${RESULT_COLOR}${TEST_RESULT}${NC}"
echo -e "  Duration:  ${DURATION} seconds"
echo -e "  Mode:      $([ "$DRY_RUN" == "true" ] && echo "Dry-run" || echo "Live")"
echo ""

if [[ "$TEST_RESULT" == "PASSED" ]]; then
    echo -e "${GREEN}All tests passed! Ready for deployment.${NC}"
    echo ""

    if [[ "$DRY_RUN" == "true" ]]; then
        echo -e "${YELLOW}Note: Tests ran in dry-run mode. For full validation before${NC}"
        echo -e "${YELLOW}production deployment, run with --live flag:${NC}"
        echo ""
        echo -e "  ${BLUE}./tests/run_tests.sh --live${NC}"
    fi
else
    echo -e "${RED}Some tests failed. Please fix the issues before deploying.${NC}"
fi

echo ""
echo -e "${BLUE}================================================================${NC}"
echo ""

exit $([[ "$TEST_RESULT" == "PASSED" ]] && echo 0 || echo 1)
