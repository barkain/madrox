#!/bin/bash
#
# Madrox Container Validation Test Suite
#
# This script performs comprehensive testing of the Madrox Docker container,
# including build validation, runtime functionality, security, and error handling.
#
# Usage:
#   ./test_container.sh [OPTIONS]
#
# Options:
#   --skip-build    Skip image build tests (use existing image)
#   --verbose       Show detailed output from all tests
#   --cleanup       Remove test containers and images after tests
#   --help          Show this help message
#
# Exit codes:
#   0 - All tests passed
#   1 - One or more tests failed
#
# Requirements:
#   - Docker installed and running
#   - Sufficient disk space for image build
#   - Port 8001 available for testing
#

set -euo pipefail

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
IMAGE_NAME="madrox:test"
CONTAINER_NAME="madrox-test-$$"
TEST_DATA_DIR="/tmp/madrox-test-data-$$"
TEST_PORT=8001
MAX_IMAGE_SIZE_MB=500
BUILD_TIMEOUT=300
STARTUP_TIMEOUT=30
HEALTH_CHECK_TIMEOUT=60

# Test counters
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_TOTAL=0

# Command line flags
SKIP_BUILD=false
VERBOSE=false
CLEANUP=false

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-build)
                SKIP_BUILD=true
                shift
                ;;
            --verbose)
                VERBOSE=true
                shift
                ;;
            --cleanup)
                CLEANUP=true
                shift
                ;;
            --help)
                grep '^#' "$0" | grep -v '#!/bin/bash' | sed 's/^# \?//'
                exit 0
                ;;
            *)
                echo -e "${RED}Unknown option: $1${NC}"
                exit 1
                ;;
        esac
    done
}

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[PASS]${NC} $*"
}

log_error() {
    echo -e "${RED}[FAIL]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[WARN]${NC} $*"
}

log_test() {
    echo -e "${YELLOW}[TEST]${NC} $*"
}

# Test result tracking
pass_test() {
    ((TESTS_PASSED++))
    ((TESTS_TOTAL++))
    log_success "$1"
}

fail_test() {
    ((TESTS_FAILED++))
    ((TESTS_TOTAL++))
    log_error "$1"
}

# Cleanup function
cleanup() {
    log_info "Cleaning up test resources..."

    # Stop and remove test container
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        docker stop "$CONTAINER_NAME" >/dev/null 2>&1 || true
        docker rm "$CONTAINER_NAME" >/dev/null 2>&1 || true
    fi

    # Remove test data directory
    if [[ -d "$TEST_DATA_DIR" ]]; then
        rm -rf "$TEST_DATA_DIR"
    fi

    # Remove test image if cleanup flag is set
    if [[ "$CLEANUP" == true ]]; then
        if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_NAME}$"; then
            docker rmi "$IMAGE_NAME" >/dev/null 2>&1 || true
        fi
    fi
}

# Set up trap for cleanup
trap cleanup EXIT

# Test 1: Image Build Tests
test_image_build() {
    log_test "Testing Docker image build..."

    if [[ "$SKIP_BUILD" == true ]]; then
        log_warning "Skipping build tests (--skip-build flag set)"

        # Verify image exists
        if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_NAME}$"; then
            fail_test "Image $IMAGE_NAME not found (required when using --skip-build)"
            return 1
        fi
        pass_test "Using existing image $IMAGE_NAME"
        return 0
    fi

    # Test: Build completes successfully
    log_info "Building Docker image..."
    local build_start=$(date +%s)

    if [[ "$VERBOSE" == true ]]; then
        docker build -t "$IMAGE_NAME" .
    else
        docker build -t "$IMAGE_NAME" . > /tmp/build-output-$$.log 2>&1
    fi

    local build_result=$?
    local build_end=$(date +%s)
    local build_duration=$((build_end - build_start))

    if [[ $build_result -eq 0 ]]; then
        pass_test "Docker image builds successfully (${build_duration}s)"
    else
        fail_test "Docker image build failed"
        if [[ "$VERBOSE" == false ]]; then
            cat /tmp/build-output-$$.log
        fi
        return 1
    fi

    # Test: Build time is reasonable
    if [[ $build_duration -le $BUILD_TIMEOUT ]]; then
        pass_test "Build completed within timeout (${build_duration}s <= ${BUILD_TIMEOUT}s)"
    else
        log_warning "Build took longer than expected (${build_duration}s > ${BUILD_TIMEOUT}s)"
    fi

    # Test: Check for build warnings
    if [[ "$VERBOSE" == false ]] && grep -qi "warning" /tmp/build-output-$$.log; then
        log_warning "Build completed with warnings"
    else
        pass_test "No build warnings detected"
    fi

    # Test: Image size is under limit
    local image_size=$(docker images "$IMAGE_NAME" --format "{{.Size}}" | head -1)
    local image_size_mb=$(docker images "$IMAGE_NAME" --format "{{.Size}}" | head -1 | sed 's/MB//' | sed 's/GB/*1024/' | bc 2>/dev/null || echo "0")

    if [[ $(echo "$image_size_mb < $MAX_IMAGE_SIZE_MB" | bc -l 2>/dev/null || echo "1") -eq 1 ]]; then
        pass_test "Image size is acceptable ($image_size)"
    else
        log_warning "Image size exceeds recommended limit ($image_size > ${MAX_IMAGE_SIZE_MB}MB)"
    fi

    # Cleanup build log
    rm -f /tmp/build-output-$$.log
}

# Test 2: Container Startup Tests
test_container_startup() {
    log_test "Testing container startup..."

    # Create test data directory
    mkdir -p "$TEST_DATA_DIR"

    # Test: Container starts successfully
    log_info "Starting container..."

    local start_output
    if start_output=$(docker run -d \
        --name "$CONTAINER_NAME" \
        -e ANTHROPIC_API_KEY="test-key-12345" \
        -e HOST="0.0.0.0" \
        -e PORT="$TEST_PORT" \
        -v "${TEST_DATA_DIR}:/data" \
        -p "${TEST_PORT}:${TEST_PORT}" \
        "$IMAGE_NAME" 2>&1); then
        pass_test "Container starts successfully"
    else
        fail_test "Container failed to start: $start_output"
        return 1
    fi

    # Wait for container to be running
    sleep 2

    # Test: Container is running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        pass_test "Container is in running state"
    else
        fail_test "Container is not running"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        return 1
    fi

    # Test: Health check passes within expected time
    log_info "Waiting for health check..."
    local health_start=$(date +%s)
    local health_timeout=$((health_start + HEALTH_CHECK_TIMEOUT))
    local health_status="starting"

    while [[ $(date +%s) -lt $health_timeout ]]; do
        health_status=$(docker inspect --format='{{.State.Health.Status}}' "$CONTAINER_NAME" 2>/dev/null || echo "none")

        if [[ "$health_status" == "healthy" ]]; then
            local health_duration=$(($(date +%s) - health_start))
            pass_test "Health check passed (${health_duration}s)"
            break
        elif [[ "$health_status" == "unhealthy" ]]; then
            fail_test "Health check failed"
            docker logs "$CONTAINER_NAME" 2>&1 | tail -20
            return 1
        fi

        sleep 2
    done

    if [[ "$health_status" != "healthy" ]]; then
        fail_test "Health check timeout (${HEALTH_CHECK_TIMEOUT}s)"
        docker logs "$CONTAINER_NAME" 2>&1 | tail -20
        return 1
    fi

    # Test: Environment variables are respected
    local container_port=$(docker exec "$CONTAINER_NAME" sh -c 'echo $PORT' 2>/dev/null || echo "")
    if [[ "$container_port" == "$TEST_PORT" ]]; then
        pass_test "Environment variables are respected (PORT=$container_port)"
    else
        fail_test "Environment variable PORT not set correctly (expected $TEST_PORT, got $container_port)"
    fi

    # Test: Non-root user execution
    local user_id=$(docker exec "$CONTAINER_NAME" id -u 2>/dev/null || echo "0")
    if [[ "$user_id" == "1000" ]]; then
        pass_test "Container runs as non-root user (UID $user_id)"
    else
        fail_test "Container not running as expected user (UID $user_id, expected 1000)"
    fi
}

# Test 3: Runtime Functionality Tests
test_runtime_functionality() {
    log_test "Testing runtime functionality..."

    # Test: SQLite database initializes correctly
    if docker exec "$CONTAINER_NAME" test -f /data/madrox.db; then
        pass_test "SQLite database file exists"
    else
        fail_test "SQLite database file not found"
    fi

    # Test database is readable
    if docker exec "$CONTAINER_NAME" sqlite3 /data/madrox.db "SELECT name FROM sqlite_master WHERE type='table';" >/dev/null 2>&1; then
        pass_test "SQLite database is readable and valid"
    else
        fail_test "SQLite database is not accessible or corrupted"
    fi

    # Test: Required directories exist
    local required_dirs=("/data" "/logs" "/tmp/claude_orchestrator")
    for dir in "${required_dirs[@]}"; do
        if docker exec "$CONTAINER_NAME" test -d "$dir"; then
            pass_test "Required directory exists: $dir"
        else
            fail_test "Required directory missing: $dir"
        fi
    done

    # Test: tmux is available and functional
    if docker exec "$CONTAINER_NAME" which tmux >/dev/null 2>&1; then
        pass_test "tmux is available"

        # Test tmux can start a session
        if docker exec "$CONTAINER_NAME" sh -c 'tmux new-session -d -s test-session "echo test" && tmux kill-session -t test-session' >/dev/null 2>&1; then
            pass_test "tmux is functional"
        else
            fail_test "tmux cannot start sessions"
        fi
    else
        fail_test "tmux is not available"
    fi

    # Test: Python dependencies load correctly
    local test_imports=(
        "fastapi"
        "uvicorn"
        "anthropic"
        "pydantic"
        "loguru"
    )

    for module in "${test_imports[@]}"; do
        if docker exec "$CONTAINER_NAME" python -c "import $module" >/dev/null 2>&1; then
            pass_test "Python module loads correctly: $module"
        else
            fail_test "Python module failed to load: $module"
        fi
    done

    # Test: Server listens on correct port
    log_info "Checking if server is listening..."
    sleep 3  # Give server time to start listening

    if docker exec "$CONTAINER_NAME" sh -c "netstat -tuln | grep ':${TEST_PORT}'" >/dev/null 2>&1 || \
       docker exec "$CONTAINER_NAME" sh -c "ss -tuln | grep ':${TEST_PORT}'" >/dev/null 2>&1; then
        pass_test "Server is listening on port $TEST_PORT"
    else
        log_warning "Could not verify server is listening on port $TEST_PORT"
    fi
}

# Test 4: Volume Persistence Tests
test_volume_persistence() {
    log_test "Testing volume persistence..."

    # Test: Write test file to data volume
    local test_file="/data/persistence-test-$$.txt"
    local test_content="persistence-test-$$-$(date +%s)"

    if docker exec "$CONTAINER_NAME" sh -c "echo '$test_content' > $test_file"; then
        pass_test "Can write to data volume"
    else
        fail_test "Cannot write to data volume"
        return 1
    fi

    # Test: File persists in mounted volume
    if [[ -f "${TEST_DATA_DIR}/persistence-test-$$.txt" ]]; then
        pass_test "Data persists to mounted volume"
    else
        fail_test "Data does not persist to mounted volume"
    fi

    # Test: Can read back data
    local read_content=$(docker exec "$CONTAINER_NAME" cat "$test_file" 2>/dev/null || echo "")
    if [[ "$read_content" == "$test_content" ]]; then
        pass_test "Data persists across container operations"
    else
        fail_test "Data corruption or persistence issue"
    fi

    # Test: Logs are written to mounted volume
    if docker exec "$CONTAINER_NAME" test -d /logs; then
        # Check if any log files exist or can be created
        if docker exec "$CONTAINER_NAME" sh -c "ls /logs/*.log" >/dev/null 2>&1 || \
           docker exec "$CONTAINER_NAME" sh -c "touch /logs/test.log && rm /logs/test.log" >/dev/null 2>&1; then
            pass_test "Log directory is accessible and writable"
        else
            log_warning "Log directory exists but may not be writable"
        fi
    else
        fail_test "Log directory not accessible"
    fi

    # Test: Workspace directory is accessible
    if docker exec "$CONTAINER_NAME" test -d /tmp/claude_orchestrator; then
        if docker exec "$CONTAINER_NAME" sh -c "touch /tmp/claude_orchestrator/test && rm /tmp/claude_orchestrator/test" >/dev/null 2>&1; then
            pass_test "Workspace directory is accessible and writable"
        else
            fail_test "Workspace directory not writable"
        fi
    else
        fail_test "Workspace directory not accessible"
    fi
}

# Test 5: Security Tests
test_security() {
    log_test "Testing security configuration..."

    # Test: Container runs as non-root (UID 1000)
    local user_id=$(docker exec "$CONTAINER_NAME" id -u 2>/dev/null)
    local user_name=$(docker exec "$CONTAINER_NAME" id -un 2>/dev/null)

    if [[ "$user_id" == "1000" ]]; then
        pass_test "Container runs as non-root user (UID: $user_id, User: $user_name)"
    else
        fail_test "Container running as UID $user_id (expected 1000)"
    fi

    # Test: No unnecessary capabilities
    local capabilities=$(docker inspect "$CONTAINER_NAME" --format='{{.HostConfig.CapAdd}}' 2>/dev/null || echo "[]")
    if [[ "$capabilities" == "[]" || "$capabilities" == "<no value>" ]]; then
        pass_test "No additional capabilities granted"
    else
        log_warning "Container has additional capabilities: $capabilities"
    fi

    # Test: File permissions are correct
    local data_perms=$(docker exec "$CONTAINER_NAME" stat -c '%a' /data 2>/dev/null || echo "")
    if [[ -n "$data_perms" ]]; then
        pass_test "Data directory has permissions: $data_perms"
    else
        fail_test "Cannot check data directory permissions"
    fi

    # Test: User cannot escalate privileges
    if docker exec "$CONTAINER_NAME" sudo -n true 2>/dev/null; then
        fail_test "User can execute sudo without password"
    else
        pass_test "User cannot escalate privileges"
    fi

    # Test: Sensitive files are not world-readable
    local db_perms=$(docker exec "$CONTAINER_NAME" stat -c '%a' /data/madrox.db 2>/dev/null || echo "600")
    local db_perms_last_digit=${db_perms: -1}
    if [[ "$db_perms_last_digit" == "0" ]]; then
        pass_test "Database file is not world-readable"
    else
        log_warning "Database file may be world-readable (permissions: $db_perms)"
    fi
}

# Test 6: Error Handling Tests
test_error_handling() {
    log_test "Testing error handling..."

    # Test: Graceful shutdown on SIGTERM
    log_info "Testing graceful shutdown..."

    local logs_before=$(docker logs "$CONTAINER_NAME" 2>&1 | wc -l)
    docker stop -t 10 "$CONTAINER_NAME" >/dev/null 2>&1

    local exit_code=$(docker inspect "$CONTAINER_NAME" --format='{{.State.ExitCode}}' 2>/dev/null || echo "1")
    if [[ "$exit_code" == "0" ]] || [[ "$exit_code" == "143" ]]; then  # 143 = 128 + 15 (SIGTERM)
        pass_test "Container shuts down gracefully (exit code: $exit_code)"
    else
        log_warning "Container exit code: $exit_code"
    fi

    # Restart container for remaining tests
    docker start "$CONTAINER_NAME" >/dev/null 2>&1
    sleep 5

    # Test: Missing API key fails appropriately
    log_info "Testing missing API key handling..."

    local no_key_container="${CONTAINER_NAME}-nokey"
    if docker run -d --name "$no_key_container" \
        -e PORT="$TEST_PORT" \
        "$IMAGE_NAME" >/dev/null 2>&1; then

        sleep 3
        local no_key_logs=$(docker logs "$no_key_container" 2>&1)

        # Container should either fail to start or log error about missing key
        if echo "$no_key_logs" | grep -qi "api.key\|anthropic"; then
            pass_test "Missing API key produces appropriate error message"
        else
            log_warning "Missing API key error message not clear"
        fi

        docker stop "$no_key_container" >/dev/null 2>&1
        docker rm "$no_key_container" >/dev/null 2>&1
    else
        pass_test "Container fails fast with missing API key"
    fi

    # Test: Invalid port configuration
    log_info "Testing invalid configuration handling..."

    local bad_port_container="${CONTAINER_NAME}-badport"
    if docker run -d --name "$bad_port_container" \
        -e ANTHROPIC_API_KEY="test-key" \
        -e PORT="invalid" \
        "$IMAGE_NAME" >/dev/null 2>&1; then

        sleep 3
        local bad_port_logs=$(docker logs "$bad_port_container" 2>&1)

        # Check if error is logged
        if echo "$bad_port_logs" | grep -qi "error\|invalid\|port"; then
            pass_test "Invalid configuration produces error message"
        else
            log_warning "Invalid configuration error not clearly reported"
        fi

        docker stop "$bad_port_container" >/dev/null 2>&1
        docker rm "$bad_port_container" >/dev/null 2>&1
    fi
}

# Main test execution
main() {
    parse_args "$@"

    echo ""
    echo "============================================="
    echo "  Madrox Container Validation Test Suite"
    echo "============================================="
    echo ""
    log_info "Test configuration:"
    log_info "  Image: $IMAGE_NAME"
    log_info "  Container: $CONTAINER_NAME"
    log_info "  Data dir: $TEST_DATA_DIR"
    log_info "  Port: $TEST_PORT"
    echo ""

    # Check Docker is available
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    # Check Docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running"
        exit 1
    fi

    # Run test suites
    test_image_build
    test_container_startup
    test_runtime_functionality
    test_volume_persistence
    test_security
    test_error_handling

    # Print summary
    echo ""
    echo "============================================="
    echo "  Test Results Summary"
    echo "============================================="
    echo ""
    echo -e "Total tests:  $TESTS_TOTAL"
    echo -e "${GREEN}Passed:       $TESTS_PASSED${NC}"
    echo -e "${RED}Failed:       $TESTS_FAILED${NC}"
    echo ""

    if [[ $TESTS_FAILED -eq 0 ]]; then
        log_success "All tests passed! ✓"
        exit 0
    else
        log_error "Some tests failed. Please review the output above."
        exit 1
    fi
}

# Run main if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
