#!/usr/bin/env python3
"""
Pytest Configuration for Browser Agent Tests

This file contains pytest hooks and fixtures shared across all test files.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def pytest_addoption(parser):
    """Add custom pytest options for integration and LLM tests."""
    # Integration test options
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run integration tests that call the model"
    )
    parser.addoption(
        "--integration-timeout",
        action="store",
        default=120,
        type=int,
        help="Timeout in seconds for each integration test"
    )
    parser.addoption(
        "--test-server-port",
        action="store",
        default=8765,
        type=int,
        help="Port for the test page server"
    )
    
    # LLM test options
    parser.addoption(
        "--run-llm-tests",
        action="store_true",
        default=False,
        help="Run LLM-based integration tests"
    )
    parser.addoption(
        "--llm-endpoint",
        action="store",
        default="http://localhost:1234/v1",
        help="LLM API endpoint (default: LM Studio at localhost:1234)"
    )
    parser.addoption(
        "--llm-model",
        action="store",
        default="local-model",
        help="LLM model name to use"
    )
    parser.addoption(
        "--success-threshold",
        action="store",
        default=70.0,
        type=float,
        help="Minimum success rate threshold (0-100) for tests to pass"
    )
    parser.addoption(
        "--llm-timeout",
        action="store",
        default=300,
        type=int,
        help="Timeout in seconds for LLM-based tests"
    )


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires --run-integration)"
    )
    config.addinivalue_line(
        "markers", "llm: mark test as LLM-based test (requires --run-llm-tests)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


# Store config values for access in test files
class PytestConfig:
    """Global pytest configuration values."""
    run_integration = False
    run_llm_tests = False
    llm_endpoint = "http://localhost:1234/v1"
    llm_model = "local-model"
    success_threshold = 70.0
    integration_timeout = 120
    llm_timeout = 300
    test_server_port = 8765


@pytest.fixture(scope="session", autouse=True)
def setup_pytest_config(request):
    """Set up global pytest configuration."""
    PytestConfig.run_integration = request.config.getoption("--run-integration")
    PytestConfig.run_llm_tests = request.config.getoption("--run-llm-tests")
    PytestConfig.llm_endpoint = request.config.getoption("--llm-endpoint")
    PytestConfig.llm_model = request.config.getoption("--llm-model")
    PytestConfig.success_threshold = request.config.getoption("--success-threshold")
    PytestConfig.integration_timeout = request.config.getoption("--integration-timeout")
    PytestConfig.llm_timeout = request.config.getoption("--llm-timeout")
    PytestConfig.test_server_port = request.config.getoption("--test-server-port")
    return PytestConfig


# Make config accessible via pytest.config
pytest.config = PytestConfig()
