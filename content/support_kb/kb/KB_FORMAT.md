# AMI Support — Email Knowledge Base

This directory holds the knowledge base for the email processor.

## How It Works

The KB starts empty and grows organically from human responses. Every time a 
customer is routed to human review and you reply, the system can extract your
answer and add it to the KB. Next time a similar question comes in, the AI
will auto-answer instead of routing to you.

## Entry Format

KB entries are `.md` files. Each entry has:

```markdown
# Question: [Question title]

**Keywords:** comma, separated, keywords
**Category:** billing, technical, account, general, etc.

[Your approved answer here — the actual text you want AI to send back.]

---
```

## Adding KB Entries

**Manual:** Create `.md` files directly in this directory with the format above.

**Automatic:** When you reply to an email that was pending, the `kb_ingest.py`
script can extract the Q&A and add it here automatically.

## Maintenance

- Review KB entries monthly
- Remove outdated entries
- Merge duplicate entries
- The KB grows organically — every human response is an opportunity to add a new entry
