# Knowledge Media Assets

Knowledge Base answers may include supporting images and videos, but those media assets are not embedded as raw URLs in knowledge text and are not matched globally. A Knowledge Media Asset is a Resource Library Item bound to a Knowledge Base, with knowledge-specific keywords, description, enabled state, and priority on the binding; V1 matches these assets only after knowledge text is recalled, only within the recalled Knowledge Base scope, and returns them through existing Agent Reply Blocks. This keeps the experience understandable for non-technical users, avoids duplicated media uploads, preserves tenant isolation, and prevents LLMs from inventing or leaking media URLs.

