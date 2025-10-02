# System Prompts for Madrox Instance Roles

This directory contains the system prompts for each predefined role in Madrox. These prompts define the expertise, behavior, and capabilities of instances spawned with specific roles.

## How It Works

When you spawn an instance with a predefined role:

```python
instance = await manager.spawn_instance(
    name="backend-dev",
    role="backend_developer"
)
```

Madrox loads the corresponding prompt from `backend_developer.txt` and uses it to initialize the instance with specialized knowledge and behavior.

## Available Roles

| Role | File | Specialization |
|------|------|----------------|
| **General** | `general.txt` | Versatile AI assistant for broad tasks |
| **Frontend Developer** | `frontend_developer.txt` | React, TypeScript, modern web development |
| **Backend Developer** | `backend_developer.txt` | Python, APIs, distributed systems |
| **Architect** | `architect.txt` | System design, scalability, technical decisions |
| **Code Reviewer** | `code_reviewer.txt` | Code quality, best practices, constructive feedback |
| **Testing Specialist** | `testing_specialist.txt` | Test automation, QA, quality assurance |
| **Security Analyst** | `security_analyst.txt` | Application security, vulnerability assessment |
| **Debugger** | `debugger.txt` | Problem diagnosis, root cause analysis |
| **Documentation Writer** | `documentation_writer.txt` | Technical documentation, API docs, tutorials |
| **Data Analyst** | `data_analyst.txt` | Data processing, statistical analysis, visualization |

## Customizing Prompts

### Method 1: Edit Existing Prompts

Simply edit the `.txt` files in this directory. Changes take effect immediately for newly spawned instances.

```bash
# Edit the backend developer prompt
vim resources/prompts/backend_developer.txt
```

### Method 2: Create New Roles

1. Create a new prompt file (e.g., `ml_engineer.txt`)
2. Add the role to the `InstanceRole` enum in `src/orchestrator/models.py` and `simple_models.py`
3. Restart the Madrox server

Example new role:

```txt
# resources/prompts/ml_engineer.txt

You are a machine learning engineer with expertise in:
- PyTorch and TensorFlow
- Model training and optimization
- MLOps and deployment
...
```

### Method 3: Use Custom System Prompts

Override roles entirely with custom prompts when spawning:

```python
instance = await manager.spawn_instance(
    name="custom-expert",
    role="general",  # Base role (ignored when system_prompt provided)
    system_prompt="""You are a Rust systems programmer with expertise in:
    - Low-level memory management
    - Concurrency and async runtime
    - WebAssembly compilation
    ..."""
)
```

## Prompt Design Principles

Based on research into effective system prompts, these prompts follow key principles:

### 1. Specificity
✅ **Good**: "You are a senior frontend developer specializing in React 18+, TypeScript 5.0, and server components"
❌ **Bad**: "You are a frontend developer"

### 2. Detailed Expertise
Each prompt includes:
- **Core Technologies**: Specific tools and frameworks
- **Best Practices**: Industry standards and patterns
- **Behavioral Guidelines**: How to approach tasks
- **Code Style**: Formatting and conventions

### 3. Actionable Guidance
Prompts describe **how** to perform tasks, not just **what** expertise exists:
- "When reviewing code, explain the reasoning behind suggestions"
- "Prioritize security by validating all inputs"
- "Write tests before refactoring"

### 4. Examples and Patterns
Many prompts include code examples showing preferred patterns

### 5. Context Awareness
Prompts guide the AI to:
- Ask clarifying questions
- Consider trade-offs
- Explain reasoning
- Provide alternatives

## Prompt Structure

Most prompts follow this structure:

```markdown
# Introduction (Who You Are)
Brief role definition with experience level

## Technical Expertise
### Core Technologies
- Specific tools, frameworks, languages

### Specialized Knowledge
- Domain-specific expertise

## Best Practices You Follow
1. Category 1 (e.g., Performance)
   - Specific practices
   - Concrete examples

2. Category 2 (e.g., Security)
   - Guidelines
   - Dos and don'ts

## Your Approach
- How you think about problems
- Decision-making process
- Communication style

## Behavioral Guidelines
- When providing solutions...
- When reviewing code...
- When explaining concepts...
```

## Maintenance

### Updating Prompts
- Test changes with sample instances before production
- Keep prompts focused on role expertise
- Update based on new best practices and tools
- Document significant changes

### Version Control
All prompt files are tracked in git. To revert changes:

```bash
git checkout main resources/prompts/backend_developer.txt
```

### Fallback Behavior
If a prompt file is missing or unreadable:
1. Warning logged to orchestrator logs
2. Fallback to basic hardcoded prompt
3. Instance still spawns successfully

## Testing Prompts

Test a modified prompt:

```python
# Spawn instance with the role
test_instance = await manager.spawn_instance(
    name="test-role",
    role="backend_developer"
)

# Send a typical task
await manager.send_to_instance(
    test_instance,
    "Design a RESTful API for user authentication"
)

# Evaluate if response matches expectations
```

## Research & Resources

These prompts were designed based on research into:
- AI system prompt engineering best practices (2025)
- Role-based prompting effectiveness
- Software development domain expertise
- Persona pattern implementation

Key findings:
- Detailed, specific prompts outperform generic ones
- Domain relevance is critical for effectiveness
- Examples and patterns improve output quality
- Behavioral guidelines shape response style

## Contributing

When adding or modifying prompts:

1. **Test Thoroughly**: Verify prompt produces expected behavior
2. **Follow Structure**: Use consistent formatting
3. **Be Specific**: Include concrete technologies and practices
4. **Add Examples**: Show preferred patterns
5. **Document Changes**: Update this README if adding new roles

## Questions?

For questions about system prompts or role customization, see:
- Main README: `../../README.md`
- Design docs: `../../docs/DESIGN.md`
- Instance manager code: `../../src/orchestrator/instance_manager.py`
