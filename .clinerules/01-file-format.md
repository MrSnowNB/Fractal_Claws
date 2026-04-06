---
title: File Format Standards
version: "1.0"
scope: global
applies_to: all_agents
---

# File Format Standards

## Rule

Every file created or modified by an agent must be one of:

- **Markdown with YAML frontmatter** — `.md` files beginning with a `---` block
- **Pure YAML** — `.yaml` or `.yml` files with no free-form prose

No agent may produce `.txt`, `.json`, `.toml`, `.ini`, `.csv`, or binary files unless the human operator explicitly overrides this rule in the task spec.

## YAML Frontmatter Minimum Fields

Every `.md` file must include at minimum:

```yaml
---
title: <descriptive title>
version: "<semver or date string>"
last_updated: "<YYYY-MM-DD>"
---
```

## Validation

Before writing any file, the agent must verify:
1. The extension is `.md`, `.yaml`, or `.yml`
2. The frontmatter block opens and closes with `---`
3. Required fields are present and non-empty

Violation of this rule constitutes a policy failure → trigger full failure handling procedure.
