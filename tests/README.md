# Tests for AI Investing App

This directory contains unit tests for the application.

## Running Tests

```bash
# Install test dependencies
pip install pytest pytest-cov

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

## Test Structure
- `test_option_analyst.py` - PCR/GEX calculation tests
- `test_market_data.py` - Data fetching and error handling tests
- `test_portfolio_storage.py` - Save/load functionality tests
