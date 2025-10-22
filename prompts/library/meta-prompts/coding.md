ROLE: You are a Python expert and software architect specializing in data processing.
OBJECTIVE: Create robust function to validate and transform user registration data for database storage

TECHNICAL CONTEXT:
- Environment: Python 3.11, PostgreSQL backend
- Constraints: GDPR compliance, 100k daily registrations
- Existing code: Uses SQLAlchemy ORM, pydantic for validation

DECOMPOSITION:
1. Analysis: Identify all validation requirements and edge cases
2. Design: Choose validation strategy and error handling approach
3. Implementation: Build function with comprehensive error handling
4. Testing: Create unit tests for happy path and edge cases
5. Documentation: Add docstrings and inline comments for complex logic

CODE REQUIREMENTS:
- Language: Python 3.11 with type hints
- Style: PEP 8, black formatter compatible
- Comments: Explain any non-obvious logic
- Error handling: Specific exceptions for each validation failure
- Testing: pytest-compatible unit tests

OUTPUT FORMAT:
- Complete function with imports
- Unit tests in separate block
- Example usage with sample data
- Performance considerations noted

VALIDATION:
- Function handles all specified edge cases
- Tests achieve 100% code coverage
- No security vulnerabilities (SQL injection, etc.)

STOP CONDITIONS: Complete when function is production-ready with tests passing.