#!/usr/bin/env python3
"""
Continuous Iteration Monitor for Azure Tenant Grapher

This script continuously monitors the iteration process, generating new iterations,
validating them, analyzing errors, and spawning parallel workstreams to fix issues.

It runs until the objective is achieved (100% fidelity) or until manually stopped.
"""
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Project root
PROJECT_ROOT = Path(__file__).parent.parent
DEMOS_DIR = PROJECT_ROOT / "demos"
STATUS_FILE = PROJECT_ROOT / "demos" / "continuous_iteration_status.json"


class IterationMonitor:
    """Monitor and control the continuous iteration process."""
    
    def __init__(self):
        self.iteration_num = self._get_next_iteration()
        self.status = self._load_status()
        self.start_time = datetime.now()
        
    def _get_next_iteration(self) -> int:
        """Get the next iteration number."""
        existing = list(DEMOS_DIR.glob("iteration*"))
        if not existing:
            return 1
        numbers = []
        for path in existing:
            try:
                num = int(path.name.replace("iteration", ""))
                numbers.append(num)
            except ValueError:
                continue
        return max(numbers) + 1 if numbers else 1
    
    def _load_status(self) -> Dict:
        """Load iteration status from disk."""
        if STATUS_FILE.exists():
            with open(STATUS_FILE) as f:
                return json.load(f)
        return {
            "iterations": [],
            "total_errors_fixed": 0,
            "validation_passes": 0,
            "current_phase": "initialization"
        }
    
    def _save_status(self):
        """Save iteration status to disk."""
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, 'w') as f:
            json.dump(self.status, f, indent=2)
    
    def _send_imessage(self, message: str):
        """Send iMessage status update."""
        try:
            subprocess.run(
                [os.path.expanduser("~/.local/bin/imessR"), message],
                capture_output=True,
                timeout=10
            )
        except Exception as e:
            logger.warning(f"Failed to send iMessage: {e}")
    
    def generate_iteration(self) -> Tuple[bool, Path, str]:
        """
        Generate a new iteration.
        
        Returns:
            (success, path, message)
        """
        iteration_dir = DEMOS_DIR / f"iteration{self.iteration_num}"
        
        logger.info(f"Generating iteration {self.iteration_num}...")
        
        cmd = [
            "uv", "run", "atg", "generate-iac",
            "--resource-filters", "resourceGroup=~'(?i).*(simuland|SimuLand).*'",
            "--resource-group-prefix", f"ITERATION{self.iteration_num}_",
            "--skip-name-validation",
            "--output", str(iteration_dir)
        ]
        
        try:
            result = subprocess.run(
                cmd,
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode == 0:
                logger.info(f"✅ Iteration {self.iteration_num} generated successfully")
                return True, iteration_dir, "Generation successful"
            else:
                error = result.stderr[-500:] if result.stderr else "Unknown error"
                logger.error(f"❌ Iteration {self.iteration_num} generation failed: {error}")
                return False, iteration_dir, error
        
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Iteration {self.iteration_num} generation timed out")
            return False, iteration_dir, "Generation timeout"
        except Exception as e:
            logger.error(f"❌ Iteration {self.iteration_num} generation error: {e}")
            return False, iteration_dir, str(e)
    
    def validate_iteration(self, iteration_dir: Path) -> Tuple[bool, int, List[str]]:
        """
        Validate an iteration using terraform validate.
        
        Returns:
            (is_valid, error_count, error_messages)
        """
        logger.info(f"Validating {iteration_dir.name}...")
        
        # Run terraform validate
        try:
            result = subprocess.run(
                ["terraform", "validate"],
                cwd=iteration_dir,
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode == 0:
                logger.info(f"✅ {iteration_dir.name} validation PASSED")
                return True, 0, []
            
            # Parse errors
            errors = []
            for line in result.stderr.split('\n'):
                if 'Error:' in line:
                    errors.append(line.strip())
            
            error_count = len(errors)
            logger.warning(f"❌ {iteration_dir.name} has {error_count} validation errors")
            return False, error_count, errors
        
        except subprocess.TimeoutExpired:
            logger.error(f"❌ {iteration_dir.name} validation timed out")
            return False, -1, ["Validation timeout"]
        except Exception as e:
            logger.error(f"❌ {iteration_dir.name} validation error: {e}")
            return False, -1, [str(e)]
    
    def analyze_errors(self, errors: List[str]) -> Dict[str, List[str]]:
        """
        Analyze validation errors and categorize them.
        
        Returns:
            Dictionary mapping error categories to error messages
        """
        categories = {
            "missing_required_argument": [],
            "undeclared_resource": [],
            "extraneous_property": [],
            "insufficient_blocks": [],
            "other": []
        }
        
        for error in errors:
            if "Missing required argument" in error:
                categories["missing_required_argument"].append(error)
            elif "undeclared resource" in error:
                categories["undeclared_resource"].append(error)
            elif "Extraneous" in error:
                categories["extraneous_property"].append(error)
            elif "Insufficient" in error:
                categories["insufficient_blocks"].append(error)
            else:
                categories["other"].append(error)
        
        return categories
    
    def run_iteration_cycle(self):
        """Run one complete iteration cycle."""
        # Generate iteration
        success, iteration_dir, message = self.generate_iteration()
        
        if not success:
            self._send_imessage(f"❌ ITER {self.iteration_num} generation failed: {message}")
            self.status["iterations"].append({
                "number": self.iteration_num,
                "timestamp": datetime.now().isoformat(),
                "status": "generation_failed",
                "message": message
            })
            self._save_status()
            return False
        
        # Validate iteration
        is_valid, error_count, errors = self.validate_iteration(iteration_dir)
        
        # Record iteration
        iteration_record = {
            "number": self.iteration_num,
            "timestamp": datetime.now().isoformat(),
            "status": "valid" if is_valid else "invalid",
            "error_count": error_count,
            "errors": errors[:10]  # Save first 10 errors
        }
        
        self.status["iterations"].append(iteration_record)
        
        if is_valid:
            self.status["validation_passes"] += 1
            self.status["current_phase"] = "deployment_ready"
            self._save_status()
            
            self._send_imessage(
                f"🎉 ITER {self.iteration_num} VALIDATION PASSED! "
                f"Ready for deployment. {self.status['validation_passes']} successful iterations."
            )
            return True
        
        # Analyze errors
        error_categories = self.analyze_errors(errors)
        
        # Update status
        self.status["current_phase"] = "fixing_errors"
        self._save_status()
        
        # Send status update
        self._send_imessage(
            f"🔄 ITER {self.iteration_num}: {error_count} errors. "
            f"Analyzing: {len(error_categories['missing_required_argument'])} missing args, "
            f"{len(error_categories['undeclared_resource'])} undeclared refs"
        )
        
        logger.info(f"Error categories: {json.dumps({k: len(v) for k, v in error_categories.items()}, indent=2)}")
        
        return False
    
    def run_continuous_loop(self, max_iterations: int = 1000):
        """
        Run continuous iteration loop until objective achieved or max iterations reached.
        
        Args:
            max_iterations: Maximum number of iterations to run
        """
        logger.info(f"Starting continuous iteration loop (max {max_iterations} iterations)")
        self._send_imessage(f"🚀 Starting continuous iteration from ITER {self.iteration_num}")
        
        consecutive_passes = 0
        required_consecutive_passes = 3  # Need 3 consecutive passes to confirm stability
        
        while self.iteration_num <= max_iterations:
            logger.info(f"\n{'='*60}")
            logger.info(f"ITERATION {self.iteration_num} - {datetime.now().strftime('%H:%M:%S')}")
            logger.info(f"{'='*60}")
            
            success = self.run_iteration_cycle()
            
            if success:
                consecutive_passes += 1
                if consecutive_passes >= required_consecutive_passes:
                    elapsed = (datetime.now() - self.start_time).total_seconds() / 60
                    self._send_imessage(
                        f"✅ OBJECTIVE ACHIEVED! {required_consecutive_passes} consecutive validation passes. "
                        f"Total iterations: {self.iteration_num}. Time: {elapsed:.1f} min"
                    )
                    logger.info("🎉 OBJECTIVE ACHIEVED - 100% validation success!")
                    return
            else:
                consecutive_passes = 0  # Reset on failure
            
            self.iteration_num += 1
            
            # Brief delay between iterations
            time.sleep(5)
        
        logger.warning(f"Reached max iterations ({max_iterations})")
        self._send_imessage(f"⚠️ Reached max iterations {max_iterations}")


def main():
    """Main entry point."""
    monitor = IterationMonitor()
    
    try:
        monitor.run_continuous_loop()
    except KeyboardInterrupt:
        logger.info("\n🛑 Stopped by user")
        monitor._send_imessage(f"🛑 Continuous iteration stopped at ITER {monitor.iteration_num}")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        monitor._send_imessage(f"💥 Fatal error at ITER {monitor.iteration_num}: {str(e)[:100]}")
        sys.exit(1)


if __name__ == "__main__":
    main()
