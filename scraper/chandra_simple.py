#!/usr/bin/env python3
"""
Simple Chandra OCR test - synchronous, minimal.
"""
import os
import subprocess
from pathlib import Path

# Test with the CLI first to confirm it works
def test_chandra_cli():
    test_pdf = "/tmp/test_macedonian.pdf"
    output_dir = "/tmp/chandra_simple_test"

    if not Path(test_pdf).exists():
        print(f"Test PDF not found: {test_pdf}")
        return

    Path(output_dir).mkdir(exist_ok=True)

    print("Running Chandra CLI...")
    result = subprocess.run(
        ['chandra', test_pdf, output_dir, '--method', 'hf', '--page-range', '1', '--batch-size', '1'],
        capture_output=True,
        text=True,
        timeout=300
    )

    print(f"Return code: {result.returncode}")
    print(f"Stdout: {result.stdout[:500] if result.stdout else 'None'}")
    print(f"Stderr: {result.stderr[:500] if result.stderr else 'None'}")

    # Check output
    md_files = list(Path(output_dir).glob('**/*.md'))
    if md_files:
        text = md_files[0].read_text()
        print(f"\nExtracted {len(text)} chars:")
        print(text[:1000])
    else:
        print("No markdown output found")

if __name__ == '__main__':
    test_chandra_cli()
