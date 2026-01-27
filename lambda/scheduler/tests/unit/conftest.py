"""
Unit tests configuration for algorithm tests.

Sets up sys.path to allow importing scheduler modules and shared modules.
"""

import sys
from pathlib import Path


# Add scheduler lambda directory to path
scheduler_dir = Path(__file__).parent.parent.parent
if str(scheduler_dir) not in sys.path:
    sys.path.insert(0, str(scheduler_dir))

# Add lambda parent directory to path (for shared module)
lambda_parent_dir = scheduler_dir.parent
if str(lambda_parent_dir) not in sys.path:
    sys.path.insert(0, str(lambda_parent_dir))
