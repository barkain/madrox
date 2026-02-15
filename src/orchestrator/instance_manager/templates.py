"""Team template MCP tools and helpers."""

import asyncio
import logging
from typing import Any

from ._mcp import mcp

logger = logging.getLogger(__name__)


class TemplateMixin:
    """MCP tools for spawning teams from templates."""

    # Declared by InstanceManager; present here for type checking only
    instances: dict[str, dict[str, Any]]
    spawn_instance: Any
    _build_tree_recursive: Any

    @mcp.tool
    async def spawn_team_from_template(
        self,
        template_name: str,
        task_description: str,
        supervisor_role: str | None = None,
        parent_instance_id: str | None = None,
    ) -> str:
        """Spawn a complete team from a predefined template.

        Available templates:
        - software_engineering_team: Build SaaS apps, APIs, microservices (6 instances, 2-4 hrs)
        - research_analysis_team: Market research, competitive intelligence (5 instances, 2-3 hrs)
        - security_audit_team: Security reviews, compliance assessments (7 instances, 2-4 hrs)
        - data_pipeline_team: ETL pipelines, data lake ingestion (5 instances, 2-4 hrs)

        Args:
            template_name: Name of the template to use
            task_description: Description of the task for the team
            supervisor_role: Optional supervisor role (defaults to template's recommended role)
            parent_instance_id: Optional parent instance ID for supervisor

        Returns:
            Formatted result text with supervisor ID and network topology
        """
        from pathlib import Path
        from re import fullmatch

        if not fullmatch(r"[a-zA-Z0-9_-]+", template_name):
            raise ValueError(f"Invalid template name: {template_name}")

        project_root = Path(__file__).parent.parent.parent.parent
        template_path = (project_root / "templates" / f"{template_name}.md").resolve()

        # Prevent path traversal outside templates directory
        templates_dir = (project_root / "templates").resolve()
        if not template_path.is_relative_to(templates_dir):
            raise ValueError(f"Invalid template name: {template_name}")

        if not template_path.exists():
            raise ValueError(
                f"Template not found: {template_name}\n"
                f"Available templates: software_engineering_team, research_analysis_team, "
                f"security_audit_team, data_pipeline_team"
            )

        template_content = template_path.read_text()

        template_meta = self._parse_template_metadata(template_content)

        role = supervisor_role or template_meta["supervisor_role"]

        instruction = self._build_template_instruction(
            template_content=template_content, task_description=task_description
        )

        supervisor_id = await self.spawn_instance(
            name=f"{template_name}-lead",
            role=role,
            wait_for_ready=True,
            initial_prompt=instruction,
            parent_instance_id=parent_instance_id,
        )

        logger.info(
            f"Spawned supervisor {supervisor_id} with initial instruction "
            f"({len(instruction)} chars, {len(instruction) / 1024:.2f}KB)"
        )

        await asyncio.sleep(10)

        tree_preview = "Initializing network..."
        try:
            roots = []
            for instance_id, instance in self.instances.items():
                if not instance.get("parent_instance_id") and instance.get("state") != "terminated":
                    roots.append((instance_id, instance.get("name", "unknown")))

            if roots:  # noqa: E501
                roots.sort(key=lambda x: x[1])
                lines: list[str] = []
                for i, (root_id, _) in enumerate(roots):
                    is_last_root = i == len(roots) - 1
                    self._build_tree_recursive(root_id, "", is_last_root, lines, is_root=True)
                tree_preview = "\n".join(lines)
        except Exception as e:
            logger.warning(f"Failed to build tree preview: {e}")

        result_text = f"""✅ Team spawned from template: {template_name}

📋 **Template Details:**
- Supervisor ID: {supervisor_id}
- Team Size: {template_meta["team_size"]} instances
- Estimated Duration: {template_meta["duration"]}
- Estimated Cost: {template_meta["estimated_cost"]}
- Status: Initializing

🌳 **Network Topology:**
{tree_preview}

📝 **Task:**
{task_description[:200]}{"..." if len(task_description) > 200 else ""}

⏳ The supervisor is now spawning the team and executing the workflow.
Use get_pending_replies({supervisor_id}) to monitor progress.
Use get_instance_tree() to see the full network hierarchy."""

        return result_text

    def _parse_template_metadata(self, template_content: str) -> dict[str, Any]:
        """Extract metadata from template markdown."""
        lines = template_content.split("\n")

        team_size = 6
        for line in lines:
            if "Team Size" in line and "instances" in line:
                try:
                    parts = line.split("instances")[0].split()
                    team_size = int(parts[-1])
                except (ValueError, IndexError):
                    pass

        duration = "2-4 hours"
        for line in lines:
            if "Estimated Duration" in line or "Duration:" in line:
                if ":" in line:
                    duration = line.split(":", 1)[-1].strip()

        supervisor_role = "general"
        in_supervisor_section = False
        for line in lines:
            if any(
                header in line
                for header in [
                    "### Technical Lead",
                    "### Research Lead",
                    "### Security Lead",
                    "### Data Engineering Lead",
                ]
            ):
                in_supervisor_section = True
            elif line.startswith("###"):
                in_supervisor_section = False

            if in_supervisor_section and "**Role**:" in line:
                if "`" in line:
                    supervisor_role = line.split("`")[1]
                    break

        return {
            "team_size": team_size,
            "duration": duration,
            "estimated_cost": f"${team_size * 5}",
            "supervisor_role": supervisor_role,
        }

    def _extract_section(self, content: str, header: str) -> str:
        """Extract markdown section by header."""
        lines = content.split("\n")
        section_lines = []
        in_section = False

        for line in lines:
            if line.strip().startswith(header):
                in_section = True
                continue
            if in_section and line.startswith("## ") and line.strip() != header:
                break
            if in_section:
                section_lines.append(line)

        return "\n".join(section_lines).strip()

    def _build_template_instruction(self, template_content: str, task_description: str) -> str:
        """Build instruction message for supervisor from template."""
        team_structure = self._extract_section(template_content, "## Team Structure")
        workflow_phases = self._extract_section(template_content, "## Workflow Phases")
        communication = self._extract_section(template_content, "## Communication Protocols")

        instruction = f"""Execute the team workflow from this template:

TASK DESCRIPTION:
{task_description}

TEAM STRUCTURE TO SPAWN:
{team_structure[:500]}... [See full template for details]

WORKFLOW PHASES TO EXECUTE:
{workflow_phases[:800]}... [See full template for details]

COMMUNICATION PROTOCOLS TO USE:
{communication[:400]}... [See full template for details]

CRITICAL EXECUTION INSTRUCTIONS:
1. Spawn your team members with parent_instance_id set to YOUR instance_id
2. Use broadcast_to_children for team-wide announcements
3. Use send_to_instance for 1-on-1 coordination
4. Workers MUST use reply_to_caller to report back to you
5. Poll get_pending_replies every 5-15 minutes to collect worker responses
6. Follow the workflow phases sequentially as outlined in the template
7. Report final deliverables and status when complete

Begin execution now. Spawn your team and start the workflow."""

        return instruction
