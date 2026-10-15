# Contributing to AdminBot

Thank you for considering contributing to AdminBot.

## Development setup

Follow the [README.md](README.md) quick start guide to get the project running locally.

## Code style

- Follow [PEP 8](https://peps.python.org/pep-0008/) for Python code
- Use meaningful variable and function names
- Add docstrings to functions and classes
- Keep functions small and focused on one task
- Write tests for new features and bug fixes

## Running tests

```bash
python manage.py test
```

Tests must pass before submitting changes.

## Commit messages

Write clear, concise commit messages in the imperative mood:

- ✓ "Add health check endpoint"
- ✓ "Fix database connection error handling"
- ✗ "Added some stuff"
- ✗ "Fixed bug"

## Submitting changes

1. Create a new branch for your feature or fix
2. Make your changes
3. Run tests and ensure they pass
4. Commit your changes with clear messages
5. Push to your branch
6. Open a pull request

## Security

Never commit secrets, API keys, or passwords. Use environment variables for sensitive configuration.

If you discover a security vulnerability, please report it privately before opening a public issue.

## Questions

If you have questions about contributing, open an issue with the "question" label.
