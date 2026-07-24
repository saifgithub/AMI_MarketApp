# Email Templates for AMI Trade Support

All email templates use the email_service.py senders from the AMI website API.
Templates here provide structured content that the processor fills in before sending.

## Template Format

Each template is a `.md` file with:
- `### subject:` — the email subject line
- `### to_pattern:` — how the recipient address is determined
- `### content:` — the email body (text or HTML)
- `### tags:` — comma-separated tags for matching

## Auto-Reply Templates

When the KB matches a user's email and we can generate an answer:
- Use `email_service.send_contact_answer()` to send

## No-Answer Templates

When no KB match is found:
- Save as draft for human review
- Optionally send a "we got it, a human will reply" acknowledgment

## Template Naming Convention

`<type>_<scenario>.md`

Types: auto_reply, escalation, acknowledgment, human_draft
Scenarios: account, billing, technical, general, etc.
