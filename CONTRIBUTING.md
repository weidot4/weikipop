# Contributing to weikipop

Thanks for contributing.

## Development setup

1. Install Python 3.10+
2. Install dependencies:
   - `pip install -r requirements.txt`
3. Run the app:
   - `python -m src.main`

## Pull request guidelines

- Keep changes focused and minimal.
- Preserve existing behavior unless the PR explicitly changes behavior.
- Include a short rationale in the PR description.
- Update documentation when user-facing behavior changes.

## Code quality checklist

Before submitting:

- `python -m compileall src`
- Manually verify core flow:
  - tray icon starts
  - OCR provider loads
  - popup renders lookup results

## Commit messages

Use clear, imperative messages such as:

- `Improve OCR provider error handling`
- `Refactor queue module naming`
- `Update README setup instructions`

## Reporting bugs

Please include:

- OS and Python version
- OCR provider in use
- Steps to reproduce
- Expected vs actual behavior
- Relevant logs/screenshots
