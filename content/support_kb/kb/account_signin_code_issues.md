# Question: I didn't get my sign-in code / forgot my password

**Keywords:** forgot password, reset password, sign in code, email code, didn't receive, not working, invalid code, expired code, can't log in, cant login
**Category:** account
**Source:** Verified against `mobile/lib/screens/auth/sign_in_screen.dart` (CR050), 2026-07-24.

There is no password to forget — AMI Trade doesn't use one. If a customer asks about a forgotten
password, they mean the sign-in flow generally; redirect them to the real mechanism.

**Answer:** AMI Trade doesn't use passwords. Sign in with one tap using Apple or Google, or tap
"Use email instead" to get a 6-digit code by email. If the code doesn't arrive: check spam, make
sure you're using the same email address you started with, and request a fresh code (codes expire
after a short window). Still stuck? Reply with your email address and we'll look into it.

**Internal note:** if this keeps failing for a specific user, escalate to the R track — it's
likely an email-delivery or backend issue, not something the customer is doing wrong.

---
