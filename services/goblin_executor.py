"""
Real Goblin Task Execution Service

Integrates with GoblinOS automation system to execute real tasks.
"""

import os
import sys
import subprocess
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
import tempfile


class GoblinExecutor:
    """Executes tasks using the GoblinOS system"""

    def __init__(self):
        # Path to GoblinOS directory
        self.goblin_os_path = (
            Path(__file__).parent.parent.parent.parent.parent / "GoblinOS"
        )
        self.goblin_cli = self.goblin_os_path / "goblin-cli.sh"
        self.goblins_yaml = self.goblin_os_path / "goblins.yaml"

        # Validate GoblinOS setup
        if not self.goblin_os_path.exists():
            raise FileNotFoundError(
                f"GoblinOS directory not found at {self.goblin_os_path}"
            )
        if not self.goblin_cli.exists():
            raise FileNotFoundError(f"goblin-cli.sh not found at {self.goblin_cli}")

    async def list_available_goblins(self) -> Dict[str, Any]:
        """List all available goblins from goblins.yaml"""
        try:
            result = await self._run_command(
                ["bash", str(self.goblin_cli), "list"], timeout=10
            )
            return {
                "success": True,
                "goblins": self._parse_goblin_list(result["stdout"]),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _parse_goblin_list(self, output: str) -> list:
        """Parse goblin list output"""
        # Expected format from goblin-cli.sh list command
        goblins = []
        for line in output.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("Available"):
                # Parse format: "goblin-id - Description"
                if " - " in line:
                    goblin_id, description = line.split(" - ", 1)
                    goblins.append(
                        {"id": goblin_id.strip(), "description": description.strip()}
                    )
        return goblins

    async def execute_goblin(
        self,
        goblin_id: str,
        task_description: str,
        code: Optional[str] = None,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute a goblin task

        Args:
            goblin_id: The goblin tool ID to execute
            task_description: Human-readable description of the task
            code: Optional code to execute (for code-based goblins)
            dry_run: If True, simulate execution without making changes

        Returns:
            Dict with execution results
        """
        try:
            # Prepare command
            cmd = ["bash", str(self.goblin_cli), "run"]

            if dry_run:
                cmd.append("--dry")

            cmd.append(goblin_id)

            # Execute command
            start_time = datetime.utcnow()
            result = await self._run_command(cmd, timeout=300)  # 5 minute timeout
            end_time = datetime.utcnow()

            execution_time = (end_time - start_time).total_seconds()

            return {
                "success": result["returncode"] == 0,
                "goblin_id": goblin_id,
                "task_description": task_description,
                "stdout": result["stdout"],
                "stderr": result["stderr"],
                "returncode": result["returncode"],
                "execution_time_seconds": execution_time,
                "dry_run": dry_run,
                "timestamp": start_time.isoformat(),
            }

        except asyncio.TimeoutError:
            return {
                "success": False,
                "goblin_id": goblin_id,
                "error": "Task execution timeout (exceeded 5 minutes)",
                "task_description": task_description,
            }
        except Exception as e:
            return {
                "success": False,
                "goblin_id": goblin_id,
                "error": str(e),
                "task_description": task_description,
            }

    async def execute_custom_script(
        self, script_content: str, working_dir: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a custom bash script

        Args:
            script_content: The bash script content to execute
            working_dir: Optional working directory

        Returns:
            Dict with execution results
        """
        try:
            # Create temporary script file
            with tempfile.NamedTemporaryFile(mode="w", suffix=".sh", delete=False) as f:
                f.write("#!/bin/bash\n")
                f.write("set -e\n")  # Exit on error
                f.write(script_content)
                script_path = f.name

            # Make executable
            os.chmod(script_path, 0o755)

            try:
                # Execute script
                start_time = datetime.utcnow()
                result = await self._run_command(
                    ["bash", script_path], timeout=300, cwd=working_dir
                )
                end_time = datetime.utcnow()

                execution_time = (end_time - start_time).total_seconds()

                return {
                    "success": result["returncode"] == 0,
                    "stdout": result["stdout"],
                    "stderr": result["stderr"],
                    "returncode": result["returncode"],
                    "execution_time_seconds": execution_time,
                    "timestamp": start_time.isoformat(),
                }
            finally:
                # Clean up temp file
                try:
                    os.unlink(script_path)
                except:
                    pass

        except Exception as e:
            return {"success": False, "error": str(e)}

    async def _run_command(
        self, cmd: list, timeout: int = 60, cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Run a shell command asynchronously

        Args:
            cmd: Command and arguments as list
            timeout: Timeout in seconds
            cwd: Working directory

        Returns:
            Dict with stdout, stderr, and returncode
        """
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd or str(self.goblin_os_path),
        )

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=timeout
            )

            return {
                "stdout": stdout.decode("utf-8", errors="replace"),
                "stderr": stderr.decode("utf-8", errors="replace"),
                "returncode": process.returncode,
            }
        except asyncio.TimeoutError:
            # Kill the process if it times out
            process.kill()
            await process.wait()
            raise

    async def validate_goblin(self, goblin_id: str) -> Dict[str, Any]:
        """
        Validate that a goblin exists and can be executed

        Args:
            goblin_id: The goblin tool ID to validate

        Returns:
            Dict with validation result
        """
        goblins_result = await self.list_available_goblins()

        if not goblins_result["success"]:
            return {"valid": False, "error": "Failed to list goblins"}

        goblin_ids = [g["id"] for g in goblins_result["goblins"]]

        if goblin_id in goblin_ids:
            return {"valid": True, "goblin_id": goblin_id}
        else:
            return {
                "valid": False,
                "error": f"Goblin '{goblin_id}' not found",
                "available_goblins": goblin_ids,
            }


# Singleton instance
_executor: Optional[GoblinExecutor] = None


def get_goblin_executor() -> GoblinExecutor:
    """Get or create singleton GoblinExecutor instance"""
    global _executor
    if _executor is None:
        _executor = GoblinExecutor()
    return _executor
