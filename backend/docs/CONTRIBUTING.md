# Contributing to nabavkidata.com

> Thank you for your interest in contributing to nabavkidata.com!

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [How Can I Contribute?](#how-can-i-contribute)
- [Getting Started](#getting-started)
- [Development Process](#development-process)
- [Pull Request Process](#pull-request-process)
- [Code Review Guidelines](#code-review-guidelines)
- [Issue Guidelines](#issue-guidelines)
- [Community Guidelines](#community-guidelines)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inspiring community for all. Please be respectful and constructive in all interactions.

### Expected Behavior

- Use welcoming and inclusive language
- Be respectful of differing viewpoints and experiences
- Gracefully accept constructive criticism
- Focus on what is best for the community
- Show empathy towards other community members

### Unacceptable Behavior

- Trolling, insulting/derogatory comments, and personal attacks
- Public or private harassment
- Publishing others' private information without permission
- Other conduct which could reasonably be considered inappropriate

### Enforcement

Violations of the Code of Conduct may be reported to support@nabavkidata.com. All complaints will be reviewed and investigated promptly.

## How Can I Contribute?

### Reporting Bugs

Before creating a bug report, please check existing issues to avoid duplicates.

**Bug Report Template:**

```markdown
**Description**
A clear and concise description of the bug.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '...'
3. Scroll down to '...'
4. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Screenshots**
If applicable, add screenshots.

**Environment**
- OS: [e.g., macOS 14.1]
- Browser: [e.g., Chrome 120]
- Version: [e.g., 1.0.0]

**Additional Context**
Any other relevant information.
```

### Suggesting Enhancements

Enhancement suggestions are tracked as GitHub issues.

**Enhancement Request Template:**

```markdown
**Is your feature request related to a problem?**
A clear description of the problem. Ex. I'm frustrated when [...]

**Describe the solution you'd like**
A clear description of what you want to happen.

**Describe alternatives you've considered**
Alternative solutions or features you've considered.

**Additional Context**
Any other context, mockups, or examples.
```

### Contributing Code

We welcome code contributions! Please follow the development process outlined below.

## Getting Started

### Prerequisites

Before contributing, ensure you have:

1. Read the [Development Guide](DEVELOPMENT.md)
2. Set up your local development environment
3. Familiarized yourself with the codebase

### First Contribution

Looking for a place to start? Check out issues labeled:

- `good first issue` - Simple issues suitable for beginners
- `help wanted` - Issues where we need community help
- `documentation` - Documentation improvements

### Development Setup

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/nabavkidata.git
cd nabavkidata

# 3. Add upstream remote
git remote add upstream https://github.com/nabavkidata/nabavkidata.git

# 4. Create a branch
git checkout -b feature/my-feature

# 5. Set up development environment
# See DEVELOPMENT.md for detailed instructions
```

## Development Process

### 1. Choose or Create an Issue

- Check existing issues for something you want to work on
- Comment on the issue to let others know you're working on it
- If no issue exists, create one first to discuss the change

### 2. Create a Branch

Branch naming conventions:

- `feature/description` - New features
- `bugfix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code refactoring
- `test/description` - Test improvements

```bash
git checkout develop
git pull upstream develop
git checkout -b feature/add-tender-export
```

### 3. Make Changes

Follow the [Code Style Guide](DEVELOPMENT.md#code-style-guide):

**Python:**
- PEP 8 compliant
- Type hints for function signatures
- Docstrings for all public functions/classes
- Maximum line length: 100 characters

**TypeScript/JavaScript:**
- ESLint and Prettier compliant
- Functional components with hooks (React)
- TypeScript for type safety

**Commit Messages:**
- Use Conventional Commits format
- Write clear, descriptive commit messages
- Reference issue numbers

Example:
```bash
git commit -m "feat(tenders): add CSV export functionality

Implement CSV export for tender search results. Includes
pagination support and custom field selection.

Closes #123"
```

### 4. Test Your Changes

**Backend:**
```bash
cd backend
pytest
pytest --cov=. --cov-report=html
```

**Frontend:**
```bash
cd frontend
npm run lint
npm run type-check
npm run build
```

**Integration:**
```bash
# Test the full stack
docker-compose up -d
# Manual testing
```

### 5. Update Documentation

- Update README.md if adding features
- Update API.md for API changes
- Add JSDoc/docstrings for new code
- Update CHANGELOG.md (maintainers will do this)

## Pull Request Process

### Before Submitting

Checklist before creating a PR:

- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Comments added for complex logic
- [ ] Documentation updated
- [ ] Tests added/updated
- [ ] All tests pass
- [ ] No linting errors
- [ ] Commits are clean and well-described
- [ ] Branch is up to date with develop

### Submitting a Pull Request

1. **Push Your Branch**

```bash
git push origin feature/my-feature
```

2. **Create Pull Request on GitHub**

Use this template:

```markdown
## Description
Brief description of changes.

## Related Issue
Closes #123

## Type of Change
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## How Has This Been Tested?
Describe the tests you ran and how to reproduce them.

## Screenshots (if applicable)
Add screenshots for UI changes.

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review performed
- [ ] Commented complex code
- [ ] Documentation updated
- [ ] No new warnings generated
- [ ] Tests added that prove fix/feature works
- [ ] New and existing tests pass locally
- [ ] Dependent changes merged
```

3. **Request Review**

- Assign relevant reviewers
- Add appropriate labels
- Link related issues
- Be responsive to feedback

### During Review

- Be open to feedback and suggestions
- Make requested changes promptly
- Push additional commits to the same branch
- Respond to review comments
- Mark conversations as resolved when addressed

### After Approval

- Maintainers will merge your PR
- Your branch will be deleted automatically
- Update your local repository:

```bash
git checkout develop
git pull upstream develop
git branch -d feature/my-feature
```

## Code Review Guidelines

### For Contributors

**Responding to Feedback:**
- Don't take criticism personally
- Ask for clarification if needed
- Explain your reasoning when disagreeing
- Be willing to compromise
- Learn from the review process

### For Reviewers

**When Reviewing:**
- Be constructive and respectful
- Explain the "why" behind suggestions
- Distinguish between "must fix" and "nice to have"
- Approve when quality standards are met
- Be timely in reviews (within 48 hours)

**Review Checklist:**
- [ ] Code logic is correct
- [ ] Code is readable and maintainable
- [ ] Follows project conventions
- [ ] Tests are adequate
- [ ] Documentation is clear
- [ ] No security issues
- [ ] Performance considerations addressed
- [ ] Error handling is robust

## Issue Guidelines

### Creating Issues

**Title:**
- Clear and descriptive
- Include component/area in brackets
- Examples:
  - `[Backend] API endpoint returns 500 on invalid input`
  - `[Frontend] Tender card not responsive on mobile`
  - `[Docs] Missing API authentication examples`

**Description:**
- Provide context and background
- Include steps to reproduce (for bugs)
- Specify expected vs actual behavior
- Add relevant logs, screenshots, or code snippets
- Tag with appropriate labels

### Issue Labels

| Label | Description |
|-------|-------------|
| `bug` | Something isn't working |
| `enhancement` | New feature or request |
| `documentation` | Documentation improvements |
| `good first issue` | Good for newcomers |
| `help wanted` | Community help needed |
| `question` | Further information requested |
| `wontfix` | Will not be worked on |
| `duplicate` | Already reported |
| `priority: high` | High priority issue |
| `priority: low` | Low priority issue |

### Issue Lifecycle

1. **Triage**: Maintainers review and label
2. **Discussion**: Community discusses approach
3. **Assignment**: Contributor assigned or self-assigns
4. **Development**: Work in progress
5. **Review**: Pull request under review
6. **Resolved**: Merged and closed

## Community Guidelines

### Communication Channels

- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: General questions, ideas
- **Discord**: Real-time chat (link in README)
- **Email**: support@nabavkidata.com

### Recognition

Contributors are recognized in:
- README.md contributors section
- Release notes
- GitHub contributor graph

### Licensing

By contributing, you agree that your contributions will be licensed under the MIT License.

### Attribution

Significant contributions will be attributed in:
- Commit history (Git)
- Release notes
- Contributors list

## Getting Help

### Resources

- [Development Guide](DEVELOPMENT.md) - Setup and development
- [Architecture Docs](ARCHITECTURE.md) - System design
- [API Docs](API.md) - API reference
- [FAQ](FAQ.md) - Common questions

### Ask Questions

Don't hesitate to ask questions:
- Open a GitHub Discussion
- Ask in Discord
- Email dev@nabavkidata.com

### Mentorship

New contributors can request mentorship:
- Comment on a "good first issue"
- Ask in Discord #contributors channel
- Email dev@nabavkidata.com with "Mentorship Request"

## Additional Notes

### Financial Contributions

We do not currently accept financial contributions. The best way to support the project is through code, documentation, and community engagement.

### Intellectual Property

- Do not include proprietary or copyrighted code
- Ensure you have rights to contribute
- Add appropriate license headers
- Respect third-party licenses

### Security Issues

**Do not** create public issues for security vulnerabilities.

Instead:
1. Email security@nabavkidata.com
2. Include detailed description
3. Provide steps to reproduce
4. We will respond within 48 hours

## Thank You!

Your contributions make nabavkidata.com better for everyone. We appreciate your time and effort!

---

**Contributing Guide Version**: 1.0
**Last Updated**: 2025-01-22
**Questions**: dev@nabavkidata.com
