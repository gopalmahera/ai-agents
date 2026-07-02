import os
import unittest

# Enable legacy Flask webhook routes for unit tests only.
os.environ["ENABLE_FLASK_WEBHOOKS"] = "1"
